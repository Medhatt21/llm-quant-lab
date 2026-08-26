"""Database models and logging utilities."""

from .models import (
    Base,
    CalibrationRecord,
    EnvironmentSnapshot,
    Experiment,
    ExperimentGroup,
    HardwareStat,
    KnowledgeEdge,
    KnowledgeNode,
    LayerMetric,
    Metric,
    PaperNote,
    QuantConfig,
    ScientistReport,
    WandbSyncLog,
    get_engine,
    get_session,
)
from .logging import (
    get_experiment_with_details,
    get_experiments_by_method,
    get_experiments_by_model,
    get_metrics_comparison,
    log_experiment,
    log_hardware_stats,
    log_layer_metrics,
    log_layer_metrics_batch,
    log_metrics,
    log_metrics_batch,
    log_quant_config,
    log_scientist_report,
    update_experiment_status,
    update_quant_config_status,
)

__all__ = [
    # Models
    "Base",
    "CalibrationRecord",
    "EnvironmentSnapshot",
    "Experiment",
    "ExperimentGroup",
    "HardwareStat",
    "KnowledgeEdge",
    "KnowledgeNode",
    "LayerMetric",
    "Metric",
    "PaperNote",
    "QuantConfig",
    "ScientistReport",
    "WandbSyncLog",
    # Session management
    "get_engine",
    "get_session",
    # Logging functions
    "log_experiment",
    "log_quant_config",
    "log_metrics",
    "log_metrics_batch",
    "log_hardware_stats",
    "log_layer_metrics",
    "log_layer_metrics_batch",
    "log_scientist_report",
    # Update functions
    "update_experiment_status",
    "update_quant_config_status",
    # Query functions
    "get_experiment_with_details",
    "get_experiments_by_model",
    "get_experiments_by_method",
    "get_metrics_comparison",
]
