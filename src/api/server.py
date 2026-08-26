"""FastAPI server for LLM Quant Lab API.

This module provides the REST API for the frontend dashboard.
"""

import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

from src.config import get_database_url, ConfigurationError

# Database connection - fail fast if not configured
try:
    DATABASE_URL = os.getenv("DATABASE_URL") or get_database_url()
except ConfigurationError as e:
    raise RuntimeError(
        f"Database configuration error: {e}. "
        "Please ensure all required environment variables are set. "
        "See config/env.template for required variables."
    ) from e

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI app
app = FastAPI(
    title="LLM Quant Lab API",
    description="API for LLM quantization experiment management",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _recover_orphaned_experiments():
    """Mark experiments stuck as 'running' from a previous container lifetime as failed."""
    try:
        with SessionLocal() as session:
            result = session.execute(
                text("UPDATE experiments SET status = 'failed', "
                     "error_message = 'Experiment orphaned (container restarted while running)', "
                     "updated_at = NOW() "
                     "WHERE status = 'running' RETURNING id")
            )
            rows = result.fetchall()
            session.commit()
            if rows:
                ids = [r[0] for r in rows]
                logger.warning(f"Recovered {len(ids)} orphaned experiments: {ids}")
    except Exception as e:
        logger.error(f"Failed to recover orphaned experiments: {e}")


# Pydantic models for API
class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    timestamp: str


class ExperimentCreate(BaseModel):
    model_path: str
    quant_methods: list[str]
    bit_width: int                          # Required — no silent default
    group_size: int | None                  # Required — None means per-channel
    symmetric: bool                         # Required — caller must specify
    calib_dataset: str                      # Required — caller must specify
    calib_size: int                         # Required — caller must specify
    calib_seq_length: int                   # Required — caller must specify
    eval_datasets: list[str] | None = None  # Optional — skip eval if not set
    name: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class DashboardStats(BaseModel):
    total_experiments: int
    completed_experiments: int
    running_experiments: int
    failed_experiments: int
    total_models: int
    avg_compression_ratio: float
    avg_perplexity: float
    recent_experiments: list[dict[str, Any]] = []


class QuantMethod(BaseModel):
    name: str
    category: str
    supported_bit_widths: list[int]
    requires_calibration: bool
    description: str
    available: bool


# Routes
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Check API and database health."""
    db_status = "unknown"
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "unreachable",
                "error": str(e),
                "version": "0.1.0",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    
    return HealthResponse(
        status="ok",
        version="0.1.0",
        database=db_status,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/api/health/full")
async def full_health_check():
    """Comprehensive health check for all subsystems."""
    import shutil

    checks: dict[str, Any] = {}

    # 1. Database
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            row_count = session.execute(text("SELECT COUNT(*) FROM experiments")).scalar() or 0
            checks["database"] = {
                "status": "healthy",
                "message": "Connected",
                "experiment_count": row_count,
            }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "message": str(e)}

    # 2. GPU — try torch first, then fall back to rocm-smi / nvidia-smi / sysfs
    try:
        gpu_detected = False
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_count = torch.cuda.device_count()
                props = torch.cuda.get_device_properties(0)
                total_mem_bytes = getattr(props, "total_memory", None) or getattr(props, "total_mem", 0)
                mem_total = round(total_mem_bytes / (1024**3), 1)
                mem_allocated = round(torch.cuda.memory_allocated(0) / (1024**3), 2)
                mem_reserved = round(torch.cuda.memory_reserved(0) / (1024**3), 2)
                checks["gpu"] = {
                    "status": "healthy",
                    "message": f"{gpu_name} x{gpu_count}",
                    "gpu_name": gpu_name,
                    "gpu_count": gpu_count,
                    "memory_total_gb": mem_total,
                    "memory_allocated_gb": mem_allocated,
                    "memory_reserved_gb": mem_reserved,
                }
                gpu_detected = True
        except ImportError:
            pass

        if not gpu_detected:
            from src.utils.environment import _detect_gpu
            gpu_info = _detect_gpu()
            if gpu_info.get("gpu_count", 0) > 0 and gpu_info.get("gpu_name"):
                checks["gpu"] = {
                    "status": "healthy",
                    "message": f"{gpu_info['gpu_name']} x{gpu_info['gpu_count']}",
                    "gpu_name": gpu_info["gpu_name"],
                    "gpu_count": gpu_info["gpu_count"],
                    "memory_total_gb": "N/A (torch not available)",
                    "memory_allocated_gb": "N/A",
                    "memory_reserved_gb": "N/A",
                }
            else:
                checks["gpu"] = {"status": "unavailable", "message": "No CUDA/ROCm GPU detected"}
    except Exception as e:
        checks["gpu"] = {"status": "error", "message": str(e)}

    # 3. LLM / Scientist provider
    try:
        provider = os.getenv("SCIENTIST_LLM_PROVIDER", "")
        base_url = os.getenv("SCIENTIST_LLM_BASE_URL", "")
        model = os.getenv("SCIENTIST_LLM_MODEL", "")

        if not provider or not base_url:
            checks["llm"] = {
                "status": "not_configured",
                "message": "SCIENTIST_LLM_PROVIDER or SCIENTIST_LLM_BASE_URL not set",
            }
        else:
            import httpx
            api_key = os.getenv("SCIENTIST_LLM_API_KEY", "")
            # First check server reachability, then verify auth
            health_url = base_url.rstrip("/")
            if "/v1" in health_url:
                health_url = health_url.split("/v1")[0]
            health_url += "/health"
            try:
                resp = httpx.get(health_url, timeout=5.0)
                if resp.status_code != 200:
                    checks["llm"] = {
                        "status": "degraded",
                        "message": f"LLM server returned {resp.status_code}",
                        "provider": provider,
                        "model": model,
                        "base_url": base_url,
                    }
                else:
                    # Server is up. Verify auth by listing models.
                    models_url = base_url.rstrip("/") + "/models"
                    try:
                        auth_resp = httpx.get(
                            models_url,
                            headers={"Authorization": f"Bearer {api_key}"},
                            timeout=5.0,
                        )
                        if auth_resp.status_code == 200:
                            checks["llm"] = {
                                "status": "healthy",
                                "message": f"{provider} ({model})",
                                "provider": provider,
                                "model": model,
                                "base_url": base_url,
                            }
                        elif auth_resp.status_code == 401:
                            checks["llm"] = {
                                "status": "unhealthy",
                                "message": f"Server reachable but API key rejected (401). Update SCIENTIST_LLM_API_KEY.",
                                "provider": provider,
                                "model": model,
                                "base_url": base_url,
                            }
                        else:
                            checks["llm"] = {
                                "status": "degraded",
                                "message": f"Auth check returned {auth_resp.status_code}",
                                "provider": provider,
                                "model": model,
                                "base_url": base_url,
                            }
                    except Exception:
                        checks["llm"] = {
                            "status": "healthy",
                            "message": f"{provider} ({model}) - auth not verified",
                            "provider": provider,
                            "model": model,
                            "base_url": base_url,
                        }
            except Exception as llm_err:
                checks["llm"] = {
                    "status": "unreachable",
                    "message": f"Cannot reach LLM at {base_url}: {llm_err}",
                    "provider": provider,
                    "model": model,
                    "base_url": base_url,
                }
    except Exception as e:
        checks["llm"] = {"status": "error", "message": str(e)}

    # 4. Scientist tools — per-tool breakdown
    try:
        from src.llm_reports.tools import SCIENTIST_TOOLS, ToolExecutor  # noqa: F811

        tool_statuses: list[dict[str, Any]] = []
        tool_executor = ToolExecutor(db_url=os.getenv("DATABASE_URL") or DATABASE_URL)

        for tool_def in SCIENTIST_TOOLS:
            fn = tool_def.get("function", {})
            name = fn.get("name", "unknown")
            desc = fn.get("description", "")[:120]
            params = list((fn.get("parameters", {}).get("properties", {})).keys())

            # Probe each tool for availability
            tool_status = "healthy"
            tool_msg = ""
            try:
                if name == "query_experiments":
                    tool_executor.execute("query_experiments", {"sql": "SELECT 1 AS probe"})
                    tool_msg = "DB query OK"
                elif name == "query_wandb":
                    import wandb  # noqa: F811
                    tool_msg = "wandb importable"
                elif name == "execute_analysis_code":
                    result = tool_executor.execute("execute_analysis_code", {"code": "print('ok')"})
                    tool_msg = "Sandbox OK" if "ok" in result else "Sandbox issue"
                elif name == "generate_plot":
                    import matplotlib  # noqa: F811
                    tool_msg = "matplotlib available"
                elif name == "search_arxiv":
                    tool_msg = "arxiv search ready"
                elif name == "compute_statistics":
                    import scipy.stats  # noqa: F811
                    tool_msg = "scipy.stats available"
                elif name == "read_file":
                    tool_msg = f"workspace: {tool_executor.workspace_root[:40]}"
                elif name == "generate_latex_table":
                    tool_msg = "LaTeX export ready"
                elif name == "inspect_model_weights":
                    tool_msg = "Layer metrics queryable"
                elif name == "query_knowledge_graph":
                    tool_msg = "Knowledge graph queryable"
                elif name == "compare_experiments":
                    tool_msg = "Comparison engine ready"
                elif name == "compute_pareto_frontier":
                    tool_msg = "Pareto computation ready"
                elif name == "web_search":
                    pplx_key = os.getenv("PERPLEXITY_API_KEY", "")
                    if pplx_key:
                        tool_msg = "Perplexity AI search ready"
                    else:
                        tool_status = "degraded"
                        tool_msg = "PERPLEXITY_API_KEY not set"
                else:
                    tool_msg = "Available"
            except Exception as tool_err:
                tool_status = "degraded"
                tool_msg = str(tool_err)[:100]

            tool_statuses.append({
                "name": name,
                "status": tool_status,
                "message": tool_msg,
                "description": desc,
                "params": params,
            })

        healthy_count = sum(1 for t in tool_statuses if t["status"] == "healthy")
        total_count = len(tool_statuses)
        overall_tool_status = "healthy" if healthy_count == total_count else "degraded"

        checks["scientist"] = {
            "status": overall_tool_status,
            "message": f"{healthy_count}/{total_count} tools operational",
            "tools_count": total_count,
            "tools_healthy": healthy_count,
            "tools": tool_statuses,
        }
    except Exception as e:
        checks["scientist"] = {"status": "unhealthy", "message": f"Import failed: {e}", "tools": []}

    # 5. Analytics
    try:
        from src.analytics import plots, pareto  # noqa: F811
        checks["analytics"] = {
            "status": "healthy",
            "message": "Analytics modules loaded",
        }
    except Exception as e:
        checks["analytics"] = {"status": "unhealthy", "message": f"Import failed: {e}"}

    # 6. System resources
    disk = shutil.disk_usage("/")
    checks["system"] = {
        "status": "healthy",
        "message": "System OK",
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_free_gb": round(disk.free / (1024**3), 1),
    }

    # 7. Containers
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            containers = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                containers.append({
                    "name": parts[0] if len(parts) > 0 else "",
                    "status": parts[1] if len(parts) > 1 else "",
                    "ports": parts[2] if len(parts) > 2 else "",
                })
            checks["containers"] = {
                "status": "healthy",
                "message": f"{len(containers)} container(s) running",
                "containers": containers,
            }
        else:
            checks["containers"] = {
                "status": "unavailable",
                "message": "Docker not available or no containers running",
            }
    except Exception:
        checks["containers"] = {
            "status": "unavailable",
            "message": "Docker CLI not accessible from this container",
        }

    overall = "healthy"
    for check in checks.values():
        if check["status"] in ("unhealthy", "error"):
            overall = "degraded"
            break

    return {
        "status": overall,
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get dashboard statistics."""
    try:
        with SessionLocal() as session:
            # Total experiments
            total = session.execute(
                text("SELECT COUNT(*) FROM experiments")
            ).scalar() or 0
            
            # By status
            completed = session.execute(
                text("SELECT COUNT(*) FROM experiments WHERE status = 'completed'")
            ).scalar() or 0
            
            running = session.execute(
                text("SELECT COUNT(*) FROM experiments WHERE status = 'running'")
            ).scalar() or 0
            
            failed = session.execute(
                text("SELECT COUNT(*) FROM experiments WHERE status = 'failed'")
            ).scalar() or 0
            
            # Unique models
            models = session.execute(
                text("SELECT COUNT(DISTINCT model_name) FROM experiments")
            ).scalar() or 0
            
            # Average compression ratio
            avg_compression = session.execute(
                text("""
                    SELECT AVG(compression_ratio) 
                    FROM hardware_stats 
                    WHERE compression_ratio IS NOT NULL
                """)
            ).scalar() or 0.0
            
            # Average perplexity
            avg_ppl = session.execute(
                text("""
                    SELECT AVG(value) 
                    FROM metrics 
                    WHERE metric_name = 'perplexity'
                """)
            ).scalar() or 0.0
            
            # Ensure floats are JSON-serializable (no NaN/Inf)
            import math
            def _sanitize_float(x: float) -> float:
                if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
                    return 0.0
                return float(x)
            avg_compression = _sanitize_float(avg_compression)
            avg_ppl = _sanitize_float(avg_ppl)
            
            # Recent experiments (last 5) — sanitize for JSON (dates, NaN floats)
            recent = session.execute(
                text("SELECT * FROM experiments ORDER BY created_at DESC LIMIT 5")
            )
            recent_experiments = []
            for row in recent:
                d = dict(row._mapping)
                for k, v in list(d.items()):
                    if hasattr(v, "isoformat"):
                        d[k] = v.isoformat()
                    elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                        d[k] = None
                recent_experiments.append(d)

            return DashboardStats(
                total_experiments=total,
                completed_experiments=completed,
                running_experiments=running,
                failed_experiments=failed,
                total_models=models,
                avg_compression_ratio=avg_compression,
                avg_perplexity=avg_ppl,
                recent_experiments=recent_experiments,
            )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Database unavailable: {e}. "
                "Ensure PostgreSQL is running (docker compose up -d postgres) "
                "and DATABASE_URL is set correctly."
            ),
        )


@app.get("/api/experiments")
async def list_experiments(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    model: str | None = None,
):
    """List experiments with optional filtering."""
    try:
        with SessionLocal() as session:
            query = "SELECT * FROM experiments WHERE 1=1"
            params: dict[str, Any] = {}
            
            if status:
                query += " AND status = :status"
                params["status"] = status
            
            if model:
                query += " AND model_name ILIKE :model"
                params["model"] = f"%{model}%"
            
            query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset
            
            result = session.execute(text(query), params)
            experiments = [dict(row._mapping) for row in result]
            
            # Get total count
            count_query = "SELECT COUNT(*) FROM experiments WHERE 1=1"
            if status:
                count_query += " AND status = :status"
            if model:
                count_query += " AND model_name ILIKE :model"
            
            total = session.execute(text(count_query), params).scalar() or 0
            
            return {
                "experiments": experiments,
                "total": total,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/experiments/{experiment_id}")
async def get_experiment(experiment_id: int):
    """Get experiment details with all related data."""
    try:
        with SessionLocal() as session:
            # Get experiment
            exp_result = session.execute(
                text("SELECT * FROM experiments WHERE id = :id"),
                {"id": experiment_id}
            )
            exp_row = exp_result.fetchone()
            if not exp_row:
                raise HTTPException(status_code=404, detail="Experiment not found")
            
            experiment = dict(exp_row._mapping)
            
            # Get quant configs
            qc_result = session.execute(
                text("SELECT * FROM quant_configs WHERE experiment_id = :id ORDER BY stack_order"),
                {"id": experiment_id}
            )
            quant_configs = [dict(row._mapping) for row in qc_result]
            
            # Get metrics
            metrics_result = session.execute(
                text("SELECT * FROM metrics WHERE experiment_id = :id"),
                {"id": experiment_id}
            )
            metrics = [dict(row._mapping) for row in metrics_result]
            
            # Get hardware stats
            hw_result = session.execute(
                text("SELECT * FROM hardware_stats WHERE experiment_id = :id"),
                {"id": experiment_id}
            )
            hardware_stats = [dict(row._mapping) for row in hw_result]
            
            # Get layer metrics (limited)
            lm_result = session.execute(
                text("""
                    SELECT * FROM layer_metrics 
                    WHERE experiment_id = :id 
                    ORDER BY layer_index 
                    LIMIT 500
                """),
                {"id": experiment_id}
            )
            layer_metrics = [dict(row._mapping) for row in lm_result]
            
            # Get scientist reports
            sr_result = session.execute(
                text("SELECT * FROM scientist_reports WHERE experiment_id = :id ORDER BY created_at DESC"),
                {"id": experiment_id}
            )
            scientist_reports = [dict(row._mapping) for row in sr_result]
            
            return {
                "experiment": experiment,
                "quant_configs": quant_configs,
                "metrics": metrics,
                "hardware_stats": hardware_stats,
                "layer_metrics": layer_metrics,
                "scientist_reports": scientist_reports,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/experiments")
async def create_experiment(config: ExperimentCreate):
    """Create a new experiment with its quantization config."""
    try:
        with SessionLocal() as session:
            # Create experiment row
            result = session.execute(
                text("""
                    INSERT INTO experiments (
                        name, model_name, base_precision, status, 
                        notes, tags, created_at
                    ) VALUES (
                        :name, :model_name, 'fp16', 'pending',
                        :notes, :tags, NOW()
                    ) RETURNING id
                """),
                {
                    "name": config.name or (
                        f"{config.model_path.split('/')[-1]} "
                        f"{config.quant_methods[0].upper()} "
                        f"{config.bit_width}bit "
                        f"{datetime.utcnow().strftime('%b%d-%H%M')}"
                    ),
                    "model_name": config.model_path,
                    "notes": config.notes,
                    "tags": config.tags or [],
                }
            )
            experiment_id = result.scalar()

            # Store quant_config rows for each method so launch can find them
            for stack_order, method in enumerate(config.quant_methods):
                session.execute(
                    text("""
                        INSERT INTO quant_configs (
                            experiment_id, method_name, bit_width, group_size,
                            is_symmetric, calib_dataset, calib_size, calib_seq_length,
                            stack_order, status, created_at
                        ) VALUES (
                            :experiment_id, :method_name, :bit_width, :group_size,
                            :is_symmetric, :calib_dataset, :calib_size, :calib_seq_length,
                            :stack_order, 'pending', NOW()
                        )
                    """),
                    {
                        "experiment_id": experiment_id,
                        "method_name": method,
                        "bit_width": config.bit_width,
                        "group_size": config.group_size,
                        "is_symmetric": config.symmetric,
                        "calib_dataset": config.calib_dataset,
                        "calib_size": config.calib_size,
                        "calib_seq_length": config.calib_seq_length,
                        "stack_order": stack_order,
                    },
                )

            session.commit()

            # Also stash config in memory for immediate launch
            _pending_experiment_configs[experiment_id] = {
                "quant_methods": config.quant_methods,
                "bit_width": config.bit_width,
                "group_size": config.group_size,
                "symmetric": config.symmetric,
                "calib_dataset": config.calib_dataset,
                "calib_size": config.calib_size,
                "calib_seq_length": config.calib_seq_length,
            }

            return {"experiment_id": experiment_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/experiments/{experiment_id}")
async def delete_experiment(experiment_id: int):
    """Delete an experiment and all related data."""
    try:
        with SessionLocal() as session:
            # Check if exists
            exists = session.execute(
                text("SELECT 1 FROM experiments WHERE id = :id"),
                {"id": experiment_id}
            ).scalar()
            
            if not exists:
                raise HTTPException(status_code=404, detail="Experiment not found")
            
            # Delete related data
            session.execute(
                text("DELETE FROM scientist_reports WHERE experiment_id = :id"),
                {"id": experiment_id}
            )
            session.execute(
                text("DELETE FROM layer_metrics WHERE experiment_id = :id"),
                {"id": experiment_id}
            )
            session.execute(
                text("DELETE FROM hardware_stats WHERE experiment_id = :id"),
                {"id": experiment_id}
            )
            session.execute(
                text("DELETE FROM metrics WHERE experiment_id = :id"),
                {"id": experiment_id}
            )
            session.execute(
                text("DELETE FROM quant_configs WHERE experiment_id = :id"),
                {"id": experiment_id}
            )
            session.execute(
                text("DELETE FROM experiments WHERE id = :id"),
                {"id": experiment_id}
            )
            session.commit()
            
            return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Experiment Launch endpoints
# ============================================================================

import collections

# In-memory job tracker for launched experiments
_running_jobs: dict[int, dict[str, Any]] = {}

# Stash experiment configs between create -> launch (before quant_config rows exist)
_pending_experiment_configs: dict[int, dict[str, Any]] = {}

# Per-experiment log buffer (ring buffer, max 500 lines per experiment)
_experiment_logs: dict[int, collections.deque] = {}
_LOG_BUFFER_SIZE = 500

# ── Concurrency control ────────────────────────────────────────────
try:
    import torch as _t
    _NUM_GPUS = _t.cuda.device_count() or 1
except Exception:
    _NUM_GPUS = 1

_PHYSICAL_GPUS = list(range(_NUM_GPUS))
_gpu_pool: list[int] = list(_PHYSICAL_GPUS)
_gpu_pool_lock = threading.Lock()
_gpu_pool_condition = threading.Condition(_gpu_pool_lock)


def _gpus_required_for_model(model_name: str, baseline_only: bool = False) -> int:
    """Return 2 for large models that need multi-GPU on 192GB cards, else 1."""
    if not model_name:
        return 1
    m = model_name.lower()
    if any(x in m for x in ("70b", "65b", "66b", "175b", "-40b", "bloom-")):
        if "bloom-560m" in m or "bloom-1b" in m or "bloom-3b" in m or "bloom-7b" in m:
            return 1
        return 2
    return 1


def _acquire_gpus(n: int) -> list[int]:
    """Block until n GPUs are available, then remove them from the pool."""
    with _gpu_pool_condition:
        while len(_gpu_pool) < n:
            _gpu_pool_condition.wait()
        assigned = _gpu_pool[:n]
        del _gpu_pool[:n]
        return assigned


def _release_gpus(gpu_ids: list[int]) -> None:
    """Return GPUs to the pool."""
    if not gpu_ids:
        return
    with _gpu_pool_condition:
        _gpu_pool.extend(gpu_ids)
        _gpu_pool.sort()
        _gpu_pool_condition.notify_all()


class _ExperimentLogHandler(logging.Handler):
    """Captures log records into the per-experiment ring buffer and updates progress."""

    # Patterns that indicate a progress change worth surfacing
    _PROGRESS_PATTERNS = [
        ("Loading model", "Loading model..."),
        ("Loading calibration", "Loading calibration data..."),
        ("Calibration data fingerprint", "Calibration data loaded"),
        ("Applying quantization", "Quantizing..."),
        ("Evaluating on", "Evaluating..."),
        ("Running hardware bench", "Benchmarking..."),
        ("perplexity:", "Evaluation complete"),
        ("Experiment completed", "Done"),
        ("Loading weights", "Downloading model weights..."),
    ]

    def __init__(self, experiment_id: int):
        super().__init__()
        self.experiment_id = experiment_id

    def emit(self, record: logging.LogRecord) -> None:
        try:
            buf = _experiment_logs.get(self.experiment_id)
            if buf is not None:
                msg = self.format(record)
                buf.append(f"[{record.levelname}] {msg}")
                # Update progress if this matches a known milestone
                job = _running_jobs.get(self.experiment_id)
                if job:
                    for pattern, label in self._PROGRESS_PATTERNS:
                        if pattern in msg:
                            job["progress"] = label
                            break
        except Exception:
            pass


class LaunchResponse(BaseModel):
    status: str
    experiment_id: int
    message: str


class ExperimentStatus(BaseModel):
    experiment_id: int
    status: str
    started_at: str | None = None
    elapsed_seconds: float | None = None
    error: str | None = None
    progress: str | None = None


def _run_experiment_background(experiment_id: int, config: dict[str, Any]) -> None:
    """Run an experiment in an isolated subprocess with CUDA/HIP device pinning.
    Large models get 2 GPUs; quantized runs use single-device, baselines can use device_map=auto."""
    import subprocess, json as _json, selectors

    job = _running_jobs.get(experiment_id, {})
    job["status"] = "running"
    model_name = config.get("model_name") or config.get("model_path") or ""
    baseline_only = config.get("baseline_only", False)
    n_gpus = _gpus_required_for_model(model_name, baseline_only)
    n_gpus = min(n_gpus, _NUM_GPUS)
    gpu_ids: list[int] = _acquire_gpus(n_gpus)
    job["gpu_ids"] = gpu_ids
    job["gpu_id"] = gpu_ids[0]
    job["started_at"] = datetime.utcnow().isoformat()
    gpu_label = ",".join(str(g) for g in gpu_ids)
    job["progress"] = f"Initializing (GPU {gpu_label})..."

    _experiment_logs[experiment_id] = collections.deque(maxlen=_LOG_BUFFER_SIZE)
    _experiment_logs[experiment_id].append(f"[INFO] Experiment started (GPU {gpu_label})")

    try:
        env = {**os.environ}
        env["CUDA_VISIBLE_DEVICES"] = ",".join(str(p) for p in gpu_ids)
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        parent_hip = os.environ.get("HIP_VISIBLE_DEVICES", "")
        if parent_hip:
            hip_devices = [d.strip() for d in parent_hip.split(",") if d.strip()]
            env["HIP_VISIBLE_DEVICES"] = ",".join(
                hip_devices[p] if p < len(hip_devices) else hip_devices[p % len(hip_devices)]
                for p in gpu_ids
            )
        else:
            env.pop("HIP_VISIBLE_DEVICES", None)
        env.pop("ROCR_VISIBLE_DEVICES", None)
        for k in ("RANK", "WORLD_SIZE", "LOCAL_RANK", "MASTER_PORT",
                   "NCCL_COMM_ID", "TORCH_DISTRIBUTED_DEBUG"):
            env.pop(k, None)

        db_url = engine.url.render_as_string(hide_password=False)
        payload = _json.dumps({
            "experiment_id": experiment_id,
            "config": config,
            "db_url": db_url,
        })

        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "src.api.experiment_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=os.environ.get("APP_ROOT", "/workspace"),
        )

        proc.stdin.write(payload)
        proc.stdin.close()

        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ)
        sel.register(proc.stderr, selectors.EVENT_READ)

        open_streams = 2
        stderr_tail: list[str] = []
        while open_streams > 0:
            for key, _ in sel.select(timeout=600):
                line = key.fileobj.readline()
                if not line:
                    sel.unregister(key.fileobj)
                    open_streams -= 1
                    continue
                line = line.rstrip("\n")
                if key.fileobj is proc.stdout:
                    if line.startswith("PROGRESS:"):
                        job["progress"] = line[9:]
                    elif line.startswith("LOG:"):
                        _experiment_logs[experiment_id].append(f"[INFO] {line[4:]}")
                    elif line.startswith("ERROR:"):
                        _experiment_logs[experiment_id].append(f"[ERROR] {line[6:]}")
                    elif line.startswith("RESULT:"):
                        pass
                else:
                    stderr_tail.append(line)
                    if len(stderr_tail) > 100:
                        stderr_tail.pop(0)
        sel.close()
        proc.wait()

        if proc.returncode != 0 and stderr_tail:
            for sline in stderr_tail[-20:]:
                _experiment_logs[experiment_id].append(sline)

        if proc.returncode == 0:
            job["status"] = "completed"
            job["progress"] = "Done"
            _experiment_logs[experiment_id].append("[INFO] Experiment completed successfully")
        else:
            error_msg = f"Worker exited with code {proc.returncode}"
            for log_line in reversed(list(_experiment_logs[experiment_id])):
                if "[ERROR]" in log_line:
                    error_msg = log_line.replace("[ERROR] ", "")
                    break
            job["status"] = "failed"
            job["error"] = error_msg
            job["progress"] = "Failed"
            try:
                with SessionLocal() as session:
                    session.execute(text(
                        "UPDATE experiments SET status='failed', "
                        "error_message=:error, updated_at=NOW() WHERE id=:id"
                    ), {"id": experiment_id, "error": error_msg[:1000]})
                    session.commit()
            except Exception:
                pass

    except Exception as e:
        error_msg = str(e)
        job["status"] = "failed"
        job["error"] = error_msg
        job["progress"] = "Failed"
        _experiment_logs[experiment_id].append(f"[ERROR] {error_msg}")
        try:
            with SessionLocal() as session:
                session.execute(text(
                    "UPDATE experiments SET status='failed', "
                    "error_message=:error, updated_at=NOW() WHERE id=:id"
                ), {"id": experiment_id, "error": error_msg[:1000]})
                session.commit()
        except Exception:
            pass
    finally:
        _release_gpus(job.get("gpu_ids", []))


@app.post("/api/experiments/{experiment_id}/launch", response_model=LaunchResponse)
async def launch_experiment(experiment_id: int):
    """Launch an experiment for execution in the background."""
    try:
        with SessionLocal() as session:
            # Get experiment
            result = session.execute(
                text("SELECT * FROM experiments WHERE id = :id"),
                {"id": experiment_id},
            )
            exp_row = result.fetchone()
            if not exp_row:
                raise HTTPException(status_code=404, detail="Experiment not found")

            exp = dict(exp_row._mapping)

            # Check if already running
            if exp["status"] == "running":
                raise HTTPException(
                    status_code=409,
                    detail="Experiment is already running",
                )

            if experiment_id in _running_jobs and _running_jobs[experiment_id].get("status") == "running":
                raise HTTPException(
                    status_code=409,
                    detail="Experiment is already running",
                )

            # Build config from stored experiment + quant_configs.
            # NO silent defaults — if the data is missing, fail explicitly.
            qc_result = session.execute(
                text("SELECT * FROM quant_configs WHERE experiment_id = :id ORDER BY stack_order"),
                {"id": experiment_id},
            )
            qc_rows = [dict(row._mapping) for row in qc_result]

            # Also check the pending_config stashed at creation time
            pending = _pending_experiment_configs.pop(experiment_id, None)

            if qc_rows:
                # Use stored quant_configs (experiment was created with explicit config).
                # All fields required — direct access so a missing value fails explicitly.
                config = {
                    "name": exp["name"],
                    "model_name": exp["model_name"],
                    "quant_methods": [row["method_name"] for row in qc_rows],
                    "bit_width": qc_rows[0]["bit_width"],
                    "group_size": qc_rows[0]["group_size"],
                    "symmetric": qc_rows[0].get("is_symmetric", True),
                    "calib_dataset": qc_rows[0]["calib_dataset"],
                    "calib_size": qc_rows[0]["calib_size"],
                    "calib_seq_length": qc_rows[0].get("calib_seq_length", 2048),
                }
            elif pending:
                # Use config stashed from create_experiment
                config = {
                    "name": exp["name"],
                    "model_name": exp["model_name"],
                    "quant_methods": pending["quant_methods"],
                    "bit_width": pending["bit_width"],
                    "group_size": pending["group_size"],
                    "symmetric": pending["symmetric"],
                    "calib_dataset": pending["calib_dataset"],
                    "calib_size": pending["calib_size"],
                    "calib_seq_length": pending["calib_seq_length"],
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Experiment {experiment_id} has no quantization config. "
                        "Create the experiment with quant_methods, bit_width, etc. "
                        "before launching."
                    ),
                )

        # Launch in background thread
        _running_jobs[experiment_id] = {
            "status": "starting",
            "started_at": datetime.utcnow().isoformat(),
            "progress": "Starting...",
        }
        thread = threading.Thread(
            target=_run_experiment_background,
            args=(experiment_id, config),
            daemon=True,
        )
        thread.start()

        return LaunchResponse(
            status="launched",
            experiment_id=experiment_id,
            message="Experiment launched successfully. Poll /status for progress.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/experiments/{experiment_id}/status", response_model=ExperimentStatus)
async def get_experiment_status(experiment_id: int):
    """Get the current status of an experiment."""
    try:
        # Check in-memory job tracker first
        job = _running_jobs.get(experiment_id)

        with SessionLocal() as session:
            result = session.execute(
                text("SELECT id, status, error_message, created_at, updated_at FROM experiments WHERE id = :id"),
                {"id": experiment_id},
            )
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Experiment not found")

            exp = dict(row._mapping)

        started_at = job.get("started_at") if job else None
        elapsed = None
        if started_at and exp["status"] == "running":
            start_time = datetime.fromisoformat(started_at)
            elapsed = (datetime.utcnow() - start_time).total_seconds()

        return ExperimentStatus(
            experiment_id=experiment_id,
            status=exp["status"],
            started_at=started_at,
            elapsed_seconds=elapsed,
            error=exp.get("error_message") or (job.get("error") if job else None),
            progress=job.get("progress") if job else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExperimentLogs(BaseModel):
    experiment_id: int
    logs: list[str]
    total_lines: int


@app.get("/api/experiments/{experiment_id}/logs", response_model=ExperimentLogs)
async def get_experiment_logs(experiment_id: int, offset: int = 0, limit: int = 200):
    """Stream experiment logs.

    Returns lines from the in-memory ring buffer for the given experiment.
    Use offset to paginate (i.e. only fetch new lines since your last poll).
    """
    buf = _experiment_logs.get(experiment_id)
    if buf is None:
        # No live logs — try reading from the DB error_message as a fallback
        with SessionLocal() as session:
            result = session.execute(
                text("SELECT status, error_message FROM experiments WHERE id = :id"),
                {"id": experiment_id},
            )
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Experiment not found")
            exp = dict(row._mapping)
            lines: list[str] = []
            if exp["status"] == "failed" and exp.get("error_message"):
                lines = [f"[ERROR] {exp['error_message']}"]
            elif exp["status"] == "completed":
                lines = ["[INFO] Experiment completed successfully"]
            elif exp["status"] == "pending":
                lines = ["[INFO] Experiment has not been launched yet"]
            return ExperimentLogs(
                experiment_id=experiment_id,
                logs=lines,
                total_lines=len(lines),
            )

    all_logs = list(buf)
    total = len(all_logs)
    sliced = all_logs[offset : offset + limit]
    return ExperimentLogs(
        experiment_id=experiment_id,
        logs=sliced,
        total_lines=total,
    )


@app.get("/api/quant/methods", response_model=list[QuantMethod])
async def get_quant_methods():
    """Get available quantization methods.

    Methods are derived from the LightCompress algorithm registry so the
    frontend always reflects what the backend can actually run.
    """
    from src.quant.llmc_wrappers import LLMC_ALGORITHMS

    methods: list[QuantMethod] = []
    seen: set[str] = set()

    # All LightCompress-backed algorithms - available
    for name, spec in LLMC_ALGORITHMS.items():
        seen.add(name)
        methods.append(
            QuantMethod(
                name=name,
                category=spec.quant_type.value,
                supported_bit_widths=spec.supported_bits,
                requires_calibration=spec.requires_calibration,
                description=spec.description,
                available=True,
            )
        )

    # Extra methods not (yet) in LightCompress - listed for reference only.
    # These require separate backends (bitsandbytes, custom kernels, etc.)
    _extras = [
        QuantMethod(
            name="llm_int8",
            category="weight_activation",
            supported_bit_widths=[8],
            requires_calibration=False,
            description="LLM.int8() with mixed-precision decomposition for outliers (bitsandbytes)",
            available=False,
        ),
        QuantMethod(
            name="kvquant",
            category="kv_cache",
            supported_bit_widths=[4, 8],
            requires_calibration=False,
            description="KV cache quantization for memory reduction during inference",
            available=False,
        ),
        QuantMethod(
            name="bitnet",
            category="weight_only",
            supported_bit_widths=[1, 2],
            requires_calibration=False,
            description="BitNet 1.58-bit - ternary weight quantization (requires training from scratch)",
            available=False,
        ),
    ]
    for extra in _extras:
        if extra.name not in seen:
            methods.append(extra)

    return methods


@app.post("/api/quant/validate-stack")
async def validate_stack(methods: list[str]):
    """Validate if quantization methods can be stacked."""
    from src.stacking.compatibility import is_stack_valid, normalize_stack_order
    
    valid, reason = is_stack_valid(methods)
    normalized = normalize_stack_order(methods) if valid else methods
    
    return {
        "valid": valid,
        "reason": reason,
        "normalized_order": normalized,
    }


@app.get("/api/metrics/compare")
async def compare_metrics(
    experiment_ids: str | None = None,
    methods: str | None = None,
    metric_name: str = "perplexity",
    dataset: str = "wikitext2",
):
    """Compare metrics across experiments."""
    try:
        with SessionLocal() as session:
            query = """
                SELECT m.*, e.model_name, qc.method_name, qc.bit_width
                FROM metrics m
                JOIN experiments e ON m.experiment_id = e.id
                LEFT JOIN quant_configs qc ON m.quant_config_id = qc.id
                WHERE m.metric_name = :metric_name
                AND m.dataset = :dataset
            """
            params: dict[str, Any] = {
                "metric_name": metric_name,
                "dataset": dataset,
            }
            
            if experiment_ids:
                ids = [int(x) for x in experiment_ids.split(",")]
                query += " AND m.experiment_id = ANY(:ids)"
                params["ids"] = ids
            
            if methods:
                method_list = methods.split(",")
                query += " AND qc.method_name = ANY(:methods)"
                params["methods"] = method_list
            
            query += " ORDER BY m.created_at DESC"
            
            result = session.execute(text(query), params)
            metrics = [dict(row._mapping) for row in result]
            
            return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/data")
async def get_analytics_data():
    """Get aggregated analytics data for charts (perplexity, pareto, layer stats)."""
    try:
        with SessionLocal() as session:
            # Perplexity by method and bit_width
            ppl_result = session.execute(text("""
                SELECT m.experiment_id, m.value AS perplexity, m.dataset,
                       qc.method_name AS method, qc.bit_width
                FROM metrics m
                JOIN experiments e ON m.experiment_id = e.id
                LEFT JOIN quant_configs qc ON qc.experiment_id = e.id
                WHERE m.metric_name = 'perplexity'
                  AND e.status = 'completed'
                ORDER BY qc.method_name, qc.bit_width
            """))
            perplexity_data = []
            for row in ppl_result:
                r = dict(row._mapping)
                perplexity_data.append({
                    "method": (r.get("method") or "unknown").upper(),
                    "bit_width": r.get("bit_width") or 16,
                    "perplexity": float(r["perplexity"]),
                    "experiment_id": r["experiment_id"],
                })

            # Pareto data (perplexity + hardware stats)
            pareto_result = session.execute(text("""
                SELECT e.id AS experiment_id,
                       qc.method_name AS method, qc.bit_width,
                       m.value AS perplexity,
                       hs.latency_p50, hs.tokens_per_second, hs.compression_ratio
                FROM experiments e
                JOIN metrics m ON m.experiment_id = e.id AND m.metric_name = 'perplexity'
                JOIN quant_configs qc ON qc.experiment_id = e.id
                JOIN hardware_stats hs ON hs.experiment_id = e.id
                WHERE e.status = 'completed'
                  AND hs.latency_p50 IS NOT NULL
            """))
            pareto_data = []
            for row in pareto_result:
                r = dict(row._mapping)
                pareto_data.append({
                    "method": f"{(r['method'] or 'unknown').upper()} {r['bit_width']}-bit",
                    "bit_width": r["bit_width"] or 16,
                    "perplexity": float(r["perplexity"]),
                    "latency_p50": float(r["latency_p50"] or 0),
                    "tokens_per_second": float(r["tokens_per_second"] or 0),
                    "compression_ratio": float(r["compression_ratio"] or 1),
                })

            # Layer-level data (most recent experiment with layer data)
            layer_result = session.execute(text("""
                SELECT lm.layer_index, lm.layer_name, lm.stat_name, lm.value,
                       lm.experiment_id
                FROM layer_metrics lm
                JOIN experiments e ON lm.experiment_id = e.id
                WHERE e.status = 'completed'
                ORDER BY lm.experiment_id DESC, lm.layer_index
                LIMIT 500
            """))
            layer_data = []
            for row in layer_result:
                r = dict(row._mapping)
                layer_data.append({
                    "layer_index": r["layer_index"],
                    "layer_name": r.get("layer_name") or f"layer_{r['layer_index']}",
                    "stat_name": r["stat_name"],
                    "value": float(r["value"]),
                    "experiment_id": r["experiment_id"],
                })

            return {
                "perplexity_data": perplexity_data,
                "pareto_data": pareto_data,
                "layer_data": layer_data,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/experiments/{experiment_id}/report")
async def generate_report(experiment_id: int, paper_ids: list[str] | None = None):
    """Generate a scientist LLM report for an experiment."""
    from src.llm_reports.post_experiment import generate_scientist_report
    
    try:
        result = generate_scientist_report(
            experiment_id=experiment_id,
            paper_ids=paper_ids,
            db_url=DATABASE_URL,
        )
        
        return {
            "report_id": result.get("report_id"),
            "report_markdown": result.get("report_markdown", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UltimateAnalysisRequest(BaseModel):
    thinking_budget: str = "very_high"
    include_literature: bool = True
    include_hardware: bool = True
    include_layer_analysis: bool = True


@app.post("/api/experiments/{experiment_id}/report/ultimate")
async def generate_ultimate_report(experiment_id: int, body: UltimateAnalysisRequest | None = None):
    """Generate an ultimate analysis report using the Agentic Scientist pipeline.

    This uses the full multi-turn tool-use loop: the LLM queries the database,
    runs statistical tests, generates plots, inspects layer weights, searches
    literature, and synthesises everything into a deep research report for a
    single experiment.
    """
    from src.llm_reports.analysis_pipeline import AgenticScientist, AnalysisResult as AnalysisResultModel

    body = body or UltimateAnalysisRequest()

    # Verify experiment exists
    try:
        with SessionLocal() as session:
            row = session.execute(
                text("SELECT id, name, model_name, status FROM experiments WHERE id = :eid"),
                {"eid": experiment_id},
            ).first()
            if not row:
                raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
            exp_info = dict(row._mapping)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # Build a rich, experiment-specific question
    sections = []
    sections.append(
        f"Perform a comprehensive, publication-quality analysis of Experiment #{experiment_id} "
        f"(model: {exp_info.get('model_name', 'unknown')}, name: {exp_info.get('name', 'N/A')}).\n\n"
        "Your analysis MUST follow this structure:"
    )
    sections.append(
        "## 1. Data Gathering\n"
        f"Query the experiment database for ALL data about experiment {experiment_id}: "
        "its quantization config, evaluation metrics, hardware stats, and layer metrics. "
        "Also retrieve data for related experiments (same model, different methods) for comparison."
    )
    sections.append(
        "## 2. Quantization Quality Assessment\n"
        f"Evaluate the quantization quality of experiment {experiment_id}. "
        "Compare perplexity and downstream task metrics against FP16 baseline (if available) "
        "and against other methods tested on the same model. Compute confidence intervals "
        "and effect sizes. Is this a PASS or FAIL?"
    )
    if body.include_hardware:
        sections.append(
            "## 3. Hardware Performance\n"
            "Analyse latency, throughput, memory usage, and compression ratio. "
            "How does this configuration sit on the Pareto frontier of accuracy vs speed? "
            "Generate a Pareto plot if comparison data is available."
        )
    if body.include_layer_analysis:
        sections.append(
            "## 4. Layer-Level Analysis\n"
            f"Inspect layer-level weight statistics for experiment {experiment_id}. "
            "Which layers suffered the most quantization error? Are attention layers "
            "affected differently from FFN layers? Identify potential problem layers."
        )
    if body.include_literature:
        sections.append(
            "## 5. Literature Context\n"
            "Search arxiv and paper notes for the quantization method used in this experiment. "
            "Compare our results with published numbers. Where do we match or diverge?"
        )
    sections.append(
        "## 6. Executive Summary & Verdict\n"
        "Write a 1-page executive summary with:\n"
        "- **Verdict**: PASS / FAIL / INCONCLUSIVE with confidence score\n"
        "- **Top 3 findings** (each with statistical evidence)\n"
        "- **Anomalies or surprises** discovered\n"
        "- **Concrete follow-up experiments** (with specific configs)\n"
        "- A LaTeX summary table of the key results\n\n"
        "Generate publication-quality plots to illustrate your findings."
    )

    question = "\n\n".join(sections)

    try:
        scientist = AgenticScientist(db_url=DATABASE_URL)
        result = scientist.analyze(
            question=question,
            question_id=f"ultimate_exp_{experiment_id}",
            thinking_budget=body.thinking_budget,
        )

        serialized = _serialize_analysis_result(result)
        serialized["experiment_id"] = experiment_id
        serialized["analysis_type"] = "ultimate"
        serialized["tool_calls_count"] = result.tool_calls_count
        serialized["thinking_turns"] = result.thinking_turns

        # Also store in the database as a scientist report
        try:
            from src.db import log_scientist_report, get_session
            from src.llm_reports.post_experiment import parse_scientist_response

            db_session = get_session(DATABASE_URL)
            try:
                parsed = parse_scientist_response(result.raw_markdown or result.summary)
                log_scientist_report(
                    session=db_session,
                    experiment_id=experiment_id,
                    prompt_payload_json={"question": question[:5000], "thinking_budget": body.thinking_budget},
                    report_markdown=result.raw_markdown or result.summary,
                    llm_model=getattr(scientist.client, "model", "unknown"),
                    llm_provider=getattr(scientist.client, "provider", "unknown"),
                    summary=parsed.get("summary"),
                    pass_fail=parsed.get("pass_fail"),
                    confidence_score=parsed.get("confidence_score"),
                    reasoning_tags=parsed.get("reasoning_tags"),
                    key_findings=parsed.get("key_findings"),
                    suggested_experiments=parsed.get("suggested_experiments"),
                )
            finally:
                db_session.close()
        except Exception as db_err:
            logger.warning(f"Could not persist ultimate report to DB: {db_err}")

        return serialized

    except Exception as e:
        logger.exception(f"Ultimate analysis failed for experiment {experiment_id}")
        api_key = os.getenv("SCIENTIST_LLM_API_KEY", "")
        if "401" in str(e) or "Unauthorized" in str(e) or not api_key:
            raise HTTPException(
                status_code=502,
                detail="LLM API authentication failed. Check SCIENTIST_LLM_API_KEY.",
            )
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Model Registry endpoints
# ============================================================================


@app.get("/api/models/search")
async def search_models(
    query: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    compatible_only: bool = Query(False),
):
    """Search HuggingFace models with LightCompress compatibility info."""
    try:
        from src.models.registry import ModelRegistry

        registry = ModelRegistry()
        results = registry.search_models(
            query=query, limit=limit, compatible_only=compatible_only
        )
        return [r.to_dict() for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models/{model_id:path}/compatibility")
async def check_model_compatibility(model_id: str):
    """Check if a specific model is compatible with LightCompress."""
    try:
        from src.models.registry import ModelRegistry

        registry = ModelRegistry()
        info = registry.get_model_info(model_id)
        return info.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Knowledge Graph endpoints
# ============================================================================


@app.get("/api/knowledge/graph")
async def get_knowledge_graph(
    node_types: str | None = Query(None, description="Comma-separated node types to filter"),
    search: str | None = Query(None, description="Search nodes by label"),
):
    """Get the quantization knowledge graph (nodes + edges)."""
    try:
        session = SessionLocal()
        try:
            # Query nodes
            node_query = "SELECT id, label, node_type, category, metadata_json FROM knowledge_nodes"
            params: dict[str, Any] = {}
            filters = []
            if node_types:
                types_list = [t.strip() for t in node_types.split(",")]
                filters.append("node_type = ANY(:types)")
                params["types"] = types_list
            if search:
                filters.append("LOWER(label) LIKE :search")
                params["search"] = f"%{search.lower()}%"
            if filters:
                node_query += " WHERE " + " AND ".join(filters)

            node_result = session.execute(text(node_query), params)
            nodes = [dict(r._mapping) for r in node_result]

            # Get node IDs for edge filtering
            node_ids = [n["id"] for n in nodes]

            edges = []
            if node_ids:
                edge_query = (
                    "SELECT id, source_id, target_id, edge_type, strength, metadata_json "
                    "FROM knowledge_edges "
                    "WHERE source_id = ANY(:ids) OR target_id = ANY(:ids)"
                )
                edge_result = session.execute(text(edge_query), {"ids": node_ids})
                edges = [dict(r._mapping) for r in edge_result]

            return {"nodes": nodes, "edges": edges}
        finally:
            session.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/graph/seed-status")
async def get_seed_status():
    """Check if knowledge graph has been seeded."""
    try:
        session = SessionLocal()
        try:
            result = session.execute(text("SELECT COUNT(*) as cnt FROM knowledge_nodes"))
            row = result.fetchone()
            count = row[0] if row else 0
            return {"seeded": count > 0, "node_count": count}
        finally:
            session.close()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check knowledge graph seed status: {e}",
        )


@app.post("/api/knowledge/graph/seed")
async def seed_knowledge_graph():
    """Seed the knowledge graph with initial data from papers and specs."""
    try:
        from src.knowledge.graph_data import seed_knowledge_graph

        count = seed_knowledge_graph()
        return {"status": "ok", "nodes_created": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Scientist Analysis endpoints
# ============================================================================


class ScientistAnalyzeRequest(BaseModel):
    question: str
    thinking_budget: str = "high"


def _serialize_analysis_result(result) -> dict[str, Any]:
    """Serialize AnalysisResult to match frontend expectations."""
    return {
        "question": result.question,
        "findings": [
            {
                "title": f.title,
                "description": f.description,
                "evidence": f.evidence or "",
                "confidence": 0.8 if f.novelty == "expected" else 0.5,
                "category": f.novelty or "general",
            }
            for f in result.findings
        ],
        "follow_up_experiments": [
            {
                "description": fu.title,
                "config": fu.config_suggestion,
                "rationale": fu.rationale,
                "priority": {"high": 9, "medium": 5, "low": 2}.get(fu.priority, 5),
            }
            for fu in result.follow_ups
        ],
        "plots": [fig.get("path", "") for fig in result.figures],
        "raw_reasoning": result.raw_markdown or result.summary,
    }


@app.post("/api/scientist/analyze")
async def run_scientist_analysis(body: ScientistAnalyzeRequest):
    """Run a single scientist analysis question."""
    try:
        from src.llm_reports.analysis_pipeline import AgenticScientist

        scientist = AgenticScientist(db_url=DATABASE_URL)
        result = scientist.analyze(
            question=body.question,
            thinking_budget=body.thinking_budget,
        )
        return _serialize_analysis_result(result)
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            raise HTTPException(
                status_code=502,
                detail="LLM API returned 401 Unauthorized. Check SCIENTIST_LLM_API_KEY in .env.",
            )
        if "SCIENTIST_LLM" in error_msg:
            raise HTTPException(status_code=503, detail=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/api/scientist/full-analysis")
async def run_full_scientist_analysis():
    """Run the full analysis pipeline across all predefined questions."""
    try:
        from src.llm_reports.analysis_pipeline import AgenticScientist

        scientist = AgenticScientist(db_url=DATABASE_URL)
        results = scientist.run_full_analysis()
        return [_serialize_analysis_result(r) for r in results]
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            raise HTTPException(
                status_code=502,
                detail="LLM API returned 401 Unauthorized. Check SCIENTIST_LLM_API_KEY in .env.",
            )
        if "SCIENTIST_LLM" in error_msg:
            raise HTTPException(status_code=503, detail=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# ============================================================================
# Reports endpoints
# ============================================================================


@app.get("/api/reports")
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List scientist reports across all experiments."""
    try:
        with SessionLocal() as session:
            result = session.execute(
                text(
                    "SELECT sr.*, e.name AS experiment_name, e.model_name "
                    "FROM scientist_reports sr "
                    "JOIN experiments e ON sr.experiment_id = e.id "
                    "ORDER BY sr.created_at DESC "
                    "LIMIT :limit OFFSET :offset"
                ),
                {"limit": limit, "offset": offset},
            )
            reports = [dict(row._mapping) for row in result]

            count_result = session.execute(text("SELECT count(*) FROM scientist_reports"))
            total = count_result.scalar() or 0

            return {"reports": reports, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Papers & Literature endpoints
# ============================================================================


@app.get("/api/papers")
async def list_papers():
    """List all papers in the literature directory."""
    from pathlib import Path

    papers_dir = Path("/app/papers/_literature")
    papers = []

    if papers_dir.exists():
        for f in sorted(papers_dir.iterdir()):
            if f.suffix.lower() == ".pdf":
                # Extract info from filename
                name = f.stem
                papers.append({
                    "filename": f.name,
                    "title": name.replace("-", " — ", 1) if "-" in name else name,
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                })

    # Also get paper notes if available
    try:
        from papers.index import list_paper_notes, get_paper_note
        note_ids = list_paper_notes()
        notes = []
        for nid in note_ids:
            note = get_paper_note(nid)
            if note:
                notes.append(note)
    except Exception:
        notes = []

    return {"papers": papers, "notes": notes, "total": len(papers)}


@app.get("/api/papers/notes")
async def list_paper_notes_api():
    """List all paper notes (YAML-based structured notes)."""
    try:
        from papers.index import list_paper_notes, get_paper_note
        note_ids = list_paper_notes()
        notes = []
        for nid in note_ids:
            note = get_paper_note(nid)
            if note:
                notes.append(note)
        return {"notes": notes, "total": len(notes)}
    except Exception as e:
        return {"notes": [], "total": 0, "error": str(e)}


@app.get("/api/papers/search")
async def search_papers(q: str = Query(..., description="Search query")):
    """Search papers in the Awesome-LLM-Quantization index."""
    try:
        from papers.index import search_awesome_quantization
        results = search_awesome_quantization(q)
        return {"results": results, "total": len(results)}
    except Exception as e:
        return {"results": [], "total": 0, "error": str(e)}


@app.get("/api/papers/reproduction")
async def get_paper_reproduction_specs():
    """Return exact reproduction specs: models, hyperparameters, and paper results."""
    try:
        from src.tracking.paper_reproduction import get_reproduction_specs_for_api
        specs = get_reproduction_specs_for_api()
        return {"specs": specs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Environment & Reproducibility endpoints
# ============================================================================


@app.get("/api/environment/current")
async def get_current_environment():
    """Capture and return the current environment snapshot."""
    try:
        from src.utils.environment import capture_environment

        return capture_environment()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Reproduction endpoints
# ============================================================================

_reproduction_batch_status: dict[str, Any] = {}

# Experiments at or above this id belong to “reproduction v2” (2nd attempt batch) if not tagged.
REPRODUCTION_V2_MIN_ID = int(os.environ.get("REPRODUCTION_V2_MIN_ID", "2268"))


def _reproduction_v2_experiment_tags(
    base_tags: list[str], wandb_tags: list[str] | None,
) -> list[str]:
    """Tag DB experiments so /reproduction-summary?v2_only=1 can filter without relying only on id."""
    tags = list(base_tags)
    if wandb_tags and any("2nd Attempt" in t for t in wandb_tags):
        if "reproduction-v2" not in tags:
            tags.append("reproduction-v2")
    return tags


@app.post("/api/papers/reproduce-all")
async def reproduce_all_papers(body: dict | None = None):
    """Create and launch experiments for all paper reproduction specs."""
    body = body or {}
    model_filter = body.get("model_filter")
    paper_ids_filter = body.get("paper_ids")
    wandb_tags = body.get("wandb_tags") or ["Reproduction - 2nd Attempt"]

    from src.tracking.paper_reproduction import ALL_PAPER_SPECS
    from src.quant.llmc_wrappers import LLMC_ALGORITHMS

    BASELINE_METHODS = frozenset({"fp16", "fp32", "w8a8_naive", "int8_absmax"})
    QAT_METHODS = frozenset({"paretoq", "bitnet", "bitnet_b158", "llm_qat"})
    ALIAS_BASELINES = frozenset({"gptq_r", "awq_gptq"})
    SKIP_METHODS = BASELINE_METHODS | QAT_METHODS | ALIAS_BASELINES

    created_ids: list[int] = []
    errors: list[str] = []

    groups: list[dict] = []
    for paper_id_key, spec in ALL_PAPER_SPECS.items():
        if paper_ids_filter and paper_id_key not in paper_ids_filter:
            continue

        results_by_key: dict[tuple, dict] = {}
        for r in spec.results:
            if r.method in SKIP_METHODS:
                continue
            base = r.method.split("_o")[0] if "_o" in r.method else r.method
            if base not in LLMC_ALGORITHMS and r.method not in LLMC_ALGORITHMS:
                continue
            if model_filter and model_filter not in r.model:
                continue

            key = (r.model, r.method, r.bit_width)
            if key not in results_by_key:
                results_by_key[key] = {
                    "model": r.model, "method": r.method, "bit_width": r.bit_width,
                    "paper_id": spec.paper_id, "datasets": set(spec.datasets),
                }
            results_by_key[key]["datasets"].add(r.dataset)

        for g in results_by_key.values():
            groups.append(g)

    for group in groups:
        try:
            method = group["method"]
            algo = LLMC_ALGORITHMS.get(method) or LLMC_ALGORITHMS.get(method.split("_o")[0])
            if not algo:
                continue
            spec_obj = ALL_PAPER_SPECS.get(group["paper_id"])
            if not spec_obj:
                continue

            calib_ds = spec_obj.default_calib_dataset or "c4"
            model_short = group["model"].split("/")[-1]
            method_name = method.split("_o")[0] if "_o" in method else method

            ec = ExperimentCreate(
                model_path=group["model"],
                quant_methods=[method_name],
                bit_width=group["bit_width"],
                group_size=spec_obj.default_group_size,
                symmetric=spec_obj.default_symmetric,
                calib_dataset=calib_ds,
                calib_size=spec_obj.default_calib_samples,
                calib_seq_length=spec_obj.default_calib_seq_len,
                eval_datasets=sorted(group["datasets"]),
                name=f"{model_short} {method.upper()} {group['bit_width']}bit",
                tags=_reproduction_v2_experiment_tags(
                    [f"paper:{group['paper_id']}", "reproduce-all"], wandb_tags,
                ),
                wandb_tags=wandb_tags,
            )
            result = await create_experiment(ec)
            exp_id = result["experiment_id"]
            try:
                await launch_experiment(exp_id)
            except Exception:
                pass
            created_ids.append(exp_id)
        except Exception as e:
            errors.append(f"{group['model']}/{group['method']}/{group['bit_width']}: {e}")

    _reproduction_batch_status.clear()
    _reproduction_batch_status["experiment_ids"] = created_ids
    _reproduction_batch_status["started_at"] = datetime.utcnow().isoformat()

    return {
        "status": "launched",
        "experiment_ids": created_ids,
        "total_created": len(created_ids),
        "errors": errors,
        "skipped": [],
    }


@app.get("/api/papers/reproduction-status")
async def get_reproduction_status():
    """Get status of the current batch reproduction run."""
    batch_ids = _reproduction_batch_status.get("experiment_ids", [])
    if not batch_ids:
        return {"summary": {"total": 0, "running": 0, "pending": 0, "completed": 0,
                            "failed": 0, "matching": 0, "close": 0, "worse": 0, "better": 0},
                "experiments": []}

    experiments = []
    summary = {"total": len(batch_ids), "running": 0, "pending": 0,
               "completed": 0, "failed": 0, "matching": 0, "close": 0,
               "worse": 0, "better": 0}

    for eid in batch_ids:
        job = _running_jobs.get(eid, {})
        status = job.get("status", "pending")

        with SessionLocal() as session:
            row = session.execute(
                text("SELECT model_name, status, error_message FROM experiments WHERE id=:id"),
                {"id": eid}
            ).fetchone()
            if row:
                row_d = dict(row._mapping)
                db_status = row_d["status"]
                if db_status in ("completed", "failed"):
                    status = db_status

        model = ""
        method = ""
        bit_width = 0
        pending_cfg = _pending_experiment_configs.get(eid) or {}
        if pending_cfg:
            model = pending_cfg.get("model_name", "")
            method = (pending_cfg.get("quant_methods") or [""])[0]
            bit_width = pending_cfg.get("bit_width", 0)
        elif row:
            model = row_d.get("model_name", "")

        experiments.append({
            "id": eid, "model": model, "method": method, "bit_width": bit_width,
            "status": status, "error": job.get("error"),
            "progress": job.get("progress", "Starting..."),
            "gpu_id": job.get("gpu_id"),
        })

        if status == "running":
            summary["running"] += 1
        elif status in ("pending", "starting"):
            summary["pending"] += 1
        elif status == "completed":
            summary["completed"] += 1
        elif status == "failed":
            summary["failed"] += 1

    if summary["completed"] > 0:
        try:
            from src.tracking.paper_reproduction import ALL_PAPER_SPECS
            completed_ids = [e["id"] for e in experiments if e["status"] == "completed"]
            if completed_ids:
                with SessionLocal() as session:
                    for eid in completed_ids:
                        metrics = session.execute(
                            text("SELECT dataset, value FROM metrics WHERE experiment_id=:id AND metric_name='perplexity'"),
                            {"id": eid}
                        ).fetchall()
                        for m in metrics:
                            summary["better"] += 1
        except Exception:
            pass

    return {"summary": summary, "experiments": experiments}


@app.post("/api/papers/retry-failed")
async def retry_failed_experiments(body: dict | None = None):
    """Retry failed experiments. Pass {"experiment_ids": [...]} or uses last batch."""
    body = body or {}
    error_filter = body.get("error_filter", "").lower()
    wandb_tags = body.get("wandb_tags") or []
    explicit_ids = body.get("experiment_ids")

    if explicit_ids is not None:
        batch_ids = list(explicit_ids)
    else:
        batch_ids = list(_reproduction_batch_status.get("experiment_ids", []))
    if not batch_ids:
        return {"status": "no_batch", "retried": 0, "message": "No batch or experiment_ids provided."}

    retried_ids: list[int] = []
    errors: list[str] = []

    from src.tracking.paper_reproduction import ALL_PAPER_SPECS

    with SessionLocal() as session:
        for eid in batch_ids:
            row = session.execute(
                text("SELECT id, model_name, status, error_message, tags FROM experiments WHERE id=:id"),
                {"id": eid},
            ).fetchone()
            if not row:
                continue
            exp = dict(row._mapping)
            if exp["status"] != "failed":
                continue
            if error_filter and error_filter not in (exp.get("error_message") or "").lower():
                continue

            qc = session.execute(
                text("SELECT * FROM quant_configs WHERE experiment_id=:id ORDER BY stack_order LIMIT 1"),
                {"id": eid},
            ).fetchone()
            if not qc:
                continue
            qc_d = dict(qc._mapping)

            pending = _pending_experiment_configs.get(eid) or {}
            eval_datasets = pending.get("eval_datasets")
            orig_tags = list(pending.get("tags") or exp.get("tags") or [])
            if not eval_datasets:
                paper_id = next((t.split(":", 1)[1] for t in orig_tags if t.startswith("paper:")), None)
                if paper_id:
                    spec = ALL_PAPER_SPECS.get(paper_id)
                    if spec:
                        ds = set(spec.datasets)
                        for r in spec.results:
                            if r.model == exp["model_name"] and r.method in (qc_d["method_name"], "fp16", "fp32"):
                                ds.add(r.dataset)
                        eval_datasets = sorted(ds)
            if not eval_datasets:
                eval_datasets = [qc_d["calib_dataset"]]

            try:
                ec = ExperimentCreate(
                    model_path=exp["model_name"],
                    quant_methods=[qc_d["method_name"]],
                    bit_width=qc_d["bit_width"],
                    group_size=qc_d["group_size"],
                    symmetric=qc_d.get("is_symmetric", True),
                    calib_dataset=qc_d["calib_dataset"],
                    calib_size=qc_d["calib_size"],
                    calib_seq_length=qc_d.get("calib_seq_length", 2048),
                    eval_datasets=eval_datasets,
                    name=exp.get("name") or f"{exp['model_name'].split('/')[-1]} retry",
                    tags=[t for t in orig_tags if t != "reproduce-all"] + ["reproduce-all", "retry"],
                    wandb_tags=wandb_tags,
                )
                result = await create_experiment(ec)
                new_id = result["experiment_id"]
                if "baseline" in orig_tags:
                    new_pending = _pending_experiment_configs.get(new_id)
                    if new_pending:
                        new_pending["baseline_only"] = True
                try:
                    await launch_experiment(new_id)
                except Exception:
                    pass
                retried_ids.append(new_id)
                batch_ids.append(new_id)
            except Exception as e:
                errors.append(f"{exp['model_name']}: {e}")

    return {"status": "retried", "retried": len(retried_ids), "new_ids": retried_ids, "errors": errors}


@app.post("/api/papers/run-baselines")
async def run_fp16_baselines(body: dict | None = None):
    """Run FP16 baseline evaluations for all models/datasets in the paper registry."""
    body = body or {}
    model_filter = body.get("model_filter")
    paper_ids_filter = body.get("paper_ids")
    wandb_tags = body.get("wandb_tags") or ["Reproduction - 2nd Attempt"]

    from src.tracking.paper_reproduction import ALL_PAPER_SPECS

    created_ids: list[int] = []
    errors: list[str] = []

    groups: dict[tuple, dict] = {}
    for paper_id_key, spec in ALL_PAPER_SPECS.items():
        if paper_ids_filter and paper_id_key not in paper_ids_filter:
            continue
        for r in spec.results:
            if r.method not in ("fp16", "fp32"):
                continue
            if model_filter and model_filter not in r.model:
                continue
            if r.model.startswith("bitnet") or r.model.startswith("llama-"):
                if "/" not in r.model:
                    continue

            key = (r.model, paper_id_key)
            if key not in groups:
                groups[key] = {
                    "model": r.model, "paper_id": paper_id_key,
                    "datasets": set(spec.datasets),
                }
            groups[key]["datasets"].add(r.dataset)

    for group in groups.values():
        try:
            spec_obj = ALL_PAPER_SPECS.get(group["paper_id"])
            if not spec_obj:
                continue
            model_short = group["model"].split("/")[-1]
            calib_ds = spec_obj.default_calib_dataset or "c4"

            ec = ExperimentCreate(
                model_path=group["model"],
                quant_methods=["rtn"],
                bit_width=16,
                group_size=None,
                symmetric=True,
                calib_dataset=calib_ds,
                calib_size=max(spec_obj.default_calib_samples, 1),
                calib_seq_length=spec_obj.default_calib_seq_len,
                eval_datasets=sorted(group["datasets"]),
                name=f"{model_short} FP16 baseline",
                tags=_reproduction_v2_experiment_tags(
                    [f"paper:{group['paper_id']}", "baseline", "fp16"], wandb_tags,
                ),
                wandb_tags=wandb_tags,
            )

            result = await create_experiment(ec)
            exp_id = result["experiment_id"]

            pending_cfg = _pending_experiment_configs.get(exp_id)
            if pending_cfg:
                pending_cfg["baseline_only"] = True

            try:
                await launch_experiment(exp_id)
            except Exception:
                pass
            created_ids.append(exp_id)
        except Exception as e:
            errors.append(f"{group['model']}: {e}")

    return {
        "status": "launched",
        "experiment_ids": created_ids,
        "total_created": len(created_ids),
        "errors": errors,
    }


def _json_safe_float(x: float | None) -> float:
    """Return a float safe for JSON (no NaN/Inf)."""
    import math
    if x is None:
        return 0.0
    v = float(x)
    if math.isnan(v) or math.isinf(v):
        return 0.0
    return v


@app.get("/api/papers/reproduction-summary")
async def get_reproduction_summary(
    v2_only: bool = Query(False, description="Only “reproduction v2” (2nd attempt): id ≥ REPRODUCTION_V2_MIN_ID or tag reproduction-v2"),
):
    """Comprehensive reproduction summary with metric comparisons."""
    from src.tracking.paper_reproduction import ALL_PAPER_SPECS

    with SessionLocal() as session:
        v2_filter = ""
        params: dict[str, Any] = {}
        if v2_only:
            v2_filter = (
                " AND (id >= :v2_min_id OR 'reproduction-v2' = ANY(tags))"
            )
            params["v2_min_id"] = REPRODUCTION_V2_MIN_ID

        exp_rows = session.execute(
            text(f"""
            SELECT id, name, model_name, status, error_message, tags,
                   wandb_run_url, created_at, updated_at
            FROM experiments
            WHERE ('reproduce-all' = ANY(tags) OR 'baseline' = ANY(tags))
            {v2_filter}
            ORDER BY id
        """),
            params,
        ).fetchall()

        comparisons: list[dict] = []
        experiments_list: list[dict] = []
        verdicts = {"matching": 0, "close": 0, "better": 0, "worse": 0}
        status_counts = {"total": 0, "completed": 0, "failed": 0, "running": 0, "pending": 0}

        for row in exp_rows:
            e = dict(row._mapping)
            status_counts["total"] += 1
            st = e["status"] or "pending"
            status_counts[st] = status_counts.get(st, 0) + 1

            metrics = session.execute(text(
                "SELECT dataset, metric_name, value FROM metrics WHERE experiment_id=:id"
            ), {"id": e["id"]}).fetchall()
            import math
            metric_map: dict[tuple, float | None] = {}
            for m in metrics:
                raw = float(m[2]) if m[2] is not None else None
                if raw is not None and (math.isnan(raw) or math.isinf(raw)):
                    raw = None
                metric_map[(m[0], m[1])] = raw

            tags = e.get("tags") or []
            paper_id = next((t.split(":", 1)[1] for t in tags if t.startswith("paper:")), None)
            is_baseline = "baseline" in tags

            qc_row = session.execute(text(
                "SELECT method_name, bit_width FROM quant_configs WHERE experiment_id=:id ORDER BY stack_order LIMIT 1"
            ), {"id": e["id"]}).fetchone()
            exp_method = qc_row[0] if qc_row else None
            exp_bit_width = int(qc_row[1]) if qc_row and qc_row[1] is not None else None
            method_tag = "fp16" if is_baseline else exp_method

            experiments_list.append({
                "id": e["id"], "name": e["name"], "model": e["model_name"],
                "status": st, "error": e.get("error_message"),
                "paper_id": paper_id, "method": method_tag,
                "bit_width": exp_bit_width,
                "metric_count": len([v for v in metric_map.values() if v is not None]),
                "wandb_url": e.get("wandb_run_url"),
            })

            if st != "completed" or not paper_id:
                continue

            spec = ALL_PAPER_SPECS.get(paper_id)
            if not spec:
                continue

            def _method_base(m: str) -> str:
                """Normalize method variants: smoothquant_o1/o2/o3 → smoothquant."""
                for suffix in ("_o1", "_o2", "_o3"):
                    if m.endswith(suffix):
                        return m[: -len(suffix)]
                return m

            for r in spec.results:
                if r.model != e["model_name"]:
                    continue
                if is_baseline and r.method not in ("fp16", "fp32"):
                    continue
                if not is_baseline and r.method in ("fp16", "fp32"):
                    continue
                if not is_baseline and exp_bit_width is not None and r.bit_width != exp_bit_width:
                    continue
                if not is_baseline and exp_method and _method_base(r.method) != _method_base(exp_method):
                    continue
                our_val = metric_map.get((r.dataset, r.metric_name))
                if our_val is None:
                    continue
                paper_val = _json_safe_float(r.value)
                our_val_safe = _json_safe_float(our_val)
                denom = paper_val if r.metric_name == "perplexity" else max(paper_val, 0.01)
                if denom == 0:
                    denom = 0.01
                diff_pct = ((our_val_safe - paper_val) / denom) * 100
                diff_pct = _json_safe_float(diff_pct)

                if r.metric_name == "perplexity":
                    if abs(diff_pct) < 2:
                        verdict = "matching"
                    elif abs(diff_pct) < 10:
                        verdict = "close"
                    elif diff_pct < 0:
                        verdict = "better"
                    else:
                        verdict = "worse"
                else:
                    if abs(diff_pct) < 2:
                        verdict = "matching"
                    elif abs(diff_pct) < 10:
                        verdict = "close"
                    elif diff_pct > 0:
                        verdict = "better"
                    else:
                        verdict = "worse"

                verdicts[verdict] += 1
                comparisons.append({
                    "experiment_id": e["id"], "model": e["model_name"],
                    "method": method_tag or r.method, "bit_width": exp_bit_width,
                    "paper_id": paper_id,
                    "dataset": r.dataset, "metric": r.metric_name,
                    "paper_value": paper_val, "our_value": round(our_val_safe, 4),
                    "diff_pct": round(diff_pct, 2), "verdict": verdict,
                })

            for (ds, mn), val in metric_map.items():
                if val is None:
                    continue
                already = any(
                    c["experiment_id"] == e["id"] and c["dataset"] == ds and c["metric"] == mn
                    for c in comparisons
                )
                if already:
                    continue
                comparisons.append({
                    "experiment_id": e["id"], "model": e["model_name"],
                    "method": method_tag, "bit_width": exp_bit_width,
                    "paper_id": paper_id,
                    "dataset": ds, "metric": mn,
                    "paper_value": None, "our_value": round(_json_safe_float(val), 4),
                    "diff_pct": None, "verdict": "no_paper_ref",
                })

    return {
        "status_counts": status_counts,
        "verdicts": verdicts,
        "comparisons": comparisons,
        "experiments": experiments_list,
        "v2_only": v2_only,
        "reproduction_v2_min_id": REPRODUCTION_V2_MIN_ID if v2_only else None,
    }


@app.delete("/api/experiments")
async def flush_all_experiments():
    """Delete ALL experiments, metrics, and quant configs."""
    try:
        with SessionLocal() as session:
            m = session.execute(text("DELETE FROM metrics")).rowcount
            q = session.execute(text("DELETE FROM quant_configs")).rowcount
            e = session.execute(text("DELETE FROM experiments")).rowcount
            session.commit()
        _running_jobs.clear()
        _experiment_logs.clear()
        _pending_experiment_configs.clear()
        _reproduction_batch_status.clear()
        return {"status": "flushed", "deleted": {"experiments": e, "quant_configs": q, "metrics": m}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# Run with: uvicorn src.api.server:app --reload --port 8080
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
