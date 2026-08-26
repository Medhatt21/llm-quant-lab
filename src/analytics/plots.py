"""Plotting utilities for experiment analysis.

This module provides functions for generating visualizations
of quantization experiment results.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (10, 6)
plt.rcParams["font.size"] = 12


def plot_accuracy_vs_bitwidth(
    data: list[dict[str, Any]],
    metric: str = "perplexity",
    output_path: str | None = None,
    title: str | None = None,
) -> plt.Figure:
    """Plot accuracy/perplexity vs bit width.
    
    Args:
        data: List of dicts with 'method', 'bit_width', and metric value
        metric: Metric name to plot
        output_path: Optional path to save figure
        title: Optional plot title
        
    Returns:
        Matplotlib figure
    """
    df = pd.DataFrame(data)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot each method
    methods = df["method"].unique()
    colors = sns.color_palette("husl", len(methods))
    
    for method, color in zip(methods, colors):
        method_data = df[df["method"] == method]
        ax.plot(
            method_data["bit_width"],
            method_data[metric],
            marker="o",
            label=method.upper(),
            color=color,
            linewidth=2,
            markersize=8,
        )
    
    ax.set_xlabel("Bit Width", fontsize=14)
    ax.set_ylabel(metric.replace("_", " ").title(), fontsize=14)
    ax.set_title(title or f"{metric.replace('_', ' ').title()} vs Bit Width", fontsize=16)
    ax.legend(title="Method", fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Set x-axis ticks
    ax.set_xticks(sorted(df["bit_width"].unique()))
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    return fig


def plot_pareto_front(
    data: list[dict[str, Any]],
    x_metric: str = "latency_p50",
    y_metric: str = "perplexity",
    output_path: str | None = None,
    title: str | None = None,
    highlight_pareto: bool = True,
) -> plt.Figure:
    """Plot Pareto front of accuracy vs latency/energy.
    
    Args:
        data: List of dicts with method, x_metric, y_metric values
        x_metric: X-axis metric (e.g., latency, energy)
        y_metric: Y-axis metric (e.g., perplexity, accuracy)
        output_path: Optional path to save figure
        title: Optional plot title
        highlight_pareto: Whether to highlight Pareto-optimal points
        
    Returns:
        Matplotlib figure
    """
    df = pd.DataFrame(data)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot all points
    methods = df["method"].unique()
    colors = sns.color_palette("husl", len(methods))
    
    for method, color in zip(methods, colors):
        method_data = df[df["method"] == method]
        ax.scatter(
            method_data[x_metric],
            method_data[y_metric],
            label=method.upper(),
            color=color,
            s=100,
            alpha=0.7,
        )
        
        # Add bit width labels
        for _, row in method_data.iterrows():
            ax.annotate(
                f"{row.get('bit_width', '')}b",
                (row[x_metric], row[y_metric]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
            )
    
    # Find and highlight Pareto front
    if highlight_pareto:
        pareto_points = _find_pareto_front(df[[x_metric, y_metric]].values)
        pareto_df = df.iloc[pareto_points]
        
        # Sort by x for line plot
        pareto_df = pareto_df.sort_values(x_metric)
        
        ax.plot(
            pareto_df[x_metric],
            pareto_df[y_metric],
            "k--",
            linewidth=2,
            label="Pareto Front",
            alpha=0.5,
        )
    
    ax.set_xlabel(x_metric.replace("_", " ").title(), fontsize=14)
    ax.set_ylabel(y_metric.replace("_", " ").title(), fontsize=14)
    ax.set_title(title or f"Pareto Front: {y_metric} vs {x_metric}", fontsize=16)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    return fig


def _find_pareto_front(points: np.ndarray) -> list[int]:
    """Find Pareto-optimal points (minimizing both dimensions).
    
    Args:
        points: Array of shape (n, 2)
        
    Returns:
        Indices of Pareto-optimal points
    """
    pareto_indices = []
    
    for i, point in enumerate(points):
        dominated = False
        for j, other in enumerate(points):
            if i != j:
                # Check if other dominates point (both values smaller)
                if other[0] <= point[0] and other[1] <= point[1]:
                    if other[0] < point[0] or other[1] < point[1]:
                        dominated = True
                        break
        
        if not dominated:
            pareto_indices.append(i)
    
    return pareto_indices


def plot_layer_stats(
    layer_data: list[dict[str, Any]],
    stat_name: str = "weight_norm",
    output_path: str | None = None,
    title: str | None = None,
    show_pre_post: bool = True,
) -> plt.Figure:
    """Plot layer-wise statistics.
    
    Args:
        layer_data: List of dicts with layer_index, stat_name, value, stat_type
        stat_name: Statistic to plot
        output_path: Optional path to save figure
        title: Optional plot title
        show_pre_post: Whether to show pre/post quantization comparison
        
    Returns:
        Matplotlib figure
    """
    df = pd.DataFrame(layer_data)
    df = df[df["stat_name"] == stat_name]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    if show_pre_post and "stat_type" in df.columns:
        # Plot pre and post quantization
        for stat_type, color in [("pre_quant", "blue"), ("post_quant", "red")]:
            type_data = df[df["stat_type"] == stat_type].sort_values("layer_index")
            if not type_data.empty:
                ax.plot(
                    type_data["layer_index"],
                    type_data["value"],
                    marker="o",
                    label=stat_type.replace("_", " ").title(),
                    color=color,
                    alpha=0.7,
                )
    else:
        # Single line plot
        df = df.sort_values("layer_index")
        ax.plot(
            df["layer_index"],
            df["value"],
            marker="o",
            color="blue",
            alpha=0.7,
        )
    
    ax.set_xlabel("Layer Index", fontsize=14)
    ax.set_ylabel(stat_name.replace("_", " ").title(), fontsize=14)
    ax.set_title(title or f"Layer-wise {stat_name.replace('_', ' ').title()}", fontsize=16)
    
    if show_pre_post:
        ax.legend(fontsize=10)
    
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    return fig


def plot_method_comparison(
    data: list[dict[str, Any]],
    metrics: list[str] | None = None,
    output_path: str | None = None,
    title: str | None = None,
) -> plt.Figure:
    """Plot comparison of multiple methods across metrics.
    
    Args:
        data: List of dicts with method and metric values
        metrics: Metrics to compare (default: perplexity, latency_p50)
        output_path: Optional path to save figure
        title: Optional plot title
        
    Returns:
        Matplotlib figure
    """
    metrics = metrics or ["perplexity", "latency_p50"]
    df = pd.DataFrame(data)
    
    # Normalize metrics for comparison
    normalized = df.copy()
    for metric in metrics:
        if metric in normalized.columns:
            max_val = normalized[metric].max()
            if max_val > 0:
                normalized[f"{metric}_norm"] = normalized[metric] / max_val
    
    fig, axes = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 6))
    if len(metrics) == 1:
        axes = [axes]
    
    colors = sns.color_palette("husl", len(df["method"].unique()))
    
    for ax, metric in zip(axes, metrics):
        if metric in df.columns:
            method_values = df.groupby("method")[metric].mean()
            bars = ax.bar(
                range(len(method_values)),
                method_values.values,
                color=colors[:len(method_values)],
            )
            ax.set_xticks(range(len(method_values)))
            ax.set_xticklabels([m.upper() for m in method_values.index], rotation=45)
            ax.set_ylabel(metric.replace("_", " ").title())
            ax.set_title(metric.replace("_", " ").title())
            
            # Add value labels
            for bar, val in zip(bars, method_values.values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{val:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )
    
    fig.suptitle(title or "Method Comparison", fontsize=16)
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    return fig


def plot_outlier_distribution(
    activation_data: list[dict[str, Any]],
    output_path: str | None = None,
    title: str | None = None,
) -> plt.Figure:
    """Plot activation outlier distribution across layers.
    
    Args:
        activation_data: List of dicts with layer info and outlier ratios
        output_path: Optional path to save figure
        title: Optional plot title
        
    Returns:
        Matplotlib figure
    """
    df = pd.DataFrame(activation_data)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot outlier ratios
    if "outlier_ratio_3sigma" in df.columns:
        ax1.bar(
            df["layer_index"],
            df["outlier_ratio_3sigma"] * 100,
            alpha=0.7,
            label="3σ outliers",
        )
    if "outlier_ratio_6sigma" in df.columns:
        ax1.bar(
            df["layer_index"],
            df["outlier_ratio_6sigma"] * 100,
            alpha=0.7,
            label="6σ outliers",
        )
    
    ax1.set_xlabel("Layer Index", fontsize=14)
    ax1.set_ylabel("Outlier Ratio (%)", fontsize=14)
    ax1.set_title("Activation Outlier Ratios by Layer", fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot kurtosis (measure of tail heaviness)
    if "kurtosis" in df.columns:
        ax2.bar(df["layer_index"], df["kurtosis"], alpha=0.7, color="orange")
        ax2.axhline(y=0, color="black", linestyle="--", alpha=0.5)
        ax2.set_xlabel("Layer Index", fontsize=14)
        ax2.set_ylabel("Kurtosis", fontsize=14)
        ax2.set_title("Activation Kurtosis by Layer", fontsize=14)
        ax2.grid(True, alpha=0.3)
    
    fig.suptitle(title or "Activation Distribution Analysis", fontsize=16)
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    return fig


def create_experiment_summary_plot(
    experiment_data: dict[str, Any],
    output_path: str | None = None,
) -> plt.Figure:
    """Create a comprehensive summary plot for an experiment.
    
    Args:
        experiment_data: Full experiment data from database
        output_path: Optional path to save figure
        
    Returns:
        Matplotlib figure
    """
    fig = plt.figure(figsize=(16, 12))
    
    # Create grid
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    
    exp = experiment_data.get("experiment", {})
    metrics = experiment_data.get("metrics", [])
    hardware = experiment_data.get("hardware_stats", [])
    layer_metrics = experiment_data.get("layer_metrics", [])
    
    # Title
    fig.suptitle(
        f"Experiment Summary: {exp.get('model_name', 'Unknown')}",
        fontsize=16,
        fontweight="bold",
    )
    
    # 1. Metrics bar chart
    ax1 = fig.add_subplot(gs[0, 0])
    if metrics:
        metric_df = pd.DataFrame(metrics)
        metric_summary = metric_df.groupby("metric_name")["value"].mean()
        ax1.barh(range(len(metric_summary)), metric_summary.values)
        ax1.set_yticks(range(len(metric_summary)))
        ax1.set_yticklabels(metric_summary.index)
        ax1.set_xlabel("Value")
        ax1.set_title("Evaluation Metrics")
    else:
        ax1.text(0.5, 0.5, "No metrics", ha="center", va="center")
        ax1.set_title("Evaluation Metrics")
    
    # 2. Hardware stats
    ax2 = fig.add_subplot(gs[0, 1])
    if hardware:
        hw = hardware[-1]
        stats = [
            ("Latency P50 (ms)", hw.get("latency_p50", 0)),
            ("Latency P95 (ms)", hw.get("latency_p95", 0)),
            ("Tokens/sec", hw.get("tokens_per_second", 0)),
            ("Memory (GB)", hw.get("memory_allocated", 0)),
        ]
        labels, values = zip(*stats)
        ax2.barh(range(len(labels)), values)
        ax2.set_yticks(range(len(labels)))
        ax2.set_yticklabels(labels)
        ax2.set_xlabel("Value")
        ax2.set_title("Hardware Performance")
    else:
        ax2.text(0.5, 0.5, "No hardware stats", ha="center", va="center")
        ax2.set_title("Hardware Performance")
    
    # 3. Layer-wise weight norms
    ax3 = fig.add_subplot(gs[1, :])
    if layer_metrics:
        lm_df = pd.DataFrame(layer_metrics)
        norm_data = lm_df[lm_df["stat_name"] == "norm_l2"]
        if not norm_data.empty:
            for stat_type in norm_data["stat_type"].unique():
                type_data = norm_data[norm_data["stat_type"] == stat_type].sort_values("layer_index")
                ax3.plot(type_data["layer_index"], type_data["value"], label=stat_type, marker=".")
            ax3.set_xlabel("Layer Index")
            ax3.set_ylabel("L2 Norm")
            ax3.set_title("Layer-wise Weight Norms")
            ax3.legend()
        else:
            ax3.text(0.5, 0.5, "No layer metrics", ha="center", va="center")
    else:
        ax3.text(0.5, 0.5, "No layer metrics", ha="center", va="center")
    ax3.set_title("Layer-wise Statistics")
    
    # 4. Experiment info text
    ax4 = fig.add_subplot(gs[2, :])
    ax4.axis("off")
    
    info_text = f"""
    Model: {exp.get('model_name', 'Unknown')}
    Base Precision: {exp.get('base_precision', 'Unknown')}
    Hardware: {exp.get('gpu_type', 'Unknown')}
    Status: {exp.get('status', 'Unknown')}
    Created: {exp.get('created_at', 'Unknown')}
    """
    
    quant_configs = experiment_data.get("quant_configs", [])
    if quant_configs:
        info_text += "\n    Quantization Methods:\n"
        for qc in quant_configs:
            info_text += f"      - {qc['method_name']} @ {qc['bit_width']}-bit\n"
    
    ax4.text(0.1, 0.9, info_text, transform=ax4.transAxes, fontsize=11,
             verticalalignment="top", fontfamily="monospace")
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved summary plot to {output_path}")
    
    return fig
