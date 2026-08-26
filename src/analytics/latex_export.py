"""LaTeX export utilities for experiment results.

This module provides functions for exporting experiment results
as LaTeX tables suitable for academic papers and thesis documents.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def export_metrics_table(
    data: list[dict[str, Any]],
    metrics: list[str] | None = None,
    caption: str = "Quantization Results",
    label: str = "tab:quant_results",
    precision: int = 2,
) -> str:
    """Export metrics as a LaTeX table.
    
    Args:
        data: List of dicts with method, model, and metric values
        metrics: Metrics to include (default: all numeric)
        caption: Table caption
        label: Table label for referencing
        precision: Decimal precision for numbers
        
    Returns:
        LaTeX table string
    """
    df = pd.DataFrame(data)
    
    # Determine metrics to include
    if metrics is None:
        metrics = [col for col in df.columns if df[col].dtype in ["float64", "int64"]]
    
    # Filter to only include specified metrics
    cols = ["method", "model"] if "model" in df.columns else ["method"]
    cols.extend([m for m in metrics if m in df.columns])
    df = df[cols]
    
    # Format column names
    col_format = {
        "method": "Method",
        "model": "Model",
        "perplexity": "PPL $\\downarrow$",
        "accuracy": "Acc $\\uparrow$",
        "latency_p50": "Lat. (ms)",
        "latency_p95": "P95 Lat.",
        "tokens_per_second": "Tok/s $\\uparrow$",
        "memory_allocated": "Mem (GB)",
        "compression_ratio": "Comp. $\\uparrow$",
        "bit_width": "Bits",
    }
    
    # Rename columns
    df = df.rename(columns={c: col_format.get(c, c.replace("_", " ").title()) for c in df.columns})
    
    # Generate LaTeX
    latex = df.to_latex(
        index=False,
        float_format=f"%.{precision}f",
        escape=False,
        column_format="l" + "c" * (len(df.columns) - 1),
    )
    
    # Wrap in table environment
    result = f"""\\begin{{table}}[htbp]
\\centering
\\caption{{{caption}}}
\\label{{{label}}}
{latex}
\\end{{table}}"""
    
    return result


def export_comparison_table(
    data: list[dict[str, Any]],
    baseline_method: str = "fp16",
    metrics: list[str] | None = None,
    caption: str = "Comparison with Baseline",
    label: str = "tab:comparison",
    show_delta: bool = True,
) -> str:
    """Export comparison table with baseline.
    
    Args:
        data: List of dicts with method and metric values
        baseline_method: Method to use as baseline
        metrics: Metrics to compare
        caption: Table caption
        label: Table label
        show_delta: Whether to show delta from baseline
        
    Returns:
        LaTeX table string
    """
    df = pd.DataFrame(data)
    metrics = metrics or ["perplexity", "latency_p50", "tokens_per_second"]
    
    # Get baseline values
    baseline = df[df["method"] == baseline_method]
    if baseline.empty:
        baseline = df.iloc[0:1]
    
    baseline_values = {m: baseline[m].values[0] for m in metrics if m in baseline.columns}
    
    # Build table rows
    rows = []
    for _, row in df.iterrows():
        method = row.get("method", "unknown")
        bit_width = row.get("bit_width", "-")
        
        row_data = {
            "Method": f"{method.upper()}",
            "Bits": str(bit_width),
        }
        
        for metric in metrics:
            if metric in row:
                value = row[metric]
                
                if show_delta and metric in baseline_values:
                    base = baseline_values[metric]
                    if base != 0:
                        delta = ((value - base) / base) * 100
                        delta_str = f"+{delta:.1f}\\%" if delta > 0 else f"{delta:.1f}\\%"
                        row_data[metric] = f"{value:.2f} ({delta_str})"
                    else:
                        row_data[metric] = f"{value:.2f}"
                else:
                    row_data[metric] = f"{value:.2f}"
        
        rows.append(row_data)
    
    result_df = pd.DataFrame(rows)
    
    # Format column names
    col_format = {
        "perplexity": "PPL",
        "latency_p50": "Lat. (ms)",
        "tokens_per_second": "Tok/s",
        "memory_allocated": "Mem (GB)",
    }
    result_df = result_df.rename(columns={c: col_format.get(c, c) for c in result_df.columns})
    
    # Generate LaTeX
    latex = result_df.to_latex(
        index=False,
        escape=False,
        column_format="l" * len(result_df.columns),
    )
    
    result = f"""\\begin{{table}}[htbp]
\\centering
\\caption{{{caption}}}
\\label{{{label}}}
{latex}
\\vspace{{0.5em}}
\\footnotesize{{Values in parentheses show \\% change from baseline ({baseline_method}).}}
\\end{{table}}"""
    
    return result


def export_layer_stats_table(
    layer_data: list[dict[str, Any]],
    stats: list[str] | None = None,
    max_layers: int = 10,
    caption: str = "Layer-wise Statistics",
    label: str = "tab:layer_stats",
) -> str:
    """Export layer-wise statistics as LaTeX table.
    
    Args:
        layer_data: List of layer metric dicts
        stats: Statistics to include
        max_layers: Maximum number of layers to show
        caption: Table caption
        label: Table label
        
    Returns:
        LaTeX table string
    """
    df = pd.DataFrame(layer_data)
    stats = stats or ["norm_l2", "mean", "std", "sparsity"]
    
    # Pivot to get stats as columns
    pivot_data = []
    for layer_idx in sorted(df["layer_index"].unique())[:max_layers]:
        layer_df = df[df["layer_index"] == layer_idx]
        row = {"Layer": layer_idx}
        
        for stat in stats:
            stat_row = layer_df[layer_df["stat_name"] == stat]
            if not stat_row.empty:
                row[stat] = stat_row["value"].values[0]
        
        pivot_data.append(row)
    
    result_df = pd.DataFrame(pivot_data)
    
    # Format column names
    col_format = {
        "norm_l2": "$\\|W\\|_2$",
        "mean": "$\\mu$",
        "std": "$\\sigma$",
        "sparsity": "Sparsity",
        "min": "Min",
        "max": "Max",
    }
    result_df = result_df.rename(columns={c: col_format.get(c, c) for c in result_df.columns})
    
    latex = result_df.to_latex(
        index=False,
        float_format="%.4f",
        escape=False,
    )
    
    result = f"""\\begin{{table}}[htbp]
\\centering
\\caption{{{caption}}}
\\label{{{label}}}
\\resizebox{{\\textwidth}}{{!}}{{
{latex}
}}
\\end{{table}}"""
    
    return result


def export_hardware_table(
    hardware_data: list[dict[str, Any]],
    caption: str = "Hardware Performance",
    label: str = "tab:hardware",
) -> str:
    """Export hardware statistics as LaTeX table.
    
    Args:
        hardware_data: List of hardware stat dicts
        caption: Table caption
        label: Table label
        
    Returns:
        LaTeX table string
    """
    rows = []
    
    for hw in hardware_data:
        rows.append({
            "Method": hw.get("method", "-"),
            "GPU": hw.get("gpu_type", "-"),
            "Lat. P50 (ms)": f"{hw.get('latency_p50', 0):.2f}",
            "Lat. P95 (ms)": f"{hw.get('latency_p95', 0):.2f}",
            "Tok/s": f"{hw.get('tokens_per_second', 0):.1f}",
            "Mem (GB)": f"{hw.get('memory_allocated', 0):.2f}",
            "Size (MB)": f"{hw.get('model_size_mb', 0):.1f}",
        })
    
    df = pd.DataFrame(rows)
    
    latex = df.to_latex(
        index=False,
        escape=False,
    )
    
    result = f"""\\begin{{table}}[htbp]
\\centering
\\caption{{{caption}}}
\\label{{{label}}}
\\resizebox{{\\textwidth}}{{!}}{{
{latex}
}}
\\end{{table}}"""
    
    return result


def export_full_results_appendix(
    experiment_data: dict[str, Any],
    output_path: str | None = None,
) -> str:
    """Export full experiment results as LaTeX appendix.
    
    Args:
        experiment_data: Full experiment data from database
        output_path: Optional path to save file
        
    Returns:
        LaTeX string
    """
    exp = experiment_data.get("experiment", {})
    quant_configs = experiment_data.get("quant_configs", [])
    metrics = experiment_data.get("metrics", [])
    hardware = experiment_data.get("hardware_stats", [])
    
    sections = []
    
    # Header
    sections.append(f"""\\section{{Experiment {exp.get('id', 'Unknown')} Details}}
\\label{{sec:exp_{exp.get('id', 0)}}}

\\subsection{{Configuration}}
\\begin{{itemize}}
    \\item Model: \\texttt{{{exp.get('model_name', 'Unknown')}}}
    \\item Base Precision: {exp.get('base_precision', 'Unknown')}
    \\item Hardware: {exp.get('gpu_type', 'Unknown')}
    \\item Status: {exp.get('status', 'Unknown')}
\\end{{itemize}}
""")
    
    # Quantization configs
    if quant_configs:
        sections.append("\\subsection{Quantization Methods}")
        for qc in quant_configs:
            sections.append(f"""\\paragraph{{{qc.get('method_name', 'Unknown').upper()}}}
\\begin{{itemize}}
    \\item Bit Width: {qc.get('bit_width', '-')}
    \\item Per-Channel: {qc.get('per_channel', '-')}
    \\item Group Size: {qc.get('group_size', '-')}
    \\item Duration: {qc.get('duration_seconds', 0):.1f}s
\\end{{itemize}}
""")
    
    # Metrics table
    if metrics:
        metrics_table = export_metrics_table(
            metrics,
            caption=f"Metrics for Experiment {exp.get('id', '')}",
            label=f"tab:exp_{exp.get('id', 0)}_metrics",
        )
        sections.append("\\subsection{Evaluation Metrics}")
        sections.append(metrics_table)
    
    # Hardware table
    if hardware:
        hw_table = export_hardware_table(
            hardware,
            caption=f"Hardware Performance for Experiment {exp.get('id', '')}",
            label=f"tab:exp_{exp.get('id', 0)}_hardware",
        )
        sections.append("\\subsection{Hardware Performance}")
        sections.append(hw_table)
    
    result = "\n\n".join(sections)
    
    if output_path:
        with open(output_path, "w") as f:
            f.write(result)
        logger.info(f"Saved LaTeX appendix to {output_path}")
    
    return result


# ============================================================================
# Enhanced tables: auto-bold-best, confidence intervals, ablation tables
# ============================================================================


def export_metrics_table_enhanced(
    data: list[dict[str, Any]],
    metrics: list[str] | None = None,
    caption: str = "Quantization Results",
    label: str = "tab:quant_results",
    precision: int = 2,
    bold_best: bool = True,
    lower_is_better: dict[str, bool] | None = None,
    show_ci: bool = False,
    ci_key_suffix: str = "_std",
) -> str:
    """Export metrics table with auto-bold-best and optional confidence intervals.

    Args:
        data: Rows with keys like method, model, perplexity, perplexity_std, ...
        metrics: Numeric columns to include.
        bold_best: Highlight the best value per metric per model.
        lower_is_better: Per-metric flag. Defaults: perplexity=True, else False.
        show_ci: Show ±std as confidence interval suffix.
        ci_key_suffix: Suffix for the std column (e.g. "_std").
    """
    import numpy as np

    df = pd.DataFrame(data)
    if metrics is None:
        metrics = [c for c in df.columns if df[c].dtype in ("float64", "int64")]

    lower_map: dict[str, bool] = lower_is_better or {}
    lower_map.setdefault("perplexity", True)
    lower_map.setdefault("loss", True)

    # Group by model if present
    group_col = "model" if "model" in df.columns else None

    def _fmt(val: float, std: float | None, is_best: bool) -> str:
        s = f"{val:.{precision}f}"
        if show_ci and std is not None and not np.isnan(std):
            s += f"$\\pm${std:.{precision}f}"
        if is_best and bold_best:
            s = f"\\textbf{{{s}}}"
        return s

    # For each metric, find the best per group
    best_idx: dict[str, dict[str, float]] = {}
    for m in metrics:
        if m not in df.columns:
            continue
        lib = lower_map.get(m, False)
        best_idx[m] = {}
        groups = df[group_col].unique() if group_col else ["__all__"]
        for g in groups:
            mask = df[group_col] == g if group_col else pd.Series([True] * len(df))
            vals = df.loc[mask, m].dropna()
            if len(vals) == 0:
                continue
            best_val = vals.min() if lib else vals.max()
            best_idx[m][str(g)] = best_val

    # Build rows
    rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        r: dict[str, str] = {}
        r["Method"] = row.get("method", "-")
        if group_col:
            r["Model"] = row.get("model", "-")
        if "bit_width" in row:
            r["Bits"] = str(int(row["bit_width"])) if pd.notna(row["bit_width"]) else "-"

        grp = str(row.get(group_col, "__all__")) if group_col else "__all__"

        for m in metrics:
            if m not in row or pd.isna(row[m]):
                r[m] = "-"
                continue
            val = float(row[m])
            std_col = m + ci_key_suffix
            std = float(row[std_col]) if std_col in row and pd.notna(row.get(std_col)) else None
            is_best = m in best_idx and grp in best_idx[m] and val == best_idx[m][grp]
            r[m] = _fmt(val, std, is_best)

        rows.append(r)

    result_df = pd.DataFrame(rows)

    # Pretty column names
    col_fmt = {
        "perplexity": "PPL $\\downarrow$",
        "accuracy": "Acc $\\uparrow$",
        "latency_p50": "Lat. (ms)",
        "tokens_per_second": "Tok/s $\\uparrow$",
        "memory_peak": "Mem (GB)",
        "compression_ratio": "Comp. $\\uparrow$",
    }
    result_df = result_df.rename(
        columns={c: col_fmt.get(c, c.replace("_", " ").title()) for c in result_df.columns}
    )

    latex = result_df.to_latex(index=False, escape=False, column_format="l" * len(result_df.columns))

    note = ""
    if bold_best:
        note = "\\footnotesize{Best values per model are \\textbf{bolded}.}"
    if show_ci:
        note += " Values show mean$\\pm$std across seeds."

    return f"""\\begin{{table}}[htbp]
\\centering
\\caption{{{caption}}}
\\label{{{label}}}
{latex}
\\vspace{{0.3em}}
{note}
\\end{{table}}"""


def export_ablation_table(
    data: list[dict[str, Any]],
    row_key: str = "method",
    col_key: str = "bit_width",
    value_key: str = "perplexity",
    std_key: str | None = "perplexity_std",
    caption: str = "Ablation: Method $\\times$ Bit Width",
    label: str = "tab:ablation",
    precision: int = 2,
    bold_best: bool = True,
    lower_is_better: bool = True,
) -> str:
    """Export a method x parameter ablation table.

    Args:
        data: Rows with row_key, col_key, value_key, and optionally std_key.
        row_key: Column used as rows (e.g. "method").
        col_key: Column used as columns (e.g. "bit_width").
        value_key: Metric value column.
        std_key: Optional std column for CI.
        bold_best: Bold the best value per column.
        lower_is_better: Whether lower metric is better.
    """
    import numpy as np

    df = pd.DataFrame(data)
    row_labels = sorted(df[row_key].unique())
    col_labels = sorted(df[col_key].unique())

    # Build matrix
    cell: dict[tuple, str] = {}
    for cl in col_labels:
        col_mask = df[col_key] == cl
        vals = df.loc[col_mask, value_key].dropna()
        best = vals.min() if lower_is_better else vals.max()
        if len(vals) == 0:
            best = None

        for rl in row_labels:
            mask = (df[row_key] == rl) & (df[col_key] == cl)
            subset = df.loc[mask]
            if subset.empty:
                cell[(rl, cl)] = "-"
                continue
            v = subset[value_key].values[0]
            is_best = best is not None and v == best
            s = f"{v:.{precision}f}"
            if std_key and std_key in subset.columns and pd.notna(subset[std_key].values[0]):
                s += f"$\\pm${subset[std_key].values[0]:.{precision}f}"
            if is_best and bold_best:
                s = f"\\textbf{{{s}}}"
            cell[(rl, cl)] = s

    # Build LaTeX manually for full control
    n_cols = len(col_labels) + 1
    col_spec = "l" + "c" * len(col_labels)
    header = " & ".join(["Method"] + [str(c) for c in col_labels])

    rows_tex: list[str] = []
    for rl in row_labels:
        vals = [cell.get((rl, cl), "-") for cl in col_labels]
        rows_tex.append(f"    {rl} & " + " & ".join(vals) + " \\\\")

    body = "\n".join(rows_tex)

    note = ""
    if bold_best:
        direction = "lowest" if lower_is_better else "highest"
        note = f"\\footnotesize{{Best ({direction}) per column is \\textbf{{bolded}}.}}"

    return f"""\\begin{{table}}[htbp]
\\centering
\\caption{{{caption}}}
\\label{{{label}}}
\\begin{{tabular}}{{{col_spec}}}
\\toprule
    {header} \\\\
\\midrule
{body}
\\bottomrule
\\end{{tabular}}
\\vspace{{0.3em}}
{note}
\\end{{table}}"""
