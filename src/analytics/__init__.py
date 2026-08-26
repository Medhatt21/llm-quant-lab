"""Analytics, plotting, and report generation."""

from .plots import (
    plot_accuracy_vs_bitwidth,
    plot_pareto_front,
    plot_layer_stats,
)
from .latex_export import (
    export_ablation_table,
    export_comparison_table,
    export_metrics_table,
    export_metrics_table_enhanced,
)
from .pareto import ParetoPoint, compute_pareto_frontier, compute_pareto_from_db
from .paper_plots import (
    plot_ablation_heatmap,
    plot_layer_error_distribution,
    plot_method_comparison_bar,
    plot_pareto_frontier,
    plot_scaling_curve,
)
from .cross_hardware import HardwareComparison, compare_hardware_results, plot_cross_hardware
from .reports import generate_markdown_report

__all__ = [
    # Existing plots
    "plot_accuracy_vs_bitwidth",
    "plot_pareto_front",
    "plot_layer_stats",
    # LaTeX export
    "export_metrics_table",
    "export_metrics_table_enhanced",
    "export_comparison_table",
    "export_ablation_table",
    # Pareto
    "ParetoPoint",
    "compute_pareto_frontier",
    "compute_pareto_from_db",
    # Paper-quality plots
    "plot_pareto_frontier",
    "plot_scaling_curve",
    "plot_ablation_heatmap",
    "plot_method_comparison_bar",
    "plot_layer_error_distribution",
    # Cross-hardware comparison
    "HardwareComparison",
    "compare_hardware_results",
    "plot_cross_hardware",
    # Reports
    "generate_markdown_report",
]
