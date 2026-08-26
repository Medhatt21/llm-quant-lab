"""Tests for Pareto frontier computation."""

from src.analytics.pareto import ParetoPoint, compute_pareto_frontier


def test_pareto_frontier_basic():
    """Basic Pareto frontier computation."""
    points = [
        ParetoPoint(experiment_id=1, method="a", model="m", bit_width=4, accuracy=10, latency=5),
        ParetoPoint(experiment_id=2, method="b", model="m", bit_width=4, accuracy=8, latency=3),
        ParetoPoint(experiment_id=3, method="c", model="m", bit_width=4, accuracy=12, latency=10),
    ]

    # Lower is better for both (perplexity, latency)
    result = compute_pareto_frontier(
        points, x_attr="latency", y_attr="accuracy",
        x_minimize=True, y_minimize=True,
    )

    optimal = [p for p in result if p.is_pareto_optimal]
    assert len(optimal) >= 1

    # Point b (accuracy=8, latency=3) should be Pareto-optimal
    b = next(p for p in result if p.method == "b")
    assert b.is_pareto_optimal


def test_pareto_frontier_empty():
    """Empty input should return empty."""
    result = compute_pareto_frontier([])
    assert result == []


def test_pareto_frontier_single():
    """Single point is always Pareto-optimal."""
    points = [ParetoPoint(experiment_id=1, method="a", model="m", bit_width=4, accuracy=10, latency=5)]
    result = compute_pareto_frontier(points)
    assert result[0].is_pareto_optimal
