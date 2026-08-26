"""Experiment runner for quantization experiments.

This module orchestrates the full experiment pipeline:
load model -> quantize -> evaluate -> collect stats -> log to DB.

Logging is performed through the **SyncManager** which provides unified
Postgres / Weights & Biases tracking with clear ownership:
- Postgres: structured summaries, configs, reproducibility metadata
- W&B: time-series metrics, training curves, artifacts

Design principle: **fail-fast with guidance**.  Silent fallbacks and bare
``except: pass`` blocks are forbidden.  Every error is either:
- A hard failure that aborts the experiment, or
- An explicitly logged warning with actionable guidance.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer

from ..db import (
    get_session,
    log_experiment,
    log_hardware_stats,
    log_layer_metrics_batch,
    log_metrics,
    log_quant_config,
    update_experiment_status,
    update_quant_config_status,
)
from ..hooks import ActivationStatsHook, KVCacheStatsHook, WeightStatsHook
from ..quant import Quantizer, QuantizerConfig, get_quantizer, list_quantizers
from ..stacking import get_stack_summary, is_stack_valid, normalize_stack_order
from ..tracking.sync_manager import SyncManager, hash_config, generate_run_id
from ..utils.environment import capture_environment, get_or_create_snapshot
from ..utils.seeds import set_deterministic_seeds
from .datasets import compute_perplexity, load_calibration_data, fingerprint_calibration_data
from .hardware import HardwareStats, detect_hardware, measure_latency, measure_memory

logger = logging.getLogger(__name__)


class ExperimentConfig(BaseModel):
    """Configuration for an experiment."""
    
    # Model settings
    model_path: str = Field(..., description="HuggingFace model ID or local path")
    model_dtype: str = Field("float16", description="Model dtype (float16, bfloat16)")
    device: str = Field("cuda", description="Device to run on")
    
    # Quantization settings — all required, no silent defaults
    quant_methods: list[str] = Field(..., description="Quantization methods to apply")
    bit_width: int = Field(..., description="Bit width for quantization")
    per_channel: bool = Field(True, description="Use per-channel quantization")
    group_size: int | None = Field(..., description="Group size for quantization (None = per-channel)")
    
    # Calibration settings — all required, no silent defaults
    calib_dataset: str = Field(..., description="Calibration dataset")
    calib_size: int = Field(..., description="Number of calibration samples")
    calib_seq_length: int = Field(2048, description="Calibration sequence length")
    
    # Evaluation settings
    eval_datasets: list[str] = Field(default_factory=lambda: ["wikitext2"], description="Evaluation datasets")
    eval_max_samples: int | None = Field(None, description="Max evaluation samples")
    
    # Hardware settings
    hardware_profile: str = Field("default", description="Hardware profile name")
    warmup_iterations: int = Field(3, description="Warmup iterations for benchmarking")
    benchmark_iterations: int = Field(10, description="Benchmark iterations")
    
    # Hook settings
    capture_weights: bool = Field(True, description="Capture weight statistics")
    capture_activations: bool = Field(False, description="Capture activation statistics")
    capture_kv: bool = Field(False, description="Capture KV cache statistics")
    
    # Experiment metadata
    name: str | None = Field(None, description="Experiment name")
    notes: str | None = Field(None, description="Experiment notes")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering")
    
    # Paper references
    paper_ids: list[str] = Field(default_factory=list, description="Paper IDs for context")
    
    # Report settings
    generate_scientist_report: bool = Field(True, description="Generate scientist LLM report")
    
    # Reproducibility
    seed: int = Field(42, description="Random seed for reproducibility")
    
    # Multi-GPU
    num_gpus: int = Field(1, ge=1, description="Number of GPUs for distributed quantization")
    
    # lm-evaluation-harness integration
    lm_eval_suite: str | None = Field(None, description="lm-eval suite preset (e.g. 'smoothquant_175b', 'gptq_zeroshot')")
    lm_eval_tasks: list[str] | None = Field(None, description="Explicit lm-eval task list (overrides suite)")
    
    # vLLM benchmarking
    run_vllm_benchmark: bool = Field(False, description="Run vLLM serving benchmarks after quantization")
    vllm_config: dict[str, Any] | None = Field(None, description="Optional overrides for VLLMConfig (port, batch_sizes, etc.)")


@dataclass
class ExperimentResult:
    """Result of an experiment."""
    experiment_id: int
    model_name: str
    status: str
    
    # Timing
    total_time_seconds: float = 0.0
    quantization_time_seconds: float = 0.0
    evaluation_time_seconds: float = 0.0
    
    # Results per method
    method_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Hardware info
    hardware_profile: dict[str, Any] = field(default_factory=dict)
    
    # Errors
    errors: list[str] = field(default_factory=list)


def run_experiment(
    config: ExperimentConfig,
    db_url: str | None = None,
) -> ExperimentResult:
    """Run a quantization experiment with unified tracking.
    
    The runner integrates with the SyncManager for unified Postgres / W&B
    logging, captures environment snapshots for reproducibility, enforces
    deterministic seeds, and fingerprints calibration data.
    
    **Fail-fast design**: infrastructure errors (database, tracking, env
    capture) abort the experiment immediately rather than producing results
    with silently missing metadata.  Only per-batch forward-pass errors
    during activation collection are tolerated (logged at WARNING level).
    
    Args:
        config: Experiment configuration
        db_url: Optional database URL
        
    Returns:
        ExperimentResult with all results
        
    Raises:
        RuntimeError: If required infrastructure (DB, SyncManager, env
            capture) cannot be initialized.
    """
    start_time = time.time()
    
    logger.info(f"Starting experiment with model: {config.model_path}")
    logger.info(f"Quantization methods: {config.quant_methods}")
    
    # ── Validate GPU availability ──────────────────────────────────────
    if config.device == "cuda" and config.num_gpus > 1:
        available_gpus = torch.cuda.device_count()
        if config.num_gpus > available_gpus:
            raise ValueError(
                f"Requested {config.num_gpus} GPUs but only {available_gpus} available. "
                f"Reduce --num-gpus or ensure all GPUs are visible via CUDA_VISIBLE_DEVICES."
            )
    
    # ── Reproducibility: enforce deterministic seeds ──────────────────
    seed_report = set_deterministic_seeds(config.seed)
    logger.info(f"Seeds set: {seed_report}")
    
    # ── Build config dict for hashing ────────────────────────────────
    config_dict = config.model_dump()
    cfg_hash = hash_config(config_dict)
    
    # ── Resolve database URL ─────────────────────────────────────────
    effective_db_url = db_url or os.getenv("DATABASE_URL", "")
    if not effective_db_url:
        raise RuntimeError(
            "DATABASE_URL is required. Set the DATABASE_URL environment variable "
            "or pass db_url to run_experiment().  Example:\n"
            "  export DATABASE_URL=postgresql://postgres:pass@localhost:5432/experiments"
        )
    
    # ── SyncManager for unified Postgres / W&B logging ───────────────
    # Fail-fast: SyncManager is the backbone of experiment tracking.
    sync = SyncManager(
        db_url=effective_db_url,
        wandb_project=os.getenv("WANDB_PROJECT", ""),
    )
    
    # Get database session (used for direct ops like layer metrics)
    session = get_session(db_url)
    
    # ── Reproducibility: environment snapshot (mandatory) ─────────────
    environment_id = get_or_create_snapshot(effective_db_url)
    logger.info(f"Environment snapshot: id={environment_id}")
    
    # Detect hardware
    hw_profile = detect_hardware()
    
    # ── Create experiment record ─────────────────────────────────────
    experiment = log_experiment(
        session=session,
        model_name=config.model_path,
        name=config.name,
        model_path=config.model_path,
        base_precision=config.model_dtype,
        hardware_profile=config.hardware_profile,
        gpu_type=hw_profile.gpu_type,
        gpu_count=hw_profile.gpu_count,
        notes=config.notes,
        tags=config.tags,
    )
    
    # Patch reproducibility columns onto the experiment row (mandatory)
    experiment.config_hash = cfg_hash
    experiment.seed = config.seed
    experiment.environment_id = environment_id
    session.commit()
    
    # Start SyncManager run (links Postgres experiment to W&B)
    run = sync.start_run(
        model_name=config.model_path,
        method=config.quant_methods[0],
        bit_width=config.bit_width,
        config=config_dict,
        group_size=config.group_size,
        name=config.name or f"exp-{experiment.id}",
        hardware_profile=config.hardware_profile,
        gpu_type=hw_profile.gpu_type,
        gpu_count=hw_profile.gpu_count,
        notes=config.notes,
        tags=config.tags or [],
        environment_id=environment_id,
    )
    
    result = ExperimentResult(
        experiment_id=experiment.id,
        model_name=config.model_path,
        status="running",
        hardware_profile=hw_profile.to_dict(),
    )
    
    try:
        # Validate stack
        valid, reason = is_stack_valid(config.quant_methods)
        if not valid:
            raise ValueError(f"Invalid method stack: {reason}")
        
        # Normalize order
        methods = normalize_stack_order(config.quant_methods)
        logger.info(f"Normalized method order: {methods}")
        
        # Load model and tokenizer
        logger.info("Loading model and tokenizer...")
        dtype = torch.float16 if config.model_dtype == "float16" else torch.bfloat16
        
        tokenizer = AutoTokenizer.from_pretrained(
            config.model_path,
            trust_remote_code=True,
        )
        
        model = AutoModelForCausalLM.from_pretrained(
            config.model_path,
            torch_dtype=dtype,
            device_map=config.device if config.device != "cpu" else None,
            trust_remote_code=True,
        )
        
        if config.device == "cpu":
            model = model.to(config.device)
        
        # Set pad token if needed
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        # Initialize hooks
        weight_hook = WeightStatsHook(compute_histogram=False) if config.capture_weights else None
        activation_hook = ActivationStatsHook() if config.capture_activations else None
        kv_hook = KVCacheStatsHook() if config.capture_kv else None
        
        # Collect pre-quantization stats
        if weight_hook:
            logger.info("Collecting pre-quantization weight statistics...")
            weight_hook.collect_pre_quant_stats(model)
        
        # ── Load and fingerprint calibration data ────────────────────
        logger.info(f"Loading calibration data from {config.calib_dataset}...")
        calib_data = load_calibration_data(
            dataset_name=config.calib_dataset,
            tokenizer=tokenizer,
            num_samples=config.calib_size,
            seq_length=config.calib_seq_length,
            seed=config.seed,
        )
        
        # Fingerprint calibration data for reproducibility tracking
        calib_hash = fingerprint_calibration_data(calib_data)
        logger.info(f"Calibration data fingerprint: {calib_hash[:16]}...")
        
        # Log calibration record to Postgres (mandatory for reproducibility)
        from ..db.models import CalibrationRecord
        calib_record = CalibrationRecord(
            experiment_id=experiment.id,
            dataset_name=config.calib_dataset,
            num_samples=config.calib_size,
            sequence_length=config.calib_seq_length,
            seed=config.seed,
            data_hash=calib_hash,
        )
        session.add(calib_record)
        session.commit()
        
        # Log calibration info to W&B via SyncManager
        sync.log_step(run, {
            "calib/dataset": config.calib_dataset,
            "calib/samples": config.calib_size,
            "calib/hash": calib_hash[:16],
        })
        
        # Collect activation statistics during calibration
        if activation_hook:
            logger.info("Collecting activation statistics...")
            handles = activation_hook.register(model)
            
            model.eval()
            with torch.no_grad():
                for batch_idx, batch in enumerate(calib_data[:32]):
                    batch = batch.to(config.device)
                    try:
                        model(batch)
                    except Exception as e:
                        # Per-batch failure is tolerable (e.g. OOM on one sample)
                        # but must be visible, not silently swallowed.
                        logger.warning(
                            f"Activation collection: batch {batch_idx} failed: {e}. "
                            "Skipping this batch; remaining batches will still be processed."
                        )
            
            activation_hook.remove_hooks(handles)
            activation_hook.finalize_stats()
        
        # Apply quantization methods
        quant_start = time.time()
        parent_config_id = None
        
        for stack_order, method in enumerate(methods):
            logger.info(f"Applying quantization method: {method}")
            
            # Create quantizer config
            quant_config = QuantizerConfig(
                method=method,
                bit_width=config.bit_width,
                per_channel=config.per_channel,
                group_size=config.group_size,
                calib_dataset=config.calib_dataset,
                calib_size=config.calib_size,
                calib_seq_length=config.calib_seq_length,
                num_gpus=config.num_gpus,
            )
            
            # Log quant config
            db_quant_config = log_quant_config(
                session=session,
                experiment_id=experiment.id,
                method_name=method,
                bit_width=config.bit_width,
                per_channel=config.per_channel,
                group_size=config.group_size,
                stack_order=stack_order,
                parent_config_id=parent_config_id,
                config_json=quant_config.model_dump(),
                calib_dataset=config.calib_dataset,
                calib_size=config.calib_size,
                calib_seq_length=config.calib_seq_length,
            )
            
            try:
                # Get quantizer
                quantizer = get_quantizer(method, quant_config)
                
                # Prepare
                method_start = time.time()
                state = quantizer.prepare(model, calib_data)
                
                # Apply
                model = quantizer.apply(model, state)
                method_duration = time.time() - method_start
                
                # Ensure model is on the correct device and dtype after quantization.
                # Some backends (e.g. LightCompress) may return the model on CPU.
                if config.device != "cpu":
                    model = model.to(config.device)
                model = model.to(dtype)
                
                # Get metadata
                metadata = quantizer.metadata(state)
                
                # Log step to W&B
                sync.log_step(run, {
                    f"quant/{method}/duration_s": method_duration,
                    f"quant/{method}/bit_width": config.bit_width,
                })
                
                # Update config status
                update_quant_config_status(
                    session=session,
                    quant_config_id=db_quant_config.id,
                    status="completed",
                    duration_seconds=method_duration,
                )
                
                result.method_results[method] = {
                    "status": "completed",
                    "duration_seconds": method_duration,
                    "metadata": metadata,
                }
                
                parent_config_id = db_quant_config.id
                
            except Exception as e:
                logger.error(f"Quantization failed for {method}: {e}")
                update_quant_config_status(
                    session=session,
                    quant_config_id=db_quant_config.id,
                    status="failed",
                    error_message=str(e),
                )
                result.errors.append(f"Quantization {method} failed: {e}")
                result.method_results[method] = {
                    "status": "failed",
                    "error": str(e),
                }
                # Fail-fast: quantization failure is fatal for the experiment
                raise RuntimeError(
                    f"Quantization method '{method}' failed. Cannot continue "
                    f"evaluation on a non-quantized model. Error: {e}"
                ) from e
        
        result.quantization_time_seconds = time.time() - quant_start
        
        # Collect post-quantization stats
        if weight_hook:
            logger.info("Collecting post-quantization weight statistics...")
            weight_hook.collect_post_quant_stats(model)
            
            # Log weight stats
            pre_records = weight_hook.to_db_records(
                experiment_id=experiment.id,
                quant_config_id=parent_config_id,
                stat_type="pre_quant",
            )
            post_records = weight_hook.to_db_records(
                experiment_id=experiment.id,
                quant_config_id=parent_config_id,
                stat_type="post_quant",
            )
            
            # Batch insert
            if pre_records:
                log_layer_metrics_batch(session, experiment.id, pre_records[:100], parent_config_id)
            if post_records:
                log_layer_metrics_batch(session, experiment.id, post_records[:100], parent_config_id)
        
        # Log activation stats
        if activation_hook:
            act_records = activation_hook.to_db_records(
                experiment_id=experiment.id,
                quant_config_id=parent_config_id,
            )
            if act_records:
                log_layer_metrics_batch(session, experiment.id, act_records[:100], parent_config_id)
        
        # Evaluation — fail-fast: every requested dataset must succeed
        eval_start = time.time()
        
        for dataset_name in config.eval_datasets:
            logger.info(f"Evaluating on {dataset_name}...")
            
            # Compute perplexity using LightCompress's evaluation
            ppl_results = compute_perplexity(
                model=model,
                tokenizer=tokenizer,
                dataset_name=dataset_name,
                seq_len=config.calib_seq_length,
                batch_size=1,
            )
            
            # Log metrics to Postgres
            log_metrics(
                session=session,
                experiment_id=experiment.id,
                quant_config_id=parent_config_id,
                dataset=dataset_name,
                metric_name="perplexity",
                value=ppl_results["perplexity"],
                split="test",
            )
            
            # Log time-series step to W&B
            sync.log_step(run, {
                f"eval/{dataset_name}/perplexity": ppl_results["perplexity"],
            })
            
            logger.info(f"{dataset_name} perplexity: {ppl_results['perplexity']:.2f}")
        
        # ── lm-evaluation-harness (zero-shot accuracy, GSM8K, etc.) ──
        if config.lm_eval_suite or config.lm_eval_tasks:
            from .lm_eval_runner import run_lm_eval

            logger.info(
                f"Running lm-eval: suite={config.lm_eval_suite}, "
                f"tasks={config.lm_eval_tasks}"
            )

            lm_eval_model_path = config.model_path
            for method in methods:
                mr = result.method_results.get(method, {})
                out_path = mr.get("metadata", {}).get("output_path")
                if out_path:
                    lm_eval_model_path = out_path

            lm_eval_results = run_lm_eval(
                model_path=lm_eval_model_path,
                suite=config.lm_eval_suite or "standard",
                tasks=config.lm_eval_tasks,
                device=config.device,
            )

            for lr in lm_eval_results:
                log_metrics(
                    session=session,
                    experiment_id=experiment.id,
                    quant_config_id=parent_config_id,
                    dataset=lr.task_name,
                    metric_name=lr.metric_name,
                    value=lr.value,
                    split="test",
                )
                sync.log_step(run, {
                    f"lm_eval/{lr.task_name}/{lr.metric_name}": lr.value,
                })

            logger.info(f"lm-eval complete: {len(lm_eval_results)} metrics")

        result.evaluation_time_seconds = time.time() - eval_start
        
        # Hardware benchmarking
        logger.info("Running hardware benchmarks...")
        
        # Create input function for benchmarking
        def input_fn():
            return {"input_ids": calib_data[0].to(config.device)}
        
        latency_stats = measure_latency(
            model=model,
            input_fn=input_fn,
            warmup_iterations=config.warmup_iterations,
            benchmark_iterations=config.benchmark_iterations,
            device=config.device,
        )
        
        memory_stats = measure_memory(model, config.device)
        
        # Log hardware stats to Postgres
        log_hardware_stats(
            session=session,
            experiment_id=experiment.id,
            quant_config_id=parent_config_id,
            gpu_type=hw_profile.gpu_type,
            gpu_memory_gb=hw_profile.gpu_memory_gb,
            latency_p50=latency_stats.p50,
            latency_p95=latency_stats.p95,
            latency_mean=latency_stats.mean,
            latency_std=latency_stats.std,
            tokens_per_second=latency_stats.tokens_per_second,
            batch_size=latency_stats.batch_size,
            sequence_length=latency_stats.sequence_length,
            memory_allocated=memory_stats.allocated_gb,
            memory_peak=memory_stats.peak_gb,
            model_size_mb=memory_stats.model_size_mb,
        )
        
        # Log hardware summary to W&B
        sync.log_step(run, {
            "hw/latency_p50_ms": latency_stats.p50,
            "hw/latency_p95_ms": latency_stats.p95,
            "hw/tokens_per_sec": latency_stats.tokens_per_second,
            "hw/memory_peak_gb": memory_stats.peak_gb,
        })
        
        # ── vLLM serving benchmark (optional) ─────────────────────────
        if config.run_vllm_benchmark:
            from ..serving.vllm_benchmark import VLLMBenchmark, VLLMConfig

            logger.info("Starting vLLM serving benchmark...")

            # Determine quantized model path for vLLM export
            save_dir = None
            for method in methods:
                mr = result.method_results.get(method, {})
                if mr.get("metadata", {}).get("output_path"):
                    save_dir = mr["metadata"]["output_path"]

            if save_dir is None:
                # Use a temp directory derived from model name
                save_dir = str(
                    Path("/tmp/llmc_vllm_export") / Path(config.model_path).name
                )
                # Save the quantized model first
                logger.info(f"Saving quantized model for vLLM export to {save_dir}")
                model.save_pretrained(save_dir)

            # Export for vLLM using the LLMCQuantizer export utility
            from ..quant.llmc_wrappers import LLMCQuantizer

            export_quant_config = QuantizerConfig(
                method=methods[-1],
                bit_width=config.bit_width,
                per_channel=config.per_channel,
                group_size=config.group_size,
            )
            exporter = LLMCQuantizer(export_quant_config, algorithm=methods[-1])
            vllm_export_path = exporter.export_for_vllm(
                model_path=save_dir,
                save_path=str(Path(save_dir).parent / f"{Path(save_dir).name}_vllm"),
            )
            logger.info(f"vLLM export path: {vllm_export_path}")

            # Build VLLMConfig from defaults + user overrides
            vllm_cfg_dict = {"model_path": vllm_export_path}
            if config.vllm_config:
                vllm_cfg_dict.update(config.vllm_config)
            vllm_cfg = VLLMConfig(**vllm_cfg_dict)

            # Run benchmarks
            benchmark = VLLMBenchmark(vllm_cfg)
            benchmark.start_server()
            try:
                vllm_results = benchmark.run_benchmarks()
            finally:
                benchmark.stop_server()

            # Log vLLM results to Postgres and W&B
            for vr in vllm_results:
                vr_dict = vr.to_dict()
                prefix = f"vllm/bs{vr.batch_size}_in{vr.input_length}"

                log_hardware_stats(
                    session=session,
                    experiment_id=experiment.id,
                    quant_config_id=parent_config_id,
                    gpu_type=hw_profile.gpu_type,
                    gpu_memory_gb=hw_profile.gpu_memory_gb,
                    latency_mean=vr.e2e_latency_mean * 1000,
                    latency_p50=vr.e2e_latency_p50 * 1000,
                    latency_p95=vr.e2e_latency_p95 * 1000,
                    tokens_per_second=vr.tokens_per_second,
                    batch_size=vr.batch_size,
                    sequence_length=vr.input_length,
                )

                sync.log_step(run, {
                    f"{prefix}/ttft_mean_s": vr.ttft_mean,
                    f"{prefix}/tbt_mean_s": vr.tbt_mean,
                    f"{prefix}/tokens_per_sec": vr.tokens_per_second,
                    f"{prefix}/e2e_latency_p50_s": vr.e2e_latency_p50,
                    f"{prefix}/e2e_latency_p95_s": vr.e2e_latency_p95,
                })

            result.method_results["vllm_benchmark"] = {
                "status": "completed",
                "num_configs": len(vllm_results),
                "results": [vr.to_dict() for vr in vllm_results],
            }
            logger.info(f"vLLM benchmark complete: {len(vllm_results)} configurations")

        # Mark experiment as completed
        update_experiment_status(session, experiment.id, "completed")
        result.status = "completed"
        
        # Finalize SyncManager (write summaries to Postgres, close W&B run)
        sync.log_summary(run, {
            "total_time_s": time.time() - start_time,
            "quant_time_s": result.quantization_time_seconds,
            "eval_time_s": result.evaluation_time_seconds,
            "status": "completed",
            "config_hash": cfg_hash,
        })
        sync.finish_run(run=run, status="completed")
        
    except Exception as e:
        logger.error(f"Experiment failed: {e}")
        update_experiment_status(session, experiment.id, "failed", str(e))
        result.status = "failed"
        result.errors.append(str(e))
        
        try:
            sync.finish_run(run=run, status="failed")
        except Exception as finish_err:
            logger.error(
                f"SyncManager.finish_run also failed during cleanup: {finish_err}. "
                "W&B run may be left in an open state. Close it manually with:\n"
                "  wandb sync --clean"
            )
        
        raise  # Re-raise: callers must know the experiment failed
    
    finally:
        session.close()
    
    result.total_time_seconds = time.time() - start_time
    
    logger.info(f"Experiment completed in {result.total_time_seconds:.1f}s")
    logger.info(f"Status: {result.status}")
    
    return result


def run_baseline_experiment(
    model_path: str,
    eval_datasets: list[str] | None = None,
    db_url: str | None = None,
) -> ExperimentResult:
    """Run a baseline experiment without quantization.
    
    Args:
        model_path: Model path
        eval_datasets: Evaluation datasets
        db_url: Database URL
        
    Returns:
        ExperimentResult for baseline
    """
    config = ExperimentConfig(
        model_path=model_path,
        quant_methods=[],  # No quantization
        eval_datasets=eval_datasets or ["wikitext2"],
        name="baseline",
        tags=["baseline"],
    )
    
    # Modify to skip quantization
    # This would need special handling in run_experiment
    # For now, just run with RTN at 16-bit (effectively no quantization)
    config.quant_methods = ["rtn"]
    config.bit_width = 16
    
    return run_experiment(config, db_url)


def compare_methods(
    model_path: str,
    methods: list[str],
    bit_widths: list[int] | None = None,
    eval_datasets: list[str] | None = None,
    db_url: str | None = None,
) -> list[ExperimentResult]:
    """Compare multiple quantization methods.
    
    Fail-fast: if any single method/bit_width combination fails, the
    entire comparison aborts.  Partial results are unreliable for
    publication.  Fix the failing configuration before re-running.
    
    Args:
        model_path: Model path
        methods: Methods to compare
        bit_widths: Bit widths to test
        eval_datasets: Evaluation datasets
        db_url: Database URL
        
    Returns:
        List of ExperimentResults
        
    Raises:
        RuntimeError: If any method/bit_width combination fails.
    """
    bit_widths = bit_widths or [4]
    eval_datasets = eval_datasets or ["wikitext2"]
    
    results = []
    
    for method in methods:
        for bit_width in bit_widths:
            logger.info(f"Running comparison: {method} @ {bit_width}-bit")
            
            config = ExperimentConfig(
                model_path=model_path,
                quant_methods=[method],
                bit_width=bit_width,
                eval_datasets=eval_datasets,
                name=f"compare_{method}_{bit_width}bit",
                tags=["comparison", method, f"{bit_width}bit"],
            )
            
            result = run_experiment(config, db_url)
            results.append(result)
    
    return results
