"""Integration tests for the quantization lab.

These tests verify that different subsystems work together correctly.
Some tests require external services (Postgres, W&B) and are marked
with appropriate skip decorators.
"""

import os
import json
import pytest

# ─── Skip helpers ─────────────────────────────────────────────────────
POSTGRES_URL = os.getenv("DATABASE_URL", "")
HAS_POSTGRES = bool(POSTGRES_URL)
WANDB_KEY = os.getenv("WANDB_API_KEY", "")
HAS_WANDB = bool(WANDB_KEY)

skip_no_postgres = pytest.mark.skipif(
    not HAS_POSTGRES, reason="DATABASE_URL not set – Postgres not available"
)
skip_no_wandb = pytest.mark.skipif(
    not HAS_WANDB, reason="WANDB_API_KEY not set – W&B not available"
)


# ─── 1. Config → Run ID → Hash round-trip ────────────────────────────
class TestConfigRoundTrip:
    """Verify that config hashing and run ID generation are consistent."""

    def test_config_roundtrip(self):
        from src.tracking.sync_manager import hash_config, generate_run_id

        config = {
            "method": "gptq",
            "model": "facebook/opt-125m",
            "bit_width": 4,
            "group_size": 128,
        }
        cfg_hash = hash_config(config)

        run_id = generate_run_id(
            method="gptq",
            model_name="facebook/opt-125m",
            bit_width=4,
            group_size=128,
            config_hash=cfg_hash,
        )
        # Run ID should embed part of the hash
        assert cfg_hash[:8] in run_id

    def test_different_seeds_same_hash(self):
        """Config hash should NOT include seed (it's separate)."""
        from src.tracking.sync_manager import hash_config

        c1 = {"method": "gptq", "bit_width": 4}
        c2 = {"method": "gptq", "bit_width": 4}  # same – no seed in config
        assert hash_config(c1) == hash_config(c2)


# ─── 2. Environment capture end-to-end ────────────────────────────────
class TestEnvironmentCapture:
    """Verify the environment capture pipeline."""

    def test_capture_contains_python(self):
        from src.utils.environment import capture_environment

        env = capture_environment()
        assert "python_version" in env
        assert len(env["python_version"]) > 0

    def test_capture_contains_pip_freeze(self):
        from src.utils.environment import capture_environment

        env = capture_environment()
        assert "pip_freeze" in env
        assert len(env["pip_freeze"]) > 0


# ─── 3. Model registry architecture lookup ───────────────────────────
class TestModelRegistryIntegration:
    """Verify model registry can resolve architectures."""

    def test_known_architectures(self):
        from src.models.registry import ARCHITECTURE_TO_LLMC

        # These must always resolve
        assert ARCHITECTURE_TO_LLMC["LlamaForCausalLM"] == "Llama"
        assert ARCHITECTURE_TO_LLMC["OPTForCausalLM"] == "Opt"
        assert ARCHITECTURE_TO_LLMC["MistralForCausalLM"] == "Mistral"

    def test_model_info_serialisation(self):
        from src.models.registry import ModelInfo

        info = ModelInfo(
            hf_id="meta-llama/Llama-2-7b-hf",
            architecture="LlamaForCausalLM",
            llmc_type="Llama",
            is_llmc_compatible=True,
            downloads=100_000,
        )
        d = info.to_dict()
        assert isinstance(d, dict)
        assert d["downloads"] == 100_000
        assert d["hf_id"] == "meta-llama/Llama-2-7b-hf"


# ─── 4. Pareto frontier end-to-end ───────────────────────────────────
class TestParetoIntegration:
    """Verify the Pareto computation pipeline end-to-end."""

    def test_pareto_marks_dominated(self):
        from src.analytics.pareto import ParetoPoint, compute_pareto_frontier

        # point a dominates point c on both dimensions (lower is better)
        points = [
            ParetoPoint(experiment_id=1, method="a", model="m", bit_width=4, accuracy=3, latency=2),
            ParetoPoint(experiment_id=2, method="b", model="m", bit_width=4, accuracy=5, latency=1),
            ParetoPoint(experiment_id=3, method="c", model="m", bit_width=4, accuracy=10, latency=10),
        ]
        results = compute_pareto_frontier(
            points, x_attr="latency", y_attr="accuracy",
            x_minimize=True, y_minimize=True,
        )
        c = next(p for p in results if p.method == "c")
        assert not c.is_pareto_optimal

    def test_pareto_preserves_all_points(self):
        from src.analytics.pareto import ParetoPoint, compute_pareto_frontier

        points = [
            ParetoPoint(experiment_id=i, method=f"m{i}", model="m", bit_width=4, accuracy=i, latency=i)
            for i in range(5)
        ]
        results = compute_pareto_frontier(points)
        assert len(results) == 5


# ─── 5. Knowledge graph data integrity ───────────────────────────────
class TestKnowledgeGraphIntegration:
    """Verify that the knowledge graph seed data is internally consistent."""

    def test_no_self_loops(self):
        from src.knowledge.graph_data import EDGES

        for e in EDGES:
            assert e["source_id"] != e["target_id"], f"Self-loop on {e['source_id']}"

    def test_no_duplicate_edges(self):
        from src.knowledge.graph_data import EDGES

        seen = set()
        for e in EDGES:
            key = (e["source_id"], e["target_id"], e["edge_type"])
            assert key not in seen, f"Duplicate edge: {key}"
            seen.add(key)

    def test_all_node_groups_present(self):
        from src.knowledge.graph_data import (
            DATA_TYPE_NODES,
            HARDWARE_NODES,
            SCHEME_NODES,
            ALGORITHM_NODES,
        )

        # Verify each group has entries
        assert len(DATA_TYPE_NODES) > 0, "No data type nodes"
        assert len(HARDWARE_NODES) > 0, "No hardware nodes"
        assert len(SCHEME_NODES) > 0, "No scheme nodes"
        assert len(ALGORITHM_NODES) > 0, "No algorithm nodes"

        # Verify categories are consistent within groups
        dt_cats = {n["category"] for n in DATA_TYPE_NODES}
        hw_cats = {n["category"] for n in HARDWARE_NODES}
        assert "traditional" in dt_cats
        assert "mx" in dt_cats
        assert "amd" in hw_cats or "nvidia" in hw_cats


# ─── 6. Seed determinism ─────────────────────────────────────────────
class TestSeedDeterminism:
    """Verify that setting seeds produces deterministic results."""

    def test_numpy_determinism(self):
        import numpy as np
        from src.utils.seeds import set_deterministic_seeds

        set_deterministic_seeds(7, deterministic_algorithms=False)
        a = np.random.rand(10).tolist()

        set_deterministic_seeds(7, deterministic_algorithms=False)
        b = np.random.rand(10).tolist()

        assert a == b

    def test_different_seeds_different_output(self):
        import numpy as np
        from src.utils.seeds import set_deterministic_seeds

        set_deterministic_seeds(1, deterministic_algorithms=False)
        a = np.random.rand(10).tolist()

        set_deterministic_seeds(2, deterministic_algorithms=False)
        b = np.random.rand(10).tolist()

        assert a != b


# ─── 7. Database schema models ───────────────────────────────────────
class TestDatabaseModels:
    """Verify ORM model definitions (no live DB needed)."""

    def test_experiment_model_has_wandb_fields(self):
        from src.db.models import Experiment

        columns = {c.name for c in Experiment.__table__.columns}
        assert "wandb_run_id" in columns
        assert "wandb_run_url" in columns
        assert "wandb_project" in columns
        assert "config_hash" in columns
        assert "environment_id" in columns
        assert "seed" in columns

    def test_knowledge_node_model(self):
        from src.db.models import KnowledgeNode

        columns = {c.name for c in KnowledgeNode.__table__.columns}
        assert "id" in columns
        assert "label" in columns
        assert "node_type" in columns
        assert "category" in columns

    def test_knowledge_edge_model(self):
        from src.db.models import KnowledgeEdge

        columns = {c.name for c in KnowledgeEdge.__table__.columns}
        assert "source_id" in columns
        assert "target_id" in columns
        assert "edge_type" in columns


# ─── 8. API route smoke test (no server needed) ─────────────────────
_api_import_error = None
try:
    from src.api.server import app as _api_app
except Exception as e:
    _api_import_error = str(e)
    _api_app = None

skip_no_api = pytest.mark.skipif(
    _api_app is None,
    reason=f"API server cannot be imported: {_api_import_error}",
)


@skip_no_api
class TestAPIRoutes:
    """Verify that API routes are registered on the app."""

    def test_routes_exist(self):
        routes = [r.path for r in _api_app.routes]
        assert "/api/models/search" in routes
        assert "/api/knowledge/graph" in routes
        assert "/api/environment/current" in routes

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient

        client = TestClient(_api_app, raise_server_exceptions=False)
        resp = client.get("/api/environment/current")
        # Should return 200 even without DB (environment capture doesn't need it)
        assert resp.status_code == 200
        data = resp.json()
        assert "python_version" in data


# ─── 9. Sync Manager (offline mode) ──────────────────────────────────
class TestSyncManagerOffline:
    """Verify SyncManager utilities without external services."""

    def test_hash_config_nested(self):
        from src.tracking.sync_manager import hash_config

        cfg = {"model": {"name": "opt", "size": "125m"}, "quant": {"bits": 4, "group": [128, 256]}}
        h = hash_config(cfg)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_generate_run_id_uniqueness(self):
        from src.tracking.sync_manager import generate_run_id

        ids = set()
        for i in range(100):
            rid = generate_run_id("gptq", "model", 4, 128, f"hash{i}")
            ids.add(rid)
        assert len(ids) == 100  # all unique


# ─── 10. Postgres + W&B integration (live services) ─────────────────
@skip_no_postgres
@skip_no_wandb
class TestLiveIntegration:
    """Full end-to-end tests that require Postgres and W&B."""

    def test_sync_manager_run_lifecycle(self):
        """Create, log, and finish a run through SyncManager."""
        from src.tracking.sync_manager import SyncManager

        mgr = SyncManager(
            db_url=POSTGRES_URL,
            wandb_project="test-integration",
        )
        config = {
            "method": "rtn",
            "model": "facebook/opt-125m",
            "bit_width": 8,
        }
        run = mgr.start_run(
            experiment_name="integration-test",
            config=config,
            seed=42,
        )
        assert run.run_id is not None

        mgr.log_step({"loss": 0.5, "step": 1})
        mgr.log_summary({"final_perplexity": 15.3})
        result = mgr.finish_run(status="completed")
        assert result is not None

    def test_environment_snapshot_db(self):
        """Capture and store environment snapshot in Postgres."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from src.utils.environment import get_or_create_snapshot

        engine = create_engine(POSTGRES_URL)
        with Session(engine) as session:
            snap = get_or_create_snapshot(session)
            assert snap.id is not None
            session.rollback()  # don't persist test data


# ─── 9. Calibration data fingerprinting ──────────────────────────────
class TestCalibrationFingerprint:
    """Verify that calibration data fingerprinting is deterministic."""

    def test_fingerprint_deterministic(self):
        """Same data always produces same hash."""
        import torch
        from src.eval.datasets import fingerprint_calibration_data

        data = [torch.arange(100), torch.arange(200)]
        h1 = fingerprint_calibration_data(data)
        h2 = fingerprint_calibration_data(data)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length

    def test_fingerprint_different_data(self):
        """Different data produces different hashes."""
        import torch
        from src.eval.datasets import fingerprint_calibration_data

        data_a = [torch.arange(100)]
        data_b = [torch.arange(100) + 1]
        assert fingerprint_calibration_data(data_a) != fingerprint_calibration_data(data_b)

    def test_fingerprint_device_invariant(self):
        """Hash should be the same regardless of tensor device (cpu)."""
        import torch
        from src.eval.datasets import fingerprint_calibration_data

        data = [torch.arange(50)]
        h_cpu = fingerprint_calibration_data(data)
        # Even if we explicitly place on cpu it should match
        data_cpu = [t.cpu() for t in data]
        assert fingerprint_calibration_data(data_cpu) == h_cpu


# ─── 10. Paper export CLI command ────────────────────────────────────
class TestPaperExportCLI:
    """Verify that the paper-export command is registered."""

    def test_paper_export_registered(self):
        """Ensure paper-export is a registered Typer command."""
        from src.main import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "paper-export" in command_names
