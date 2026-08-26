"""Experiment tracking with unified Postgres / Weights & Biases storage.

Architecture
------------
The **SyncManager** is the single source of truth for experiment tracking.
It enforces clear ownership between storage systems:

- **Postgres**: Experiment definitions, configs, config hashes, summary
  metrics, environment snapshots, calibration records, scientist reports,
  experiment groups, W&B cross-references.
- **W&B**: Full metric time-series, weight/activation histograms,
  interactive tables, model artifacts/checkpoints, raw logs.

The ``WandbTracker`` class is maintained for backward compatibility but
delegates **all** write operations to ``SyncManager`` internally – there
is no independent dual-write path.

Preferred usage::

    from src.tracking import SyncManager

    sync = SyncManager(db_url="postgresql://...", wandb_project="llm-quant-lab")
    run = sync.start_run(model_name="facebook/opt-125m", method="gptq", ...)
    sync.log_step(run, {"loss": 1.23}, step=0)
    sync.finish_run(run, final_metrics={"perplexity": 15.4})
"""

from .sync_manager import SyncManager, UnifiedRun, hash_config, generate_run_id

from .wandb_tracker import (
    WandbTracker,
    ExperimentTracker,
    TrackerConfig,
    create_tracker,
    log_quantization_run,
    log_evaluation_metrics,
    log_hardware_stats,
    log_layer_analysis,
)

from .paper_reproduction import (
    PaperReproductionTracker,
    GPTQReproduction,
    SmoothQuantReproduction,
    GPTQ_PAPER,
    SMOOTHQUANT_PAPER,
    compare_with_paper_results,
)

from .advanced_reporting import (
    AdvancedReportGenerator,
    QuantizationResult,
    ExperimentReport,
    ReportBuilder,
)

__all__ = [
    # Unified sync manager (preferred API)
    "SyncManager",
    "UnifiedRun",
    "hash_config",
    "generate_run_id",
    # Legacy-compatible tracker (delegates to SyncManager)
    "WandbTracker",
    "ExperimentTracker",
    "TrackerConfig",
    "create_tracker",
    "log_quantization_run",
    "log_evaluation_metrics",
    "log_hardware_stats",
    "log_layer_analysis",
    # Paper reproduction
    "PaperReproductionTracker",
    "GPTQReproduction",
    "SmoothQuantReproduction",
    "GPTQ_PAPER",
    "SMOOTHQUANT_PAPER",
    "compare_with_paper_results",
    # Reporting
    "AdvancedReportGenerator",
    "QuantizationResult",
    "ExperimentReport",
    "ReportBuilder",
]
