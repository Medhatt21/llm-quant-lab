"""Pareto frontier computation for accuracy-vs-efficiency trade-offs.

Computes Pareto-optimal configurations from experiment data in Postgres,
supporting multiple objective pairs:
- Accuracy vs Latency
- Accuracy vs Memory
- Accuracy vs Model Size
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ParetoPoint:
    """A single point in the Pareto analysis."""

    experiment_id: int
    method: str
    model: str
    bit_width: int
    group_size: int | None = None

    # Objectives
    accuracy: float = 0.0  # higher is better (or lower perplexity)
    latency: float = 0.0  # lower is better (ms)
    memory: float = 0.0  # lower is better (GB)
    model_size_mb: float = 0.0

    is_pareto_optimal: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def compute_pareto_frontier(
    points: list[ParetoPoint],
    x_attr: str = "latency",
    y_attr: str = "accuracy",
    x_minimize: bool = True,
    y_minimize: bool = True,
) -> list[ParetoPoint]:
    """Compute the Pareto frontier from a set of experiment points.

    A point is Pareto-optimal if no other point is strictly better on
    *both* objectives simultaneously.

    Args:
        points: List of ParetoPoint objects.
        x_attr: Attribute name for X axis.
        y_attr: Attribute name for Y axis.
        x_minimize: Whether lower X is better.
        y_minimize: Whether lower Y is better.

    Returns:
        List of ParetoPoint with ``is_pareto_optimal`` set.
    """
    if not points:
        return []

    n = len(points)
    xs = np.array([getattr(p, x_attr) for p in points])
    ys = np.array([getattr(p, y_attr) for p in points])

    # Flip signs if we need to maximise
    sx = xs if x_minimize else -xs
    sy = ys if y_minimize else -ys

    is_optimal = np.ones(n, dtype=bool)
    for i in range(n):
        if not is_optimal[i]:
            continue
        for j in range(n):
            if i == j or not is_optimal[j]:
                continue
            # j dominates i if j is <= on both objectives and < on at least one
            if sx[j] <= sx[i] and sy[j] <= sy[i] and (sx[j] < sx[i] or sy[j] < sy[i]):
                is_optimal[i] = False
                break

    for idx, p in enumerate(points):
        p.is_pareto_optimal = bool(is_optimal[idx])

    optimal = [p for p in points if p.is_pareto_optimal]
    logger.info(f"Pareto frontier: {len(optimal)} optimal out of {n} total points")
    return points


def compute_pareto_from_db(
    db_url: str | None = None,
    accuracy_metric: str = "perplexity",
    accuracy_dataset: str = "wikitext2",
) -> list[ParetoPoint]:
    """Pull experiment results from Postgres and compute Pareto frontier.

    Args:
        db_url: Database URL.
        accuracy_metric: Metric name for accuracy axis.
        accuracy_dataset: Dataset filter.

    Returns:
        Points with Pareto flags set.
    """
    from ..db.models import Experiment, HardwareStat, Metric, QuantConfig, get_session

    session = get_session(db_url)
    points: list[ParetoPoint] = []

    try:
        rows = (
            session.query(
                Experiment.id,
                Experiment.model_name,
                QuantConfig.method_name,
                QuantConfig.bit_width,
                QuantConfig.group_size,
                Metric.value,
                HardwareStat.latency_mean,
                HardwareStat.memory_peak,
                HardwareStat.model_size_mb,
                HardwareStat.quantized_size_mb,
            )
            .join(QuantConfig, Experiment.id == QuantConfig.experiment_id)
            .join(Metric, Experiment.id == Metric.experiment_id)
            .outerjoin(HardwareStat, Experiment.id == HardwareStat.experiment_id)
            .filter(Experiment.status == "completed")
            .filter(Metric.metric_name == accuracy_metric)
            .filter(Metric.dataset == accuracy_dataset)
            .all()
        )

        for row in rows:
            points.append(
                ParetoPoint(
                    experiment_id=row[0],
                    model=row[1],
                    method=row[2],
                    bit_width=row[3],
                    group_size=row[4],
                    accuracy=row[5] or 0.0,
                    latency=row[6] or 0.0,
                    memory=row[7] or 0.0,
                    model_size_mb=row[9] or row[8] or 0.0,
                )
            )
    finally:
        session.close()

    # For perplexity, lower is better
    if accuracy_metric == "perplexity":
        return compute_pareto_frontier(
            points, x_attr="latency", y_attr="accuracy",
            x_minimize=True, y_minimize=True,
        )
    else:
        return compute_pareto_frontier(
            points, x_attr="latency", y_attr="accuracy",
            x_minimize=True, y_minimize=False,
        )
