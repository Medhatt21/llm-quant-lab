"""Database logging utilities for structured experiment tracking."""

from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .models import (
    Experiment,
    ExperimentCreate,
    HardwareStat,
    LayerMetric,
    Metric,
    MetricCreate,
    PaperNote,
    QuantConfig,
    QuantConfigCreate,
    ScientistReport,
    get_session,
)


def get_git_info() -> tuple[str | None, str | None]:
    """Get current git SHA and branch."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        sha = None
    
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        branch = None
    
    return sha, branch


def log_experiment(
    session: Session,
    model_name: str,
    name: str | None = None,
    description: str | None = None,
    model_path: str | None = None,
    base_precision: str = "fp16",
    hardware_profile: str | None = None,
    gpu_type: str | None = None,
    gpu_count: int = 1,
    notes: str | None = None,
    tags: list[str] | None = None,
) -> Experiment:
    """Create a new experiment record.
    
    Args:
        session: Database session
        model_name: Name of the model (e.g., 'facebook/opt-125m')
        name: Optional experiment name
        description: Optional description
        model_path: Optional path to local model
        base_precision: Base precision (default: 'fp16')
        hardware_profile: Hardware profile name
        gpu_type: GPU type string
        gpu_count: Number of GPUs
        notes: User notes
        tags: List of tags for filtering
        
    Returns:
        Created Experiment object
    """
    git_sha, git_branch = get_git_info()
    
    experiment = Experiment(
        name=name,
        description=description,
        git_sha=git_sha,
        git_branch=git_branch,
        model_name=model_name,
        model_path=model_path,
        base_precision=base_precision,
        hardware_profile=hardware_profile,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        status="running",
        notes=notes,
        tags=tags or [],
    )
    
    session.add(experiment)
    session.commit()
    session.refresh(experiment)
    
    return experiment


def update_experiment_status(
    session: Session,
    experiment_id: int,
    status: str,
    error_message: str | None = None,
) -> Experiment:
    """Update experiment status.
    
    Args:
        session: Database session
        experiment_id: Experiment ID
        status: New status ('pending', 'running', 'completed', 'failed', 'cancelled')
        error_message: Optional error message for failed experiments
        
    Returns:
        Updated Experiment object
    """
    experiment = session.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise ValueError(f"Experiment {experiment_id} not found")
    
    experiment.status = status
    if error_message:
        experiment.error_message = error_message
    
    session.commit()
    session.refresh(experiment)
    
    return experiment


def log_quant_config(
    session: Session,
    experiment_id: int,
    method_name: str,
    bit_width: int,
    per_channel: bool = True,
    is_symmetric: bool = True,
    group_size: int | None = None,
    activation_quant: bool = False,
    activation_bits: int | None = None,
    kv_quant: bool = False,
    kv_bits: int | None = None,
    stack_order: int = 0,
    parent_config_id: int | None = None,
    config_json: dict[str, Any] | None = None,
    calib_dataset: str | None = None,
    calib_size: int | None = None,
    calib_seq_length: int | None = None,
    method_version: str | None = None,
) -> QuantConfig:
    """Log a quantization configuration.
    
    Args:
        session: Database session
        experiment_id: Parent experiment ID
        method_name: Quantization method name (e.g., 'awq', 'gptq')
        bit_width: Bit width for quantization
        per_channel: Whether to use per-channel quantization
        is_symmetric: Whether to use symmetric quantization
        group_size: Group size for quantization
        activation_quant: Whether to quantize activations
        activation_bits: Bit width for activation quantization
        kv_quant: Whether to quantize KV cache
        kv_bits: Bit width for KV cache quantization
        stack_order: Order in stack (0 = first)
        parent_config_id: Previous method in stack
        config_json: Full configuration dictionary
        calib_dataset: Calibration dataset name
        calib_size: Number of calibration samples
        calib_seq_length: Sequence length for calibration
        method_version: Version of the quantization method
        
    Returns:
        Created QuantConfig object
    """
    quant_config = QuantConfig(
        experiment_id=experiment_id,
        method_name=method_name,
        method_version=method_version,
        bit_width=bit_width,
        per_channel=per_channel,
        is_symmetric=is_symmetric,
        group_size=group_size,
        activation_quant=activation_quant,
        activation_bits=activation_bits,
        kv_quant=kv_quant,
        kv_bits=kv_bits,
        stack_order=stack_order,
        parent_config_id=parent_config_id,
        config_json=config_json or {},
        calib_dataset=calib_dataset,
        calib_size=calib_size,
        calib_seq_length=calib_seq_length,
        status="running",
    )
    
    session.add(quant_config)
    session.commit()
    session.refresh(quant_config)
    
    return quant_config


def update_quant_config_status(
    session: Session,
    quant_config_id: int,
    status: str,
    duration_seconds: float | None = None,
    error_message: str | None = None,
) -> QuantConfig:
    """Update quantization config status.
    
    Args:
        session: Database session
        quant_config_id: QuantConfig ID
        status: New status
        duration_seconds: Time taken for quantization
        error_message: Optional error message
        
    Returns:
        Updated QuantConfig object
    """
    quant_config = session.query(QuantConfig).filter(QuantConfig.id == quant_config_id).first()
    if quant_config is None:
        raise ValueError(f"QuantConfig {quant_config_id} not found")
    
    quant_config.status = status
    if duration_seconds is not None:
        quant_config.duration_seconds = duration_seconds
    if error_message:
        quant_config.error_message = error_message
    
    session.commit()
    session.refresh(quant_config)
    
    return quant_config


def log_metrics(
    session: Session,
    experiment_id: int,
    dataset: str,
    metric_name: str,
    value: float,
    quant_config_id: int | None = None,
    split: str = "test",
    metadata: dict[str, Any] | None = None,
) -> Metric:
    """Log an evaluation metric.
    
    Args:
        session: Database session
        experiment_id: Parent experiment ID
        dataset: Dataset name
        metric_name: Metric name (e.g., 'perplexity', 'accuracy')
        value: Metric value
        quant_config_id: Optional quant config ID
        split: Dataset split (default: 'test')
        metadata: Additional metadata
        
    Returns:
        Created Metric object
    """
    metric = Metric(
        experiment_id=experiment_id,
        quant_config_id=quant_config_id,
        dataset=dataset,
        split=split,
        metric_name=metric_name,
        value=value,
        metadata=metadata or {},
    )
    
    session.add(metric)
    session.commit()
    session.refresh(metric)
    
    return metric


def log_metrics_batch(
    session: Session,
    experiment_id: int,
    metrics: list[dict[str, Any]],
    quant_config_id: int | None = None,
) -> list[Metric]:
    """Log multiple metrics at once.
    
    Args:
        session: Database session
        experiment_id: Parent experiment ID
        metrics: List of metric dictionaries with keys: dataset, metric_name, value, split (optional)
        quant_config_id: Optional quant config ID
        
    Returns:
        List of created Metric objects
    """
    metric_objects = []
    for m in metrics:
        metric = Metric(
            experiment_id=experiment_id,
            quant_config_id=quant_config_id,
            dataset=m["dataset"],
            split=m.get("split", "test"),
            metric_name=m["metric_name"],
            value=m["value"],
            metadata=m.get("metadata", {}),
        )
        session.add(metric)
        metric_objects.append(metric)
    
    session.commit()
    for m in metric_objects:
        session.refresh(m)
    
    return metric_objects


def log_hardware_stats(
    session: Session,
    experiment_id: int,
    quant_config_id: int | None = None,
    gpu_type: str | None = None,
    gpu_memory_gb: float | None = None,
    latency_p50: float | None = None,
    latency_p95: float | None = None,
    latency_p99: float | None = None,
    latency_mean: float | None = None,
    latency_std: float | None = None,
    tokens_per_second: float | None = None,
    batch_size: int | None = None,
    sequence_length: int | None = None,
    memory_allocated: float | None = None,
    memory_reserved: float | None = None,
    memory_peak: float | None = None,
    power_avg: float | None = None,
    power_peak: float | None = None,
    energy_joules: float | None = None,
    model_size_mb: float | None = None,
    quantized_size_mb: float | None = None,
    compression_ratio: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> HardwareStat:
    """Log hardware statistics.
    
    Args:
        session: Database session
        experiment_id: Parent experiment ID
        quant_config_id: Optional quant config ID
        gpu_type: GPU type string
        gpu_memory_gb: GPU memory in GB
        latency_p50: 50th percentile latency (ms)
        latency_p95: 95th percentile latency (ms)
        latency_p99: 99th percentile latency (ms)
        latency_mean: Mean latency (ms)
        latency_std: Standard deviation of latency (ms)
        tokens_per_second: Throughput in tokens/second
        batch_size: Batch size used
        sequence_length: Sequence length used
        memory_allocated: Allocated GPU memory (GB)
        memory_reserved: Reserved GPU memory (GB)
        memory_peak: Peak GPU memory (GB)
        power_avg: Average power consumption (W)
        power_peak: Peak power consumption (W)
        energy_joules: Total energy consumed (J)
        model_size_mb: Original model size (MB)
        quantized_size_mb: Quantized model size (MB)
        compression_ratio: Compression ratio
        metadata: Additional metadata
        
    Returns:
        Created HardwareStat object
    """
    hw_stat = HardwareStat(
        experiment_id=experiment_id,
        quant_config_id=quant_config_id,
        gpu_type=gpu_type,
        gpu_memory_gb=gpu_memory_gb,
        latency_p50=latency_p50,
        latency_p95=latency_p95,
        latency_p99=latency_p99,
        latency_mean=latency_mean,
        latency_std=latency_std,
        tokens_per_second=tokens_per_second,
        batch_size=batch_size,
        sequence_length=sequence_length,
        memory_allocated=memory_allocated,
        memory_reserved=memory_reserved,
        memory_peak=memory_peak,
        power_avg=power_avg,
        power_peak=power_peak,
        energy_joules=energy_joules,
        model_size_mb=model_size_mb,
        quantized_size_mb=quantized_size_mb,
        compression_ratio=compression_ratio,
        metadata=metadata or {},
    )
    
    session.add(hw_stat)
    session.commit()
    session.refresh(hw_stat)
    
    return hw_stat


def log_layer_metrics(
    session: Session,
    experiment_id: int,
    layer_index: int,
    stat_name: str,
    value: float,
    quant_config_id: int | None = None,
    layer_name: str | None = None,
    layer_type: str | None = None,
    stat_type: str = "weight",
    histogram_bins: list[float] | None = None,
    histogram_counts: list[int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LayerMetric:
    """Log a layer-wise metric.
    
    Args:
        session: Database session
        experiment_id: Parent experiment ID
        layer_index: Layer index
        stat_name: Statistic name (e.g., 'weight_norm', 'outlier_ratio')
        value: Statistic value
        quant_config_id: Optional quant config ID
        layer_name: Layer name
        layer_type: Layer type (e.g., 'Linear', 'Attention')
        stat_type: Type of statistic ('weight', 'activation', 'kv_cache')
        histogram_bins: Optional histogram bin edges
        histogram_counts: Optional histogram counts
        metadata: Additional metadata
        
    Returns:
        Created LayerMetric object
    """
    layer_metric = LayerMetric(
        experiment_id=experiment_id,
        quant_config_id=quant_config_id,
        layer_index=layer_index,
        layer_name=layer_name,
        layer_type=layer_type,
        stat_name=stat_name,
        stat_type=stat_type,
        value=value,
        histogram_bins=histogram_bins,
        histogram_counts=histogram_counts,
        metadata=metadata or {},
    )
    
    session.add(layer_metric)
    session.commit()
    session.refresh(layer_metric)
    
    return layer_metric


def log_layer_metrics_batch(
    session: Session,
    experiment_id: int,
    layer_metrics: list[dict[str, Any]],
    quant_config_id: int | None = None,
) -> list[LayerMetric]:
    """Log multiple layer metrics at once.
    
    Args:
        session: Database session
        experiment_id: Parent experiment ID
        layer_metrics: List of layer metric dictionaries
        quant_config_id: Optional quant config ID
        
    Returns:
        List of created LayerMetric objects
    """
    metric_objects = []
    for lm in layer_metrics:
        layer_metric = LayerMetric(
            experiment_id=experiment_id,
            quant_config_id=quant_config_id,
            layer_index=lm["layer_index"],
            layer_name=lm.get("layer_name"),
            layer_type=lm.get("layer_type"),
            stat_name=lm["stat_name"],
            stat_type=lm.get("stat_type", "weight"),
            value=lm["value"],
            histogram_bins=lm.get("histogram_bins"),
            histogram_counts=lm.get("histogram_counts"),
            metadata=lm.get("metadata", {}),
        )
        session.add(layer_metric)
        metric_objects.append(layer_metric)
    
    session.commit()
    for m in metric_objects:
        session.refresh(m)
    
    return metric_objects


def log_scientist_report(
    session: Session,
    experiment_id: int,
    prompt_payload_json: dict[str, Any],
    report_markdown: str,
    llm_model: str | None = None,
    llm_provider: str | None = None,
    summary: str | None = None,
    pass_fail: str | None = None,
    confidence_score: float | None = None,
    reasoning_tags: list[str] | None = None,
    key_findings: list[str] | None = None,
    suggested_experiments: list[str] | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> ScientistReport:
    """Log a scientist LLM report.
    
    Args:
        session: Database session
        experiment_id: Parent experiment ID
        prompt_payload_json: Full prompt payload sent to LLM
        report_markdown: Full report in Markdown format
        llm_model: LLM model used
        llm_provider: LLM provider (e.g., 'openai', 'anthropic')
        summary: Short summary of the report
        pass_fail: Pass/fail judgment ('pass', 'fail', 'inconclusive', 'unknown')
        confidence_score: Confidence score (0-1)
        reasoning_tags: Tags for reasoning (e.g., 'novel insight', 'failure mode')
        key_findings: List of key findings
        suggested_experiments: List of suggested follow-up experiments
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        total_tokens: Total tokens used
        metadata: Additional metadata
        
    Returns:
        Created ScientistReport object
    """
    report = ScientistReport(
        experiment_id=experiment_id,
        llm_model=llm_model,
        llm_provider=llm_provider,
        prompt_payload_json=prompt_payload_json,
        report_markdown=report_markdown,
        summary=summary,
        pass_fail=pass_fail,
        confidence_score=confidence_score,
        reasoning_tags=reasoning_tags or [],
        key_findings=key_findings or [],
        suggested_experiments=suggested_experiments or [],
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        metadata=metadata or {},
    )
    
    session.add(report)
    session.commit()
    session.refresh(report)
    
    return report


# ============================================================================
# Query helpers
# ============================================================================


def get_experiment_with_details(session: Session, experiment_id: int) -> dict[str, Any] | None:
    """Get experiment with all related data.
    
    Args:
        session: Database session
        experiment_id: Experiment ID
        
    Returns:
        Dictionary with experiment and all related data
    """
    experiment = session.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        return None
    
    return {
        "experiment": experiment.to_dict(),
        "quant_configs": [qc.to_dict() for qc in experiment.quant_configs],
        "metrics": [m.to_dict() for m in experiment.metrics],
        "hardware_stats": [hs.to_dict() for hs in experiment.hardware_stats],
        "layer_metrics": [lm.to_dict() for lm in experiment.layer_metrics],
        "scientist_reports": [sr.to_dict() for sr in experiment.scientist_reports],
    }


def get_experiments_by_model(session: Session, model_name: str) -> list[Experiment]:
    """Get all experiments for a specific model.
    
    Args:
        session: Database session
        model_name: Model name to filter by
        
    Returns:
        List of Experiment objects
    """
    return session.query(Experiment).filter(Experiment.model_name == model_name).all()


def get_experiments_by_method(session: Session, method_name: str) -> list[Experiment]:
    """Get all experiments using a specific quantization method.
    
    Args:
        session: Database session
        method_name: Method name to filter by
        
    Returns:
        List of Experiment objects
    """
    return (
        session.query(Experiment)
        .join(QuantConfig)
        .filter(QuantConfig.method_name == method_name)
        .distinct()
        .all()
    )


def get_metrics_comparison(
    session: Session,
    method_names: list[str],
    metric_name: str = "perplexity",
    dataset: str | None = None,
) -> list[dict[str, Any]]:
    """Get metrics comparison across methods.
    
    Args:
        session: Database session
        method_names: List of method names to compare
        metric_name: Metric to compare
        dataset: Optional dataset filter
        
    Returns:
        List of comparison results
    """
    query = (
        session.query(
            QuantConfig.method_name,
            QuantConfig.bit_width,
            Experiment.model_name,
            Metric.dataset,
            Metric.value,
        )
        .join(Experiment)
        .join(Metric, Metric.quant_config_id == QuantConfig.id)
        .filter(QuantConfig.method_name.in_(method_names))
        .filter(Metric.metric_name == metric_name)
    )
    
    if dataset:
        query = query.filter(Metric.dataset == dataset)
    
    results = query.all()
    
    return [
        {
            "method_name": r[0],
            "bit_width": r[1],
            "model_name": r[2],
            "dataset": r[3],
            "value": r[4],
        }
        for r in results
    ]
