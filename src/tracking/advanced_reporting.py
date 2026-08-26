"""Advanced reporting module for quantization experiments.

This module provides comprehensive reporting capabilities including:
- Automated analysis and insights generation
- Publication-ready figures and tables
- Paper comparison reports
- Executive summaries
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# Plotting Setup
# ============================================================================

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import seaborn as sns
    
    # Set publication-quality defaults
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.figsize': (10, 6),
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
    })
    
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available for plotting")

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("plotly not available for interactive plots")


# ============================================================================
# Report Data Classes
# ============================================================================

@dataclass
class QuantizationResult:
    """Single quantization experiment result."""
    
    model: str
    method: str
    bit_width: int
    group_size: int | None = None
    
    # Perplexity results
    perplexity: dict[str, float] = field(default_factory=dict)
    
    # Hardware metrics
    latency_ms: float | None = None
    throughput_tps: float | None = None
    memory_gb: float | None = None
    model_size_mb: float | None = None
    compression_ratio: float | None = None
    
    # Timing
    quantization_time_s: float | None = None
    
    # Layer stats
    layer_stats: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentReport:
    """Complete experiment report."""
    
    title: str
    description: str
    
    # Results
    results: list[QuantizationResult] = field(default_factory=list)
    
    # Paper comparison
    paper_id: str | None = None
    paper_comparisons: list[dict[str, Any]] = field(default_factory=list)
    
    # Analysis
    key_findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    # Metadata
    author: str = "LLM Quant Lab"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "results": [r.__dict__ for r in self.results],
            "paper_id": self.paper_id,
            "paper_comparisons": self.paper_comparisons,
            "key_findings": self.key_findings,
            "recommendations": self.recommendations,
            "author": self.author,
            "timestamp": self.timestamp,
        }


# ============================================================================
# Advanced Report Generator
# ============================================================================

class AdvancedReportGenerator:
    """Generates comprehensive reports for quantization experiments."""
    
    def __init__(
        self,
        output_dir: str | Path = "reports",
        style: str = "publication",
    ):
        """Initialize report generator.
        
        Args:
            output_dir: Directory for report outputs
            style: Report style ('publication', 'technical', 'executive')
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.style = style
        
        # Color schemes
        self.method_colors = {
            "fp16": "#2ecc71",
            "gptq": "#3498db",
            "awq": "#9b59b6",
            "smoothquant": "#e74c3c",
            "rtn": "#95a5a6",
            "hqq": "#f39c12",
            "omniquant": "#1abc9c",
        }
    
    def create_results_dataframe(
        self,
        results: list[QuantizationResult],
    ) -> pd.DataFrame:
        """Convert results to DataFrame.
        
        Args:
            results: List of quantization results
            
        Returns:
            Pandas DataFrame
        """
        rows = []
        for r in results:
            row = {
                "model": r.model,
                "method": r.method,
                "bit_width": r.bit_width,
                "group_size": r.group_size,
                "latency_ms": r.latency_ms,
                "throughput_tps": r.throughput_tps,
                "memory_gb": r.memory_gb,
                "model_size_mb": r.model_size_mb,
                "compression_ratio": r.compression_ratio,
                "quantization_time_s": r.quantization_time_s,
            }
            
            # Add perplexity for each dataset
            for dataset, ppl in r.perplexity.items():
                row[f"ppl_{dataset}"] = ppl
            
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    def plot_perplexity_comparison(
        self,
        df: pd.DataFrame,
        dataset: str = "wikitext2",
        save_path: str | None = None,
        title: str | None = None,
    ):
        """Create perplexity comparison plot.
        
        Args:
            df: Results DataFrame
            dataset: Dataset to plot
            save_path: Optional save path
            title: Plot title
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available")
            return
        
        ppl_col = f"ppl_{dataset}"
        if ppl_col not in df.columns:
            logger.warning(f"No perplexity data for {dataset}")
            return
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Group by model
        models = df["model"].unique()
        methods = df["method"].unique()
        
        x = np.arange(len(models))
        width = 0.8 / len(methods)
        
        for i, method in enumerate(methods):
            method_data = df[df["method"] == method]
            values = [
                method_data[method_data["model"] == m][ppl_col].values[0]
                if m in method_data["model"].values else 0
                for m in models
            ]
            
            color = self.method_colors.get(method, f"C{i}")
            bars = ax.bar(
                x + i * width - width * len(methods) / 2,
                values,
                width,
                label=method.upper(),
                color=color,
                alpha=0.85,
            )
            
            # Add value labels
            for bar, val in zip(bars, values):
                if val > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.5,
                        f"{val:.1f}",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        rotation=45,
                    )
        
        ax.set_xlabel("Model")
        ax.set_ylabel(f"Perplexity ({dataset})")
        ax.set_title(title or f"Perplexity Comparison on {dataset.upper()}")
        ax.set_xticks(x)
        ax.set_xticklabels([m.split("/")[-1] for m in models], rotation=45, ha="right")
        ax.legend(loc="upper right")
        ax.grid(axis="y", alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved perplexity plot to {save_path}")
        
        return fig
    
    def plot_bit_width_analysis(
        self,
        df: pd.DataFrame,
        model: str,
        method: str,
        save_path: str | None = None,
    ):
        """Create bit-width analysis plot.
        
        Args:
            df: Results DataFrame
            model: Model to analyze
            method: Method to analyze
            save_path: Optional save path
        """
        if not MATPLOTLIB_AVAILABLE:
            return
        
        model_df = df[(df["model"] == model) & (df["method"] == method)]
        if model_df.empty:
            logger.warning(f"No data for {model} with {method}")
            return
        
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        bit_widths = model_df["bit_width"].values
        
        # Perplexity vs bit-width
        ppl_cols = [c for c in model_df.columns if c.startswith("ppl_")]
        if ppl_cols:
            ax = axes[0]
            for col in ppl_cols:
                dataset = col.replace("ppl_", "")
                ax.plot(bit_widths, model_df[col].values, "o-", label=dataset)
            ax.set_xlabel("Bit Width")
            ax.set_ylabel("Perplexity")
            ax.set_title("Perplexity vs Bit Width")
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        # Model size vs bit-width
        ax = axes[1]
        if "model_size_mb" in model_df.columns:
            ax.bar(bit_widths, model_df["model_size_mb"].values, color=self.method_colors.get(method, "C0"))
            ax.set_xlabel("Bit Width")
            ax.set_ylabel("Model Size (MB)")
            ax.set_title("Model Size vs Bit Width")
            ax.grid(True, alpha=0.3)
        
        # Compression ratio vs bit-width
        ax = axes[2]
        if "compression_ratio" in model_df.columns:
            ax.plot(bit_widths, model_df["compression_ratio"].values, "s-", color="green", markersize=10)
            ax.set_xlabel("Bit Width")
            ax.set_ylabel("Compression Ratio")
            ax.set_title("Compression vs Bit Width")
            ax.grid(True, alpha=0.3)
        
        plt.suptitle(f"{model.split('/')[-1]} - {method.upper()} Analysis", fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved bit-width analysis to {save_path}")
        
        return fig
    
    def plot_pareto_frontier(
        self,
        df: pd.DataFrame,
        x_metric: str = "model_size_mb",
        y_metric: str = "ppl_wikitext2",
        save_path: str | None = None,
    ):
        """Create Pareto frontier plot (quality vs efficiency).
        
        Args:
            df: Results DataFrame
            x_metric: X-axis metric (efficiency)
            y_metric: Y-axis metric (quality)
            save_path: Optional save path
        """
        if not MATPLOTLIB_AVAILABLE:
            return
        
        if x_metric not in df.columns or y_metric not in df.columns:
            logger.warning(f"Missing columns: {x_metric} or {y_metric}")
            return
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot each method with different colors
        for method in df["method"].unique():
            method_df = df[df["method"] == method]
            color = self.method_colors.get(method, None)
            
            ax.scatter(
                method_df[x_metric],
                method_df[y_metric],
                s=100,
                c=color,
                label=method.upper(),
                alpha=0.7,
                edgecolors="black",
                linewidths=0.5,
            )
            
            # Add model labels
            for _, row in method_df.iterrows():
                model_short = row["model"].split("/")[-1]
                ax.annotate(
                    f"{model_short}\n{row['bit_width']}b",
                    (row[x_metric], row[y_metric]),
                    textcoords="offset points",
                    xytext=(5, 5),
                    fontsize=7,
                    alpha=0.8,
                )
        
        # Identify Pareto frontier
        pareto_points = self._find_pareto_frontier(
            df[[x_metric, y_metric]].values,
            maximize_x=False,  # Lower size is better
            maximize_y=False,  # Lower perplexity is better
        )
        
        if len(pareto_points) > 1:
            pareto_df = df.iloc[pareto_points].sort_values(x_metric)
            ax.plot(
                pareto_df[x_metric],
                pareto_df[y_metric],
                "k--",
                alpha=0.5,
                linewidth=2,
                label="Pareto Frontier",
            )
        
        ax.set_xlabel(x_metric.replace("_", " ").title())
        ax.set_ylabel(y_metric.replace("_", " ").replace("ppl", "Perplexity").title())
        ax.set_title("Quality vs Efficiency Pareto Analysis")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved Pareto plot to {save_path}")
        
        return fig
    
    def _find_pareto_frontier(
        self,
        points: np.ndarray,
        maximize_x: bool = False,
        maximize_y: bool = False,
    ) -> list[int]:
        """Find Pareto-optimal points.
        
        Args:
            points: Nx2 array of (x, y) points
            maximize_x: Whether to maximize x
            maximize_y: Whether to maximize y
            
        Returns:
            Indices of Pareto-optimal points
        """
        n = len(points)
        pareto_indices = []
        
        for i in range(n):
            is_dominated = False
            for j in range(n):
                if i == j:
                    continue
                
                if maximize_x:
                    x_better = points[j, 0] >= points[i, 0]
                    x_strict = points[j, 0] > points[i, 0]
                else:
                    x_better = points[j, 0] <= points[i, 0]
                    x_strict = points[j, 0] < points[i, 0]
                
                if maximize_y:
                    y_better = points[j, 1] >= points[i, 1]
                    y_strict = points[j, 1] > points[i, 1]
                else:
                    y_better = points[j, 1] <= points[i, 1]
                    y_strict = points[j, 1] < points[i, 1]
                
                if x_better and y_better and (x_strict or y_strict):
                    is_dominated = True
                    break
            
            if not is_dominated:
                pareto_indices.append(i)
        
        return pareto_indices
    
    def plot_layer_statistics(
        self,
        layer_stats: dict[str, dict[str, float]],
        stat_name: str = "weight_range",
        save_path: str | None = None,
    ):
        """Plot layer-wise statistics.
        
        Args:
            layer_stats: Dict of layer_name -> stats
            stat_name: Statistic to plot
            save_path: Optional save path
        """
        if not MATPLOTLIB_AVAILABLE:
            return
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        layers = list(layer_stats.keys())
        values = [layer_stats[l].get(stat_name, 0) for l in layers]
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(layers)))
        bars = ax.bar(range(len(layers)), values, color=colors)
        
        ax.set_xlabel("Layer")
        ax.set_ylabel(stat_name.replace("_", " ").title())
        ax.set_title(f"Layer-wise {stat_name.replace('_', ' ').title()}")
        ax.set_xticks(range(0, len(layers), max(1, len(layers) // 20)))
        ax.grid(axis="y", alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            logger.info(f"Saved layer stats plot to {save_path}")
        
        return fig
    
    def create_interactive_dashboard(
        self,
        df: pd.DataFrame,
        save_path: str | None = None,
    ):
        """Create interactive Plotly dashboard.
        
        Args:
            df: Results DataFrame
            save_path: Optional HTML save path
        """
        if not PLOTLY_AVAILABLE:
            logger.warning("plotly not available")
            return
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Perplexity Comparison",
                "Model Size Comparison",
                "Latency vs Perplexity",
                "Compression vs Quality",
            ),
            specs=[[{"type": "bar"}, {"type": "bar"}],
                   [{"type": "scatter"}, {"type": "scatter"}]],
        )
        
        # Perplexity comparison
        ppl_col = "ppl_wikitext2" if "ppl_wikitext2" in df.columns else df.filter(like="ppl_").columns[0] if any(df.columns.str.startswith("ppl_")) else None
        
        if ppl_col:
            for method in df["method"].unique():
                method_df = df[df["method"] == method]
                fig.add_trace(
                    go.Bar(
                        x=[m.split("/")[-1] for m in method_df["model"]],
                        y=method_df[ppl_col],
                        name=method.upper(),
                        marker_color=self.method_colors.get(method, None),
                    ),
                    row=1, col=1,
                )
        
        # Model size comparison
        if "model_size_mb" in df.columns:
            for method in df["method"].unique():
                method_df = df[df["method"] == method]
                fig.add_trace(
                    go.Bar(
                        x=[m.split("/")[-1] for m in method_df["model"]],
                        y=method_df["model_size_mb"],
                        name=method.upper(),
                        marker_color=self.method_colors.get(method, None),
                        showlegend=False,
                    ),
                    row=1, col=2,
                )
        
        # Latency vs Perplexity scatter
        if "latency_ms" in df.columns and ppl_col:
            for method in df["method"].unique():
                method_df = df[df["method"] == method]
                fig.add_trace(
                    go.Scatter(
                        x=method_df["latency_ms"],
                        y=method_df[ppl_col],
                        mode="markers+text",
                        name=method.upper(),
                        text=[m.split("/")[-1] for m in method_df["model"]],
                        textposition="top center",
                        marker=dict(size=12, color=self.method_colors.get(method, None)),
                        showlegend=False,
                    ),
                    row=2, col=1,
                )
        
        # Compression vs Quality scatter
        if "compression_ratio" in df.columns and ppl_col:
            for method in df["method"].unique():
                method_df = df[df["method"] == method]
                fig.add_trace(
                    go.Scatter(
                        x=method_df["compression_ratio"],
                        y=method_df[ppl_col],
                        mode="markers+text",
                        name=method.upper(),
                        text=[m.split("/")[-1] for m in method_df["model"]],
                        textposition="top center",
                        marker=dict(size=12, color=self.method_colors.get(method, None)),
                        showlegend=False,
                    ),
                    row=2, col=2,
                )
        
        fig.update_layout(
            height=800,
            title_text="Quantization Experiment Dashboard",
            showlegend=True,
        )
        
        if save_path:
            fig.write_html(save_path)
            logger.info(f"Saved interactive dashboard to {save_path}")
        
        return fig
    
    def generate_markdown_report(
        self,
        report: ExperimentReport,
        include_plots: bool = True,
    ) -> str:
        """Generate a complete markdown report.
        
        Args:
            report: Experiment report data
            include_plots: Whether to generate and embed plots
            
        Returns:
            Markdown string
        """
        md = f"""# {report.title}

**Author**: {report.author}  
**Date**: {report.timestamp}

## Description

{report.description}

## Results Summary

"""
        
        # Create results table
        df = self.create_results_dataframe(report.results)
        
        # Summary table
        md += "### Perplexity Results\n\n"
        md += "| Model | Method | Bits | Group Size "
        ppl_cols = [c for c in df.columns if c.startswith("ppl_")]
        for col in ppl_cols:
            dataset = col.replace("ppl_", "").upper()
            md += f"| {dataset} PPL "
        md += "|\n"
        md += "|" + "---|" * (4 + len(ppl_cols)) + "\n"
        
        for _, row in df.iterrows():
            model_short = row["model"].split("/")[-1]
            md += f"| {model_short} | {row['method']} | {row['bit_width']} | {row['group_size'] or '-'} "
            for col in ppl_cols:
                val = row.get(col)
                md += f"| {val:.2f} " if val else "| - "
            md += "|\n"
        
        md += "\n"
        
        # Hardware metrics table
        if "latency_ms" in df.columns or "memory_gb" in df.columns:
            md += "### Hardware Metrics\n\n"
            md += "| Model | Method | Bits | Latency (ms) | Memory (GB) | Size (MB) | Compression |\n"
            md += "|---|---|---|---|---|---|---|\n"
            
            for _, row in df.iterrows():
                model_short = row["model"].split("/")[-1]
                latency = f"{row['latency_ms']:.1f}" if row.get('latency_ms') else "-"
                memory = f"{row['memory_gb']:.2f}" if row.get('memory_gb') else "-"
                size = f"{row['model_size_mb']:.0f}" if row.get('model_size_mb') else "-"
                compression = f"{row['compression_ratio']:.2f}x" if row.get('compression_ratio') else "-"
                md += f"| {model_short} | {row['method']} | {row['bit_width']} | {latency} | {memory} | {size} | {compression} |\n"
            
            md += "\n"
        
        # Paper comparison
        if report.paper_comparisons:
            md += "## Paper Comparison\n\n"
            md += "| Model | Method | Bits | Dataset | Ours | Paper | Diff (%) | Status |\n"
            md += "|---|---|---|---|---|---|---|---|\n"
            
            for comp in report.paper_comparisons:
                model_short = comp["model"].split("/")[-1]
                paper_val = comp.get("paper_value", "-")
                our_val = comp.get("our_value", "-")
                diff = comp.get("relative_diff_pct", "-")
                
                if isinstance(diff, float):
                    diff_str = f"{diff:+.1f}%"
                    status = "✓" if abs(diff) <= 10 else "✗"
                else:
                    diff_str = "-"
                    status = "?"
                
                md += f"| {model_short} | {comp['method']} | {comp['bit_width']} | {comp['dataset']} | {our_val:.2f} | {paper_val} | {diff_str} | {status} |\n"
            
            md += "\n"
        
        # Key findings
        if report.key_findings:
            md += "## Key Findings\n\n"
            for i, finding in enumerate(report.key_findings, 1):
                md += f"{i}. {finding}\n"
            md += "\n"
        
        # Recommendations
        if report.recommendations:
            md += "## Recommendations\n\n"
            for i, rec in enumerate(report.recommendations, 1):
                md += f"{i}. {rec}\n"
            md += "\n"
        
        # Generate and save plots
        if include_plots and MATPLOTLIB_AVAILABLE:
            report_dir = self.output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            report_dir.mkdir(parents=True, exist_ok=True)
            
            # Perplexity comparison
            ppl_plot_path = report_dir / "perplexity_comparison.png"
            self.plot_perplexity_comparison(df, save_path=str(ppl_plot_path))
            md += f"\n## Figures\n\n"
            md += f"![Perplexity Comparison]({ppl_plot_path})\n\n"
            
            # Pareto plot
            if "model_size_mb" in df.columns:
                pareto_path = report_dir / "pareto_frontier.png"
                self.plot_pareto_frontier(df, save_path=str(pareto_path))
                md += f"![Pareto Frontier]({pareto_path})\n\n"
        
        return md
    
    def save_report(
        self,
        report: ExperimentReport,
        format: str = "markdown",
        filename: str | None = None,
    ) -> Path:
        """Save report to file.
        
        Args:
            report: Experiment report
            format: Output format ('markdown', 'json', 'html')
            filename: Optional filename
            
        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "markdown":
            content = self.generate_markdown_report(report)
            ext = "md"
        elif format == "json":
            content = json.dumps(report.to_dict(), indent=2)
            ext = "json"
        elif format == "html":
            md_content = self.generate_markdown_report(report, include_plots=False)
            try:
                import markdown
                content = markdown.markdown(md_content, extensions=["tables"])
                content = f"<html><head><style>table {{border-collapse: collapse;}} th, td {{border: 1px solid #ddd; padding: 8px;}}</style></head><body>{content}</body></html>"
            except ImportError:
                content = f"<html><body><pre>{md_content}</pre></body></html>"
            ext = "html"
        else:
            raise ValueError(f"Unknown format: {format}")
        
        filename = filename or f"experiment_report_{timestamp}.{ext}"
        output_path = self.output_dir / filename
        
        with open(output_path, "w") as f:
            f.write(content)
        
        logger.info(f"Report saved to {output_path}")
        return output_path


# ============================================================================
# Report Builder Helper
# ============================================================================

class ReportBuilder:
    """Fluent builder for creating experiment reports."""
    
    def __init__(self, title: str):
        """Initialize builder with title.
        
        Args:
            title: Report title
        """
        self._report = ExperimentReport(
            title=title,
            description="",
        )
        self._generator = AdvancedReportGenerator()
    
    def with_description(self, description: str) -> "ReportBuilder":
        """Add description."""
        self._report.description = description
        return self
    
    def with_paper(self, paper_id: str) -> "ReportBuilder":
        """Set paper for comparison."""
        self._report.paper_id = paper_id
        return self
    
    def add_result(self, result: QuantizationResult) -> "ReportBuilder":
        """Add a result."""
        self._report.results.append(result)
        return self
    
    def add_finding(self, finding: str) -> "ReportBuilder":
        """Add key finding."""
        self._report.key_findings.append(finding)
        return self
    
    def add_recommendation(self, rec: str) -> "ReportBuilder":
        """Add recommendation."""
        self._report.recommendations.append(rec)
        return self
    
    def add_paper_comparison(self, comparison: dict[str, Any]) -> "ReportBuilder":
        """Add paper comparison."""
        self._report.paper_comparisons.append(comparison)
        return self
    
    def build(self) -> ExperimentReport:
        """Build and return the report."""
        return self._report
    
    def save(self, format: str = "markdown") -> Path:
        """Build and save the report."""
        report = self.build()
        return self._generator.save_report(report, format=format)
