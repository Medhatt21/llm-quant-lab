"""Publication-quality plots in NeurIPS/ICML style.

Generates:
- Pareto frontier plots (accuracy vs latency, accuracy vs memory)
- Scaling curves (degradation vs model size)
- Ablation heatmaps (method x bit_width -> metric)
- Layer-wise error distributions
- Method comparison bar charts

All plots are saved as both PDF and PNG for paper inclusion.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

# NeurIPS / ICML style defaults
PAPER_RC = {
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.figsize": (5.5, 3.5),
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "lines.linewidth": 1.5,
    "lines.markersize": 6,
}

# Colour palette (colour-blind friendly)
METHOD_COLOURS = {
    "gptq": "#1b9e77",
    "awq": "#d95f02",
    "smoothquant": "#7570b3",
    "rtn": "#e7298a",
    "hqq": "#66a61e",
    "quarot": "#e6ab02",
    "spqr": "#a6761d",
    "owq": "#666666",
    "omniquant": "#a6cee3",
    "dgq": "#1f78b4",
}


def _setup_style() -> None:
    matplotlib.rcParams.update(PAPER_RC)


def _save_fig(fig: plt.Figure, path: Path, formats: list[str] | None = None) -> list[Path]:
    """Save figure in multiple formats."""
    formats = formats or ["pdf", "png"]
    saved: list[Path] = []
    for fmt in formats:
        out = path.with_suffix(f".{fmt}")
        fig.savefig(out)
        saved.append(out)
        logger.info(f"Saved plot: {out}")
    plt.close(fig)
    return saved


# ============================================================================
# Plot functions
# ============================================================================


def plot_pareto_frontier(
    points: list[dict[str, Any]],
    x_key: str = "latency",
    y_key: str = "accuracy",
    x_label: str = "Latency (ms)",
    y_label: str = "Perplexity",
    title: str = "Accuracy vs Latency Pareto Frontier",
    output_path: Path = Path("reports/pareto_frontier"),
) -> list[Path]:
    """Plot a Pareto frontier with method colour coding.

    Args:
        points: List of dicts with keys: method, {x_key}, {y_key}, is_pareto_optimal.
        x_key: Key for X axis values.
        y_key: Key for Y axis values.
        output_path: Base path (without extension).

    Returns:
        List of saved file paths.
    """
    _setup_style()
    fig, ax = plt.subplots()

    methods = list({p["method"] for p in points})

    for method in methods:
        mp = [p for p in points if p["method"] == method]
        xs = [p[x_key] for p in mp]
        ys = [p[y_key] for p in mp]
        colour = METHOD_COLOURS.get(method, "#333333")
        marker = "o" if any(p.get("is_pareto_optimal") for p in mp) else "x"
        ax.scatter(xs, ys, label=method, color=colour, marker=marker, alpha=0.8, zorder=3)

    # Draw Pareto frontier line
    pareto = [p for p in points if p.get("is_pareto_optimal")]
    if pareto:
        pareto.sort(key=lambda p: p[x_key])
        ax.plot(
            [p[x_key] for p in pareto],
            [p[y_key] for p in pareto],
            "k--", alpha=0.5, linewidth=1, zorder=2, label="Pareto frontier",
        )

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.legend(loc="best", framealpha=0.9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _save_fig(fig, output_path)


def plot_scaling_curve(
    data: list[dict[str, Any]],
    x_key: str = "model_params_b",
    y_key: str = "perplexity_delta",
    group_key: str = "method",
    x_label: str = "Model Parameters (B)",
    y_label: str = "Perplexity Degradation (vs FP16)",
    title: str = "Quantisation Degradation vs Model Scale",
    output_path: Path = Path("reports/scaling_curve"),
) -> list[Path]:
    """Plot perplexity degradation vs model size per method."""
    _setup_style()
    fig, ax = plt.subplots()

    methods = list({d[group_key] for d in data})
    for method in methods:
        md = [d for d in data if d[group_key] == method]
        md.sort(key=lambda d: d[x_key])
        xs = [d[x_key] for d in md]
        ys = [d[y_key] for d in md]
        colour = METHOD_COLOURS.get(method, "#333333")
        ax.plot(xs, ys, "o-", label=method, color=colour, alpha=0.8)

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.legend(loc="best", framealpha=0.9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _save_fig(fig, output_path)


def plot_ablation_heatmap(
    data: dict[tuple[str, int], float],
    row_labels: list[str],
    col_labels: list[int],
    metric_name: str = "Perplexity",
    title: str = "Ablation: Method x Bit Width",
    output_path: Path = Path("reports/ablation_heatmap"),
    bold_best: bool = True,
) -> list[Path]:
    """Plot a heatmap of method x bit_width -> metric.

    Args:
        data: Dict mapping (method, bit_width) -> metric value.
        row_labels: Method names (rows).
        col_labels: Bit widths (columns).
        bold_best: Whether to bold the best value per column.
    """
    _setup_style()

    matrix = np.zeros((len(row_labels), len(col_labels)))
    for i, method in enumerate(row_labels):
        for j, bw in enumerate(col_labels):
            matrix[i, j] = data.get((method, bw), float("nan"))

    fig, ax = plt.subplots(figsize=(max(4, len(col_labels) * 1.2), max(3, len(row_labels) * 0.6)))
    im = ax.imshow(matrix, cmap="RdYlGn_r", aspect="auto")

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels([f"{b}-bit" for b in col_labels])
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels)

    # Annotate cells
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = matrix[i, j]
            if not np.isnan(val):
                # Bold the best (lowest perplexity) per column
                col_vals = matrix[:, j]
                is_best = val == np.nanmin(col_vals) and bold_best
                weight = "bold" if is_best else "normal"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=8, fontweight=weight)

    ax.set_title(title)
    fig.colorbar(im, ax=ax, label=metric_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _save_fig(fig, output_path)


def plot_method_comparison_bar(
    data: list[dict[str, Any]],
    metric_key: str = "perplexity",
    error_key: str | None = "perplexity_std",
    group_key: str = "method",
    title: str = "Method Comparison",
    y_label: str = "Perplexity",
    output_path: Path = Path("reports/method_comparison"),
) -> list[Path]:
    """Bar chart comparing methods with error bars."""
    _setup_style()
    fig, ax = plt.subplots()

    methods = [d[group_key] for d in data]
    values = [d[metric_key] for d in data]
    errors = [d.get(error_key, 0) for d in data] if error_key else None
    colours = [METHOD_COLOURS.get(m, "#333333") for m in methods]

    bars = ax.bar(methods, values, yerr=errors, color=colours, alpha=0.8,
                  capsize=3, edgecolor="white", linewidth=0.5)

    ax.set_ylabel(y_label)
    ax.set_title(title)
    plt.xticks(rotation=45, ha="right")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _save_fig(fig, output_path)


def plot_layer_error_distribution(
    layer_errors: dict[str, list[float]],
    title: str = "Layer-wise Quantisation Error",
    y_label: str = "MSE",
    output_path: Path = Path("reports/layer_errors"),
) -> list[Path]:
    """Box plot of quantisation error per layer group."""
    _setup_style()
    fig, ax = plt.subplots(figsize=(8, 4))

    labels = list(layer_errors.keys())
    data = [layer_errors[k] for k in labels]

    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#7570b3")
        patch.set_alpha(0.6)

    ax.set_ylabel(y_label)
    ax.set_title(title)
    plt.xticks(rotation=45, ha="right")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _save_fig(fig, output_path)
