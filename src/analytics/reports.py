"""Local report generation utilities.

This module provides functions for generating Markdown reports
from experiment data without requiring the scientist LLM.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_markdown_report(
    experiment_data: dict[str, Any],
    output_path: str | None = None,
    include_plots: bool = False,
) -> str:
    """Generate a Markdown report from experiment data.
    
    Args:
        experiment_data: Full experiment data from database
        output_path: Optional path to save report
        include_plots: Whether to generate and include plots
        
    Returns:
        Markdown report string
    """
    exp = experiment_data.get("experiment", {})
    quant_configs = experiment_data.get("quant_configs", [])
    metrics = experiment_data.get("metrics", [])
    hardware = experiment_data.get("hardware_stats", [])
    layer_metrics = experiment_data.get("layer_metrics", [])
    
    sections = []
    
    # Header
    sections.append(f"""# Experiment Report: {exp.get('name', f"Experiment {exp.get('id', 'Unknown')}")}

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## Overview

| Property | Value |
|----------|-------|
| Experiment ID | {exp.get('id', 'Unknown')} |
| Model | `{exp.get('model_name', 'Unknown')}` |
| Base Precision | {exp.get('base_precision', 'Unknown')} |
| Hardware | {exp.get('gpu_type', 'Unknown')} x{exp.get('gpu_count', 1)} |
| Status | **{exp.get('status', 'Unknown')}** |
| Created | {exp.get('created_at', 'Unknown')} |
""")
    
    if exp.get('notes'):
        sections.append(f"""
### Notes

{exp['notes']}
""")
    
    # Quantization Configuration
    if quant_configs:
        sections.append("""
## Quantization Configuration
""")
        
        for i, qc in enumerate(quant_configs):
            sections.append(f"""
### Method {i + 1}: {qc.get('method_name', 'Unknown').upper()}

| Parameter | Value |
|-----------|-------|
| Bit Width | {qc.get('bit_width', '-')} |
| Per-Channel | {qc.get('per_channel', '-')} |
| Symmetric | {qc.get('symmetric', '-')} |
| Group Size | {qc.get('group_size', '-')} |
| Activation Quant | {qc.get('activation_quant', False)} |
| KV Quant | {qc.get('kv_quant', False)} |
| Calibration Dataset | {qc.get('calib_dataset', '-')} |
| Calibration Samples | {qc.get('calib_size', '-')} |
| Status | {qc.get('status', '-')} |
| Duration | {qc.get('duration_seconds', 0):.2f}s |
""")
    
    # Evaluation Metrics
    if metrics:
        sections.append("""
## Evaluation Metrics
""")
        
        # Group by dataset
        by_dataset: dict[str, list[dict]] = {}
        for m in metrics:
            dataset = m.get("dataset", "unknown")
            if dataset not in by_dataset:
                by_dataset[dataset] = []
            by_dataset[dataset].append(m)
        
        for dataset, dataset_metrics in by_dataset.items():
            sections.append(f"""
### {dataset}

| Metric | Value | Split |
|--------|-------|-------|""")
            
            for m in dataset_metrics:
                value = m.get("value", 0)
                value_str = f"{value:.4f}" if isinstance(value, float) else str(value)
                sections.append(f"| {m.get('metric_name', '-')} | {value_str} | {m.get('split', 'test')} |")
    
    # Hardware Performance
    if hardware:
        hw = hardware[-1]  # Use most recent
        
        sections.append(f"""
## Hardware Performance

### Latency

| Metric | Value |
|--------|-------|
| P50 | {hw.get('latency_p50', 'N/A')} ms |
| P95 | {hw.get('latency_p95', 'N/A')} ms |
| P99 | {hw.get('latency_p99', 'N/A')} ms |
| Mean | {hw.get('latency_mean', 'N/A')} ms |
| Std | {hw.get('latency_std', 'N/A')} ms |

### Throughput

| Metric | Value |
|--------|-------|
| Tokens/second | {hw.get('tokens_per_second', 'N/A')} |
| Batch Size | {hw.get('batch_size', 'N/A')} |
| Sequence Length | {hw.get('sequence_length', 'N/A')} |

### Memory

| Metric | Value |
|--------|-------|
| Allocated | {hw.get('memory_allocated', 'N/A')} GB |
| Peak | {hw.get('memory_peak', 'N/A')} GB |
| Model Size | {hw.get('model_size_mb', 'N/A')} MB |
| Quantized Size | {hw.get('quantized_size_mb', 'N/A')} MB |
| Compression Ratio | {hw.get('compression_ratio', 'N/A')}x |
""")
    
    # Layer-wise Statistics Summary
    if layer_metrics:
        sections.append("""
## Layer-wise Statistics Summary
""")
        
        # Compute summary statistics
        import pandas as pd
        lm_df = pd.DataFrame(layer_metrics)
        
        for stat_type in lm_df["stat_type"].unique():
            type_df = lm_df[lm_df["stat_type"] == stat_type]
            
            sections.append(f"""
### {stat_type.replace('_', ' ').title()}

| Statistic | Mean | Min | Max | Std |
|-----------|------|-----|-----|-----|""")
            
            for stat_name in type_df["stat_name"].unique()[:10]:
                stat_df = type_df[type_df["stat_name"] == stat_name]
                values = stat_df["value"]
                sections.append(
                    f"| {stat_name} | {values.mean():.4f} | {values.min():.4f} | "
                    f"{values.max():.4f} | {values.std():.4f} |"
                )
    
    # Footer
    sections.append("""
---

*Report generated by LLM Quant Lab*
""")
    
    report = "\n".join(sections)
    
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report)
        logger.info(f"Saved report to {output_path}")
    
    return report


def generate_comparison_report(
    experiments: list[dict[str, Any]],
    output_path: str | None = None,
) -> str:
    """Generate a comparison report for multiple experiments.
    
    Args:
        experiments: List of experiment data dictionaries
        output_path: Optional path to save report
        
    Returns:
        Markdown report string
    """
    sections = []
    
    sections.append(f"""# Experiment Comparison Report

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

**Experiments Compared**: {len(experiments)}

---

## Summary Table

| Exp ID | Model | Method | Bits | Perplexity | Latency P50 | Tokens/s |
|--------|-------|--------|------|------------|-------------|----------|""")
    
    for exp_data in experiments:
        exp = exp_data.get("experiment", {})
        qc = exp_data.get("quant_configs", [{}])[0] if exp_data.get("quant_configs") else {}
        metrics = exp_data.get("metrics", [])
        hardware = exp_data.get("hardware_stats", [{}])[-1] if exp_data.get("hardware_stats") else {}
        
        # Find perplexity
        ppl = next((m["value"] for m in metrics if m.get("metric_name") == "perplexity"), "N/A")
        ppl_str = f"{ppl:.2f}" if isinstance(ppl, (int, float)) else ppl
        
        sections.append(
            f"| {exp.get('id', '-')} | {exp.get('model_name', '-')[:20]} | "
            f"{qc.get('method_name', '-')} | {qc.get('bit_width', '-')} | "
            f"{ppl_str} | {hardware.get('latency_p50', 'N/A')} | "
            f"{hardware.get('tokens_per_second', 'N/A')} |"
        )
    
    # Detailed sections for each experiment
    sections.append("""
---

## Detailed Results
""")
    
    for exp_data in experiments:
        exp = exp_data.get("experiment", {})
        sections.append(f"""
### Experiment {exp.get('id', 'Unknown')}: {exp.get('name', 'Unnamed')}

Model: `{exp.get('model_name', 'Unknown')}`
Status: {exp.get('status', 'Unknown')}
""")
        
        # Metrics
        metrics = exp_data.get("metrics", [])
        if metrics:
            sections.append("**Metrics:**")
            for m in metrics:
                value = m.get("value", 0)
                value_str = f"{value:.4f}" if isinstance(value, float) else str(value)
                sections.append(f"- {m.get('metric_name', '-')}: {value_str}")
    
    sections.append("""
---

*Report generated by LLM Quant Lab*
""")
    
    report = "\n".join(sections)
    
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report)
        logger.info(f"Saved comparison report to {output_path}")
    
    return report


def generate_quick_summary(experiment_data: dict[str, Any]) -> str:
    """Generate a quick one-paragraph summary.
    
    Args:
        experiment_data: Experiment data
        
    Returns:
        Summary string
    """
    exp = experiment_data.get("experiment", {})
    qc = experiment_data.get("quant_configs", [{}])[0] if experiment_data.get("quant_configs") else {}
    metrics = experiment_data.get("metrics", [])
    hardware = experiment_data.get("hardware_stats", [{}])[-1] if experiment_data.get("hardware_stats") else {}
    
    # Find key metrics
    ppl = next((m["value"] for m in metrics if m.get("metric_name") == "perplexity"), None)
    
    summary_parts = [
        f"Experiment {exp.get('id', '?')} applied {qc.get('method_name', 'unknown').upper()} "
        f"{qc.get('bit_width', '?')}-bit quantization to {exp.get('model_name', 'unknown')}."
    ]
    
    if ppl is not None:
        summary_parts.append(f"Achieved perplexity of {ppl:.2f}.")
    
    if hardware.get("latency_p50"):
        summary_parts.append(f"Latency: {hardware['latency_p50']:.1f}ms (P50).")
    
    if hardware.get("tokens_per_second"):
        summary_parts.append(f"Throughput: {hardware['tokens_per_second']:.1f} tokens/s.")
    
    summary_parts.append(f"Status: {exp.get('status', 'unknown')}.")
    
    return " ".join(summary_parts)
