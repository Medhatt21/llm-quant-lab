"""Standardised experiment matrix runner.

Accepts a declarative matrix config (methods x models x bit_widths)
and executes the full grid, logging everything through the unified
SyncManager.

Usage::

    from src.eval.matrix_runner import MatrixConfig, run_matrix

    config = MatrixConfig(
        models=["facebook/opt-125m", "meta-llama/Llama-2-7b-hf"],
        methods=["gptq", "awq", "smoothquant", "rtn"],
        bit_widths=[4, 8],
        group_sizes=[128],
        eval_datasets=["wikitext2"],
    )
    results = run_matrix(config)
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MatrixConfig(BaseModel):
    """Declarative experiment matrix configuration."""

    # What to test
    models: list[str] = Field(
        default_factory=lambda: ["facebook/opt-125m"],
        description="HuggingFace model IDs or local paths",
    )
    methods: list[str] = Field(
        default_factory=lambda: ["gptq", "awq", "rtn"],
        description="Quantization methods to test",
    )
    bit_widths: list[int] = Field(
        default_factory=lambda: [4],
        description="Bit widths to sweep",
    )
    group_sizes: list[int] = Field(
        default_factory=lambda: [128],
        description="Group sizes to sweep",
    )

    # Evaluation
    eval_datasets: list[str] = Field(
        default_factory=lambda: ["wikitext2"],
        description="Perplexity eval datasets",
    )
    lm_eval_suite: str | None = Field(
        None,
        description="lm-eval suite to run (None to skip)",
    )

    # Calibration
    calib_dataset: str = "wikitext2"
    calib_size: int = 128
    calib_seq_length: int = 2048

    # Seeds
    seeds: list[int] = Field(
        default_factory=lambda: [42],
        description="Seeds for multi-seed runs",
    )

    # Hardware
    device: str = "cuda"
    hardware_profile: str = "default"

    # Experiment grouping
    group_name: str | None = None
    tags: list[str] = Field(default_factory=list)

    # Limits
    dry_run: bool = False

    @property
    def total_experiments(self) -> int:
        return (
            len(self.models)
            * len(self.methods)
            * len(self.bit_widths)
            * len(self.group_sizes)
            * len(self.seeds)
        )


@dataclass
class MatrixResult:
    """Aggregated result of a full matrix run."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


def run_matrix(
    config: MatrixConfig,
    db_url: str | None = None,
    wandb_project: str = "llm-quant-lab",
    enable_wandb: bool = True,
) -> MatrixResult:
    """Execute a full experiment matrix.

    Args:
        config: Matrix configuration.
        db_url: Database URL.
        wandb_project: W&B project name.
        enable_wandb: Whether to log to W&B.

    Returns:
        MatrixResult with aggregated outcomes.
    """
    from ..tracking.sync_manager import SyncManager
    from ..utils.seeds import set_deterministic_seeds

    result = MatrixResult(total=config.total_experiments)

    logger.info(
        f"Experiment matrix: {config.total_experiments} total experiments "
        f"({len(config.models)} models x {len(config.methods)} methods x "
        f"{len(config.bit_widths)} bit widths x {len(config.group_sizes)} "
        f"group sizes x {len(config.seeds)} seeds)"
    )

    if config.dry_run:
        logger.info("DRY RUN - listing experiments without executing")
        for model, method, bw, gs, seed in itertools.product(
            config.models,
            config.methods,
            config.bit_widths,
            config.group_sizes,
            config.seeds,
        ):
            logger.info(f"  {method} | {model} | {bw}b | g{gs} | seed={seed}")
        return result

    sync = SyncManager(
        db_url=db_url,
        wandb_project=wandb_project,
        enable_wandb=enable_wandb,
    )

    for model, method, bw, gs, seed in itertools.product(
        config.models,
        config.methods,
        config.bit_widths,
        config.group_sizes,
        config.seeds,
    ):
        exp_tags = list(config.tags) + [method, f"{bw}bit", f"g{gs}", f"seed{seed}"]
        exp_config = {
            "model_path": model,
            "method": method,
            "bit_width": bw,
            "group_size": gs,
            "calib_dataset": config.calib_dataset,
            "calib_size": config.calib_size,
            "calib_seq_length": config.calib_seq_length,
            "device": config.device,
            "seed": seed,
        }

        logger.info(f"Running: {method} | {model} | {bw}b | g{gs} | seed={seed}")

        try:
            # Set seeds
            set_deterministic_seeds(seed, deterministic_algorithms=False)

            # Start unified run
            run = sync.start_run(
                model_name=model,
                method=method,
                bit_width=bw,
                config=exp_config,
                group_size=gs,
                tags=exp_tags,
                wandb_group=config.group_name,
            )

            # Run quantization + evaluation using the existing runner
            from .runner import ExperimentConfig, run_experiment

            exp_cfg = ExperimentConfig(
                model_path=model,
                quant_methods=[method],
                bit_width=bw,
                per_channel=True,
                group_size=gs,
                calib_dataset=config.calib_dataset,
                calib_size=config.calib_size,
                calib_seq_length=config.calib_seq_length,
                eval_datasets=config.eval_datasets,
                name=run.run_id,
                tags=exp_tags,
                device=config.device,
                hardware_profile=config.hardware_profile,
            )

            exp_result = run_experiment(exp_cfg, db_url)

            # Sync summary metrics
            metrics_dict: dict[str, float] = {}
            for m_key, m_val in exp_result.method_results.items():
                if m_val.get("status") == "completed":
                    metrics_dict[f"{m_key}_duration_s"] = m_val.get("duration_seconds", 0)

            sync.finish_run(run, final_metrics=metrics_dict, status=exp_result.status)

            result.completed += 1
            result.results.append(
                {
                    "model": model,
                    "method": method,
                    "bit_width": bw,
                    "group_size": gs,
                    "seed": seed,
                    "status": exp_result.status,
                    "run_id": run.run_id,
                }
            )

        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            result.failed += 1
            result.errors.append(
                {
                    "model": model,
                    "method": method,
                    "bit_width": bw,
                    "group_size": gs,
                    "seed": seed,
                    "error": str(e),
                }
            )

    logger.info(
        f"Matrix complete: {result.completed} completed, "
        f"{result.failed} failed out of {result.total}"
    )
    return result
