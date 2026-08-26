"""Weights & Biases experiment tracking integration.

This module provides a **legacy-compatible** tracking interface that delegates
to the :class:`SyncManager` for all write paths.  The SyncManager enforces
the unified storage architecture:

- **Postgres** owns structured summaries, configs, environment snapshots.
- **W&B** owns time-series, histograms, artifacts, raw logs.

Existing call-sites that use ``WandbTracker`` or ``create_tracker()`` will
continue to work, but all actual logging now goes through SyncManager –
there is **no more independent dual-write**.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch

from .sync_manager import SyncManager, UnifiedRun, hash_config, generate_run_id

if TYPE_CHECKING:
    from transformers import PreTrainedModel

logger = logging.getLogger(__name__)


# ============================================================================
# W&B Availability Check
# ============================================================================

try:
    import wandb
    from wandb.sdk.wandb_run import Run as WandbRun

    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    WandbRun = None  # type: ignore[assignment, misc]
    logger.warning("wandb not available. Install with: pip install wandb")


# ============================================================================
# Tracker Configuration
# ============================================================================


@dataclass
class TrackerConfig:
    """Configuration for experiment tracking."""

    # W&B settings
    wandb_project: str = "llm-quant-lab"
    wandb_entity: str | None = None
    wandb_tags: list[str] = field(default_factory=list)
    wandb_notes: str | None = None
    wandb_group: str | None = None

    # PostgreSQL settings
    db_url: str | None = None
    log_to_db: bool = True

    # Logging settings
    log_layer_stats: bool = True
    log_histograms: bool = False
    log_model_checkpoints: bool = False
    checkpoint_interval: int = 1

    # Paper reproduction
    paper_id: str | None = None
    reproduction_mode: bool = False
    expected_results: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Main Tracker Class (delegates to SyncManager)
# ============================================================================


class WandbTracker:
    """Legacy-compatible experiment tracker.

    All write operations are **delegated** to :class:`SyncManager` so that
    Postgres receives structured summaries and W&B receives time-series data
    via a single unified path.  No independent dual-writing occurs.
    """

    def __init__(
        self,
        config: TrackerConfig | None = None,
        experiment_name: str | None = None,
        model_name: str | None = None,
    ):
        self.config = config or TrackerConfig()
        self.experiment_name = experiment_name
        self.model_name = model_name

        # Underlying SyncManager
        self._sync: SyncManager | None = None
        self._unified_run: UnifiedRun | None = None

        # Legacy convenience attributes
        self._run: WandbRun | None = None
        self._db_experiment_id: int | None = None
        self._start_time: float | None = None
        self._step = 0

        # Metrics accumulator (for summary computation)
        self._accumulated_metrics: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        run_config: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> "WandbTracker":
        """Start tracking by creating a unified run via SyncManager."""
        self._start_time = time.time()

        # Build the SyncManager
        db_url = self.config.db_url or os.getenv("DATABASE_URL")
        self._sync = SyncManager(
            db_url=db_url,
            wandb_project=self.config.wandb_project,
            wandb_entity=self.config.wandb_entity,
            enable_wandb=WANDB_AVAILABLE,
        )

        # Derive method/bit-width from run_config when available
        cfg = run_config or {}
        method = cfg.get("quant/method", cfg.get("method", "unknown"))
        bit_width = cfg.get("quant/bit_width", cfg.get("bit_width", 16))
        group_size = cfg.get("quant/group_size", cfg.get("group_size"))

        tags = list(self.config.wandb_tags)
        if self.config.reproduction_mode:
            tags.append("paper-reproduction")
        if self.config.paper_id:
            tags.append(f"paper:{self.config.paper_id}")

        # Start unified run (creates Postgres record + W&B run, links them)
        try:
            self._unified_run = self._sync.start_run(
                model_name=self.model_name or "unknown",
                method=str(method),
                bit_width=int(bit_width),
                config=cfg,
                group_size=int(group_size) if group_size else None,
                name=self.experiment_name,
                notes=self.config.wandb_notes,
                tags=tags,
                wandb_tags=tags,
                wandb_group=self.config.wandb_group,
            )

            # Expose convenience handles
            self._run = self._unified_run.wandb_run
            self._db_experiment_id = self._unified_run.pg_experiment_id

            logger.info(
                f"WandbTracker started via SyncManager: "
                f"pg_id={self._db_experiment_id}, "
                f"wandb_id={self._unified_run.wandb_run_id or 'disabled'}"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to start experiment tracking: {e}. "
                f"Cannot proceed without a tracking session."
            ) from e

        return self

    # ------------------------------------------------------------------
    # Metrics logging  (time-series -> W&B, summary accumulation -> Postgres)
    # ------------------------------------------------------------------

    def log(self, metrics: dict[str, Any], step: int | None = None) -> None:
        """Log per-step metrics through SyncManager."""
        if step is None:
            step = self._step
            self._step += 1

        # Add timing metadata
        metrics["_timestamp"] = time.time()
        metrics["_elapsed_seconds"] = time.time() - (self._start_time or time.time())

        # Delegate to SyncManager (time-series -> W&B only)
        if self._sync and self._unified_run:
            self._sync.log_step(self._unified_run, metrics, step=step)

        # Accumulate for summary (written to Postgres on finish)
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and not key.startswith("_"):
                if key not in self._accumulated_metrics:
                    self._accumulated_metrics[key] = []
                self._accumulated_metrics[key].append(value)

    def log_config(self, config: dict[str, Any]) -> None:
        """Log configuration parameters to W&B."""
        if self._run is not None:
            self._run.config.update(config)

    def log_quantization_config(
        self,
        method: str,
        bit_width: int,
        group_size: int | None = None,
        symmetric: bool = True,
        activation_quant: bool = False,
        activation_bits: int | None = None,
        calib_dataset: str | None = None,
        calib_samples: int | None = None,
        **extra_config,
    ) -> None:
        """Log quantization config via SyncManager to Postgres."""
        config = {
            "quant/method": method,
            "quant/bit_width": bit_width,
            "quant/group_size": group_size,
            "quant/symmetric": symmetric,
            "quant/activation_quant": activation_quant,
            "quant/activation_bits": activation_bits,
            "calib/dataset": calib_dataset,
            "calib/samples": calib_samples,
            **{f"quant/{k}": v for k, v in extra_config.items()},
        }

        # W&B config update
        self.log_config(config)

        # Postgres via SyncManager
        if self._sync and self._unified_run:
            try:
                self._sync.log_quant_config(
                    self._unified_run,
                    method_name=method,
                    bit_width=bit_width,
                    per_channel=True,
                    group_size=group_size,
                    activation_quant=activation_quant,
                    activation_bits=activation_bits,
                    config_json=config,
                    calib_dataset=calib_dataset,
                    calib_size=calib_samples,
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to log quantization config: {e}. "
                    f"Experiment metadata will be incomplete."
                ) from e

    def log_perplexity(
        self,
        dataset: str,
        perplexity: float,
        loss: float | None = None,
        split: str = "test",
        prefix: str = "",
    ) -> None:
        """Log perplexity: time-series -> W&B, summary value accumulated for Postgres."""
        metrics = {
            f"{prefix}eval/{dataset}/perplexity": perplexity,
        }
        if loss is not None:
            metrics[f"{prefix}eval/{dataset}/loss"] = loss

        self.log(metrics)

        # Also track as summary metric so it goes to Postgres on finish
        if self._unified_run:
            self._unified_run._summary_metrics[f"perplexity/{dataset}"] = perplexity
            if loss is not None:
                self._unified_run._summary_metrics[f"loss/{dataset}"] = loss

    def log_layer_stats(
        self,
        layer_idx: int,
        layer_name: str,
        stats: dict[str, float],
        stat_type: str = "weight",
    ) -> None:
        """Log per-layer statistics: time-series -> W&B."""
        if not self.config.log_layer_stats:
            return

        metrics = {
            f"layer/{layer_idx}/{stat_type}/{k}": v
            for k, v in stats.items()
        }
        self.log(metrics)

    def log_hardware_stats(
        self,
        latency_ms: dict[str, float] | None = None,
        throughput: float | None = None,
        memory_gb: dict[str, float] | None = None,
        model_size_mb: float | None = None,
        compression_ratio: float | None = None,
    ) -> None:
        """Log hardware stats: W&B time-series + Postgres structured summary."""
        metrics: dict[str, Any] = {}

        if latency_ms:
            for k, v in latency_ms.items():
                metrics[f"hardware/latency_{k}_ms"] = v
        if throughput is not None:
            metrics["hardware/tokens_per_second"] = throughput
        if memory_gb:
            for k, v in memory_gb.items():
                metrics[f"hardware/memory_{k}_gb"] = v
        if model_size_mb is not None:
            metrics["hardware/model_size_mb"] = model_size_mb
        if compression_ratio is not None:
            metrics["hardware/compression_ratio"] = compression_ratio

        # Time-series -> W&B
        self.log(metrics)

        # Structured summary -> Postgres via SyncManager
        if self._sync and self._unified_run:
            try:
                self._sync.log_hardware(
                    self._unified_run,
                    latency_mean_ms=latency_ms.get("mean") if latency_ms else None,
                    latency_p50_ms=latency_ms.get("p50") if latency_ms else None,
                    latency_p95_ms=latency_ms.get("p95") if latency_ms else None,
                    latency_p99_ms=latency_ms.get("p99") if latency_ms else None,
                    throughput_tokens_per_sec=throughput,
                    memory_allocated_gb=memory_gb.get("allocated") if memory_gb else None,
                    memory_reserved_gb=memory_gb.get("reserved") if memory_gb else None,
                    memory_peak_gb=memory_gb.get("peak") if memory_gb else None,
                    model_size_mb=model_size_mb,
                    compression_ratio=compression_ratio,
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to log hardware stats: {e}."
                ) from e

    def log_histogram(
        self,
        name: str,
        values: torch.Tensor | list,
        bins: int = 64,
    ) -> None:
        """Log a histogram (W&B only – visualization data)."""
        if not self.config.log_histograms:
            return

        if self._run is not None and WANDB_AVAILABLE:
            if isinstance(values, torch.Tensor):
                values = values.detach().cpu().numpy().flatten()
            self._run.log({name: wandb.Histogram(values, num_bins=bins)})

    def log_weight_distribution(
        self,
        model: "PreTrainedModel",
        layer_filter: str | None = None,
    ) -> None:
        """Log weight distributions for all layers (W&B only)."""
        if not self.config.log_histograms:
            return

        for name, param in model.named_parameters():
            if layer_filter and layer_filter not in name:
                continue
            if param.requires_grad:
                self.log_histogram(f"weights/{name}", param.data)

    def log_artifact(
        self,
        name: str,
        artifact_type: str,
        path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an artifact (W&B only – artifact storage)."""
        if self._run is None or not WANDB_AVAILABLE:
            return

        artifact = wandb.Artifact(name=name, type=artifact_type, metadata=metadata)

        path = Path(path)
        if path.is_dir():
            artifact.add_dir(str(path))
        else:
            artifact.add_file(str(path))

        self._run.log_artifact(artifact)
        logger.info(f"Logged artifact: {name} ({artifact_type})")

    def log_table(
        self,
        name: str,
        columns: list[str],
        data: list[list[Any]],
    ) -> None:
        """Log a table (W&B only – interactive tables)."""
        if self._run is None or not WANDB_AVAILABLE:
            return

        table = wandb.Table(columns=columns, data=data)
        self._run.log({name: table})

    def log_comparison_table(
        self,
        results: list[dict[str, Any]],
        metrics: list[str],
        group_by: str = "method",
    ) -> None:
        """Log a comparison table of results (W&B only)."""
        columns = [group_by] + metrics
        data = []

        for r in results:
            row = [r.get(group_by, "unknown")]
            for m in metrics:
                row.append(r.get(m, None))
            data.append(row)

        self.log_table("comparison", columns, data)

    def compare_with_paper(
        self,
        metric_name: str,
        our_value: float,
        paper_value: float,
        tolerance: float = 0.1,
    ) -> dict[str, Any]:
        """Compare our result with paper's reported value."""
        diff = our_value - paper_value
        rel_diff = abs(diff) / paper_value if paper_value != 0 else float("inf")
        within_tolerance = rel_diff <= tolerance

        result = {
            "metric": metric_name,
            "our_value": our_value,
            "paper_value": paper_value,
            "absolute_diff": diff,
            "relative_diff_pct": rel_diff * 100,
            "within_tolerance": within_tolerance,
            "tolerance_pct": tolerance * 100,
        }

        # Log comparison
        metrics = {
            f"paper_comparison/{metric_name}/our_value": our_value,
            f"paper_comparison/{metric_name}/paper_value": paper_value,
            f"paper_comparison/{metric_name}/diff": diff,
            f"paper_comparison/{metric_name}/rel_diff_pct": rel_diff * 100,
        }
        self.log(metrics)

        if within_tolerance:
            logger.info(
                f"✓ {metric_name}: {our_value:.4f} vs paper {paper_value:.4f} "
                f"(diff: {rel_diff*100:.1f}%, within {tolerance*100:.0f}% tolerance)"
            )
        else:
            logger.warning(
                f"✗ {metric_name}: {our_value:.4f} vs paper {paper_value:.4f} "
                f"(diff: {rel_diff*100:.1f}%, exceeds {tolerance*100:.0f}% tolerance)"
            )

        return result

    # ------------------------------------------------------------------
    # Finish
    # ------------------------------------------------------------------

    def finish(self, status: str = "completed") -> dict[str, Any]:
        """Finish tracking via SyncManager."""
        elapsed = time.time() - (self._start_time or time.time())

        # Compute summary statistics from accumulated metrics
        summary: dict[str, Any] = {
            "status": status,
            "elapsed_seconds": elapsed,
        }

        for key, values in self._accumulated_metrics.items():
            if values:
                summary[f"{key}/mean"] = sum(values) / len(values)
                summary[f"{key}/final"] = values[-1]

        # Delegate finalisation to SyncManager
        if self._sync and self._unified_run:
            final_metrics = {
                k: v for k, v in summary.items()
                if isinstance(v, (int, float))
            }
            try:
                result = self._sync.finish_run(
                    self._unified_run,
                    final_metrics=final_metrics,
                    status=status,
                )
                summary.update(result)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to finalize experiment run: {e}. "
                    f"Data may be inconsistent."
                ) from e
        elif self._run is not None:
            # Last-resort cleanup: finish W&B run directly if SyncManager wasn't available
            try:
                for k, v in summary.items():
                    if isinstance(v, (int, float, str)):
                        self._run.summary[k] = v
                self._run.finish()
            except Exception as e:
                logger.error(f"W&B finish failed (last-resort cleanup): {e}")

        return summary

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def run(self) -> WandbRun | None:
        """Get the W&B run object."""
        return self._run

    @property
    def experiment_id(self) -> int | None:
        """Get the DB experiment ID."""
        return self._db_experiment_id

    @property
    def unified_run(self) -> UnifiedRun | None:
        """Get the underlying UnifiedRun handle."""
        return self._unified_run


# ============================================================================
# Convenience Functions
# ============================================================================


def create_tracker(
    experiment_name: str,
    model_name: str,
    project: str = "llm-quant-lab",
    tags: list[str] | None = None,
    paper_id: str | None = None,
    log_to_db: bool = True,
) -> WandbTracker:
    """Create a new tracker (backed by SyncManager).

    Args:
        experiment_name: Name for the experiment
        model_name: Model being quantized
        project: W&B project name
        tags: Tags for the experiment
        paper_id: Paper ID if reproducing
        log_to_db: Whether to log to PostgreSQL

    Returns:
        WandbTracker instance (call ``.start()`` to begin tracking)
    """
    config = TrackerConfig(
        wandb_project=project,
        wandb_tags=tags or [],
        paper_id=paper_id,
        reproduction_mode=paper_id is not None,
        log_to_db=log_to_db,
        db_url=os.getenv("DATABASE_URL"),
    )

    tracker = WandbTracker(
        config=config,
        experiment_name=experiment_name,
        model_name=model_name,
    )

    return tracker


# Alias for backward compatibility
ExperimentTracker = WandbTracker


def log_quantization_run(
    tracker: WandbTracker,
    method: str,
    bit_width: int,
    perplexity_results: dict[str, float],
    hardware_stats: dict[str, Any] | None = None,
    **config,
) -> None:
    """Log a complete quantization run.

    Args:
        tracker: Tracker instance
        method: Quantization method
        bit_width: Bit width
        perplexity_results: Dict of dataset -> perplexity
        hardware_stats: Optional hardware stats
        **config: Additional config
    """
    tracker.log_quantization_config(method=method, bit_width=bit_width, **config)

    for dataset, ppl in perplexity_results.items():
        tracker.log_perplexity(dataset=dataset, perplexity=ppl)

    if hardware_stats:
        tracker.log_hardware_stats(**hardware_stats)


def log_evaluation_metrics(
    tracker: WandbTracker,
    dataset: str,
    metrics: dict[str, float],
    prefix: str = "",
) -> None:
    """Log evaluation metrics.

    Args:
        tracker: Tracker instance
        dataset: Dataset name
        metrics: Metrics dict
        prefix: Metric prefix
    """
    for name, value in metrics.items():
        if name == "perplexity":
            tracker.log_perplexity(dataset=dataset, perplexity=value, prefix=prefix)
        else:
            tracker.log({f"{prefix}eval/{dataset}/{name}": value})


def log_hardware_stats(
    tracker: WandbTracker,
    latency_results: dict[str, float],
    memory_results: dict[str, float],
    throughput: float | None = None,
) -> None:
    """Log hardware statistics.

    Args:
        tracker: Tracker instance
        latency_results: Latency measurements
        memory_results: Memory measurements
        throughput: Throughput in tokens/sec
    """
    tracker.log_hardware_stats(
        latency_ms=latency_results,
        memory_gb=memory_results,
        throughput=throughput,
    )


def log_layer_analysis(
    tracker: WandbTracker,
    layer_stats: dict[str, dict[str, float]],
    stat_type: str = "weight",
) -> None:
    """Log layer-wise analysis.

    Args:
        tracker: Tracker instance
        layer_stats: Dict of layer_name -> stats
        stat_type: Type of stats
    """
    for idx, (name, stats) in enumerate(layer_stats.items()):
        tracker.log_layer_stats(
            layer_idx=idx,
            layer_name=name,
            stats=stats,
            stat_type=stat_type,
        )
