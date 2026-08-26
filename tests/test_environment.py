"""Tests for environment snapshotting."""

from src.utils.environment import capture_environment


def test_capture_environment():
    """Should capture basic environment info."""
    env = capture_environment()
    assert "python_version" in env
    assert "env_hash" in env
    assert len(env["env_hash"]) == 64  # SHA-256 hex


def test_capture_environment_deterministic():
    """Same environment should produce same hash."""
    env1 = capture_environment()
    env2 = capture_environment()
    assert env1["env_hash"] == env2["env_hash"]
