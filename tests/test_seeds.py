"""Tests for deterministic seed enforcement."""

import random

from src.utils.seeds import set_deterministic_seeds


def test_set_seeds():
    """Seeds should make random deterministic."""
    set_deterministic_seeds(42, deterministic_algorithms=False)
    a = random.random()
    set_deterministic_seeds(42, deterministic_algorithms=False)
    b = random.random()
    assert a == b


def test_set_seeds_report():
    """set_deterministic_seeds should return a report dict."""
    report = set_deterministic_seeds(123, deterministic_algorithms=False)
    assert report["seed"] == 123
    assert report["python"] is True
    assert report["hash_seed"] is True
