"""Tests for config hashing and run ID generation."""

from src.tracking.sync_manager import hash_config, generate_run_id


def test_hash_config_deterministic():
    """Same config should always produce the same hash."""
    cfg = {"method": "gptq", "bit_width": 4, "group_size": 128}
    h1 = hash_config(cfg)
    h2 = hash_config(cfg)
    assert h1 == h2


def test_hash_config_order_independent():
    """Key order should not affect the hash."""
    cfg1 = {"a": 1, "b": 2}
    cfg2 = {"b": 2, "a": 1}
    assert hash_config(cfg1) == hash_config(cfg2)


def test_hash_config_different_values():
    """Different configs should produce different hashes."""
    cfg1 = {"bit_width": 4}
    cfg2 = {"bit_width": 8}
    assert hash_config(cfg1) != hash_config(cfg2)


def test_generate_run_id_format():
    """Run IDs should follow the expected format."""
    run_id = generate_run_id("gptq", "facebook/opt-125m", 4, 128, "abc123")
    assert "gptq" in run_id
    assert "opt125m" in run_id
    assert "4b" in run_id
    assert "g128" in run_id
    assert "abc123" in run_id[:50]


def test_generate_run_id_no_group_size():
    """Run ID without group size should use 'gch'."""
    run_id = generate_run_id("rtn", "facebook/opt-125m", 8, None, "xyz")
    assert "gch" in run_id
