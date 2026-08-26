"""Cross-hardware comparison analysis.

Compares experiment results across different GPU hardware backends
(CUDA, ROCm) to validate hardware-agnosticity and identify
hardware-specific effects on quantisation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HardwareComparison:
    """Comparison of results between two hardware backends."""

    method: str
    model: str
    bit_width: int

    # Hardware A (e.g., CUDA)
    hw_a_name: str = ""
    hw_a_perplexity: float = 0.0
    hw_a_latency: float = 0.0
    hw_a_memory: float = 0.0

    # Hardware B (e.g., ROCm)
    hw_b_name: str = ""
    hw_b_perplexity: float = 0.0
    hw_b_latency: float = 0.0
    hw_b_memory: float = 0.0

    # Deltas
    perplexity_delta: float = 0.0  # Relative difference
    latency_delta: float = 0.0
    memory_delta: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "model": self.model,
            "bit_width": self.bit_width,
            "hw_a": self.hw_a_name,
            "hw_b": self.hw_b_name,
            "ppl_a": self.hw_a_perplexity,
            "ppl_b": self.hw_b_perplexity,
            "ppl_delta_pct": self.perplexity_delta * 100,
            "latency_a": self.hw_a_latency,
            "latency_b": self.hw_b_latency,
            "latency_delta_pct": self.latency_delta * 100,
        }


def compare_hardware_results(
    db_url: str | None = None,
    hw_a: str = "NVIDIA",
    hw_b: str = "AMD",
    metric_name: str = "perplexity",
    dataset: str = "wikitext2",
) -> list[HardwareComparison]:
    """Pull results from Postgres and compare between hardware backends.

    Matches experiments by (model, method, bit_width) across hardware.
    """
    from ..db.models import Experiment, HardwareStat, Metric, QuantConfig, get_session

    session = get_session(db_url)
    comparisons: list[HardwareComparison] = []

    try:
        rows = (
            session.query(
                Experiment.model_name,
                Experiment.gpu_type,
                QuantConfig.method_name,
                QuantConfig.bit_width,
                QuantConfig.group_size,
                Metric.value,
                HardwareStat.latency_mean,
                HardwareStat.memory_peak,
            )
            .join(QuantConfig, Experiment.id == QuantConfig.experiment_id)
            .join(Metric, Experiment.id == Metric.experiment_id)
            .outerjoin(HardwareStat, Experiment.id == HardwareStat.experiment_id)
            .filter(Experiment.status == "completed")
            .filter(Metric.metric_name == metric_name)
            .filter(Metric.dataset == dataset)
            .all()
        )

        # Group by (model, method, bit_width)
        groups: dict[tuple, dict[str, Any]] = {}
        for row in rows:
            key = (row[0], row[2], row[3])  # model, method, bit_width
            gpu = row[1] or ""
            hw_label = hw_a if hw_a.lower() in gpu.lower() else hw_b if hw_b.lower() in gpu.lower() else "other"
            if hw_label == "other":
                continue
            if key not in groups:
                groups[key] = {}
            groups[key][hw_label] = {
                "perplexity": row[5],
                "latency": row[6],
                "memory": row[7],
                "gpu": gpu,
            }

        # Build comparisons
        for (model, method, bw), hw_data in groups.items():
            if hw_a not in hw_data or hw_b not in hw_data:
                continue
            a = hw_data[hw_a]
            b = hw_data[hw_b]

            ppl_delta = (
                abs(a["perplexity"] - b["perplexity"]) / max(a["perplexity"], 1e-6)
                if a["perplexity"] and b["perplexity"]
                else 0
            )

            comp = HardwareComparison(
                method=method,
                model=model,
                bit_width=bw,
                hw_a_name=a["gpu"],
                hw_a_perplexity=a["perplexity"] or 0,
                hw_a_latency=a["latency"] or 0,
                hw_a_memory=a["memory"] or 0,
                hw_b_name=b["gpu"],
                hw_b_perplexity=b["perplexity"] or 0,
                hw_b_latency=b["latency"] or 0,
                hw_b_memory=b["memory"] or 0,
                perplexity_delta=ppl_delta,
            )
            comparisons.append(comp)

    finally:
        session.close()

    logger.info(f"Cross-hardware comparison: {len(comparisons)} matched experiments")
    return comparisons


def plot_cross_hardware(
    comparisons: list[HardwareComparison],
    output_path: Path = Path("reports/cross_hardware"),
) -> list[Path]:
    """Generate cross-hardware comparison plots."""
    from .paper_plots import _setup_style, _save_fig

    import matplotlib.pyplot as plt

    _setup_style()

    if not comparisons:
        logger.warning("No cross-hardware comparisons to plot")
        return []

    # Scatter plot: HW A perplexity vs HW B perplexity
    fig, ax = plt.subplots()
    ppls_a = [c.hw_a_perplexity for c in comparisons]
    ppls_b = [c.hw_b_perplexity for c in comparisons]

    ax.scatter(ppls_a, ppls_b, alpha=0.7, edgecolors="k", linewidth=0.5)
    lims = [min(min(ppls_a), min(ppls_b)) * 0.9, max(max(ppls_a), max(ppls_b)) * 1.1]
    ax.plot(lims, lims, "k--", alpha=0.4, label="y=x")
    ax.set_xlabel(f"Perplexity ({comparisons[0].hw_a_name})")
    ax.set_ylabel(f"Perplexity ({comparisons[0].hw_b_name})")
    ax.set_title("Cross-Hardware Perplexity Agreement")
    ax.legend()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return _save_fig(fig, output_path)
