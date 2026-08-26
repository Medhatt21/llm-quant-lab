"""Unified Postgres <-> W&B synchronization manager.

This module provides the single write path for experiment tracking.
Instead of dual-writing to both Postgres and W&B independently,
the SyncManager assigns clear ownership:

- Postgres owns: Experiment definitions, configs, summary metrics,
  environment snapshots, calibration records, scientist reports.
- W&B owns: Full metric time-series, histograms, artifacts, raw logs.

The SyncManager links them via shared run IDs and provides a
bidirectional read path using wandb.Api.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from ..db.logging import (
    get_git_info,
    log_experiment,
    log_hardware_stats,
    log_metrics,
    log_metrics_batch,
    log_quant_config,
    log_scientist_report,
    update_experiment_status,
)
from ..db.models import Experiment, get_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ============================================================================
# W&B availability check
# ============================================================================

try:
    import wandb
    from wandb.sdk.wandb_run import Run as WandbRun

    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    WandbRun = None  # type: ignore[assignment, misc]
    logger.debug("wandb not available. Install with: pip install wandb")


# ============================================================================
# Config hashing
# ============================================================================


def hash_config(config_dict: dict[str, Any]) -> str:
    """Generate a deterministic SHA-256 hash of an experiment config.

    The config is serialised to canonical JSON (sorted keys, no whitespace)
    so the hash is stable across runs.
    """
    canonical = json.dumps(config_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def generate_run_id(
    method: str,
    model_name: str,
    bit_width: int,
    group_size: int | None = None,
    config_hash: str = "",
) -> str:
    """Generate a human-readable, deterministic run ID.

    Format: {method}_{model_short}_{bits}b_g{group_size}_{hash[:8]}_{date}
    Example: gptq_opt125m_4b_g128_a3f2c1d9_20260208
    """
    model_short = model_name.split("/")[-1].lower().replace("-", "")
    gs = f"g{group_size}" if group_size and group_size > 0 else "gch"
    h = config_hash[:8] if config_hash else "00000000"
    date_str = datetime.utcnow().strftime("%Y%m%d")
    return f"{method}_{model_short}_{bit_width}b_{gs}_{h}_{date_str}"


# ============================================================================
# Unified Run handle
# ============================================================================


@dataclass
class UnifiedRun:
    """Handle representing a run tracked in both Postgres and W&B."""

    # Postgres side
    pg_experiment_id: int
    pg_session: Session

    # W&B side (may be None when W&B is disabled)
    wandb_run: WandbRun | None = None
    wandb_run_id: str | None = None
    wandb_run_url: str | None = None

    # Identifiers
    run_id: str = ""
    config_hash: str = ""

    # Accumulated summary metrics (written to Postgres on finish)
    _summary_metrics: dict[str, float] = field(default_factory=dict)

    # Step counter for W&B logging
    _step: int = 0

    # Start time
    _start_time: float = field(default_factory=time.time)


# ============================================================================
# SyncManager
# ============================================================================


class SyncManager:
    """Bidirectional Postgres <-> W&B synchronization.

    Usage::

        sync = SyncManager(db_url="postgresql://...", wandb_project="llm-quant-lab")
        run = sync.start_run(
            model_name="facebook/opt-125m",
            method="gptq",
            bit_width=4,
            config={"group_size": 128, ...},
            tags=["gptq", "4bit"],
        )

        # During experiment – time-series goes to W&B only
        sync.log_step(run, {"loss": 1.23, "ppl": 15.4}, step=0)

        # At end – summary metrics go to Postgres
        sync.finish_run(run, final_metrics={"perplexity": 15.4}, status="completed")
    """

    def __init__(
        self,
        db_url: str | None = None,
        wandb_project: str | None = None,
        wandb_entity: str | None = None,
        enable_wandb: bool = True,
    ):
        self.db_url = db_url or os.getenv("DATABASE_URL") or os.getenv("DB_URL", "")
        if not self.db_url:
            raise RuntimeError(
                "No database URL provided.  Pass db_url or set DATABASE_URL in your .env file."
            )
        self.wandb_project = wandb_project or os.getenv("WANDB_PROJECT", "")
        if not self.wandb_project:
            raise RuntimeError(
                "No W&B project name provided.  Pass wandb_project or set WANDB_PROJECT in your .env file."
            )
        self.wandb_entity = wandb_entity
        self.enable_wandb = enable_wandb and WANDB_AVAILABLE

        # Lazy W&B API client for read path
        self._wandb_api: Any | None = None

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def start_run(
        self,
        model_name: str,
        method: str,
        bit_width: int,
        config: dict[str, Any] | None = None,
        group_size: int | None = None,
        name: str | None = None,
        description: str | None = None,
        hardware_profile: str | None = None,
        gpu_type: str | None = None,
        gpu_count: int = 1,
        notes: str | None = None,
        tags: list[str] | None = None,
        wandb_tags: list[str] | None = None,
        wandb_group: str | None = None,
        environment_id: int | None = None,
    ) -> UnifiedRun:
        """Create a run in both Postgres and W&B, linked by shared IDs."""
        config = config or {}

        # 1. Generate config hash and run ID
        cfg_hash = hash_config(config)
        run_id = name or generate_run_id(method, model_name, bit_width, group_size, cfg_hash)

        # 2. Create Postgres experiment
        session = get_session(self.db_url)
        pg_exp = log_experiment(
            session=session,
            model_name=model_name,
            name=run_id,
            description=description,
            model_path=config.get("model_path"),
            base_precision=config.get("base_precision", "fp16"),
            hardware_profile=hardware_profile,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            notes=notes,
            tags=tags or [],
        )

        # Store config_hash and environment_id (mandatory columns)
        pg_exp.config_hash = cfg_hash  # type: ignore[attr-defined]
        if environment_id is not None:
            pg_exp.environment_id = environment_id  # type: ignore[attr-defined]

        # 3. Init W&B run with same run_id as name
        wb_run: WandbRun | None = None
        wb_run_id: str | None = None
        wb_run_url: str | None = None

        if self.enable_wandb:
            try:
                all_tags = list(tags or [])
                all_tags.extend(wandb_tags or [])
                if method:
                    all_tags.append(method)
                all_tags.append(f"{bit_width}bit")

                wb_run = wandb.init(
                    project=self.wandb_project,
                    entity=self.wandb_entity,
                    name=run_id,
                    config=config,
                    tags=list(set(all_tags)),
                    notes=notes,
                    group=wandb_group,
                    reinit=True,
                )
                wb_run_id = wb_run.id
                wb_run_url = wb_run.url
                logger.info(f"W&B run started: {wb_run_url}")
            except Exception as e:
                raise RuntimeError(
                    f"W&B initialization failed: {e}. "
                    f"Set enable_wandb=False to run without W&B."
                ) from e

        # 4. Store W&B cross-reference in Postgres
        pg_exp.wandb_run_id = wb_run_id  # type: ignore[attr-defined]
        pg_exp.wandb_run_url = wb_run_url  # type: ignore[attr-defined]
        pg_exp.wandb_project = self.wandb_project  # type: ignore[attr-defined]

        session.commit()
        session.refresh(pg_exp)

        logger.info(
            f"Unified run started: pg_id={pg_exp.id}, run_id={run_id}, "
            f"wandb_id={wb_run_id or 'disabled'}"
        )

        return UnifiedRun(
            pg_experiment_id=pg_exp.id,
            pg_session=session,
            wandb_run=wb_run,
            wandb_run_id=wb_run_id,
            wandb_run_url=wb_run_url,
            run_id=run_id,
            config_hash=cfg_hash,
        )

    def log_step(
        self,
        run: UnifiedRun,
        metrics: dict[str, Any],
        step: int | None = None,
    ) -> None:
        """Log per-step metrics to W&B only (time-series data).

        Summary/final metrics are written to Postgres on ``finish_run``.
        """
        if step is None:
            step = run._step
            run._step += 1

        if run.wandb_run is not None:
            try:
                run.wandb_run.log(metrics, step=step)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to log metrics to W&B at step {step}: {e}. "
                    f"This run's W&B data is now incomplete."
                ) from e

        # Track latest values for summary
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                run._summary_metrics[k] = v

    def log_summary(self, run: UnifiedRun, metrics: dict[str, float]) -> None:
        """Explicitly add metrics to the summary that will be written to Postgres."""
        run._summary_metrics.update(metrics)

    def log_quant_config(
        self,
        run: UnifiedRun,
        method_name: str,
        bit_width: int,
        **kwargs: Any,
    ) -> int:
        """Log a quantization config to Postgres and return its ID."""
        qc = log_quant_config(
            session=run.pg_session,
            experiment_id=run.pg_experiment_id,
            method_name=method_name,
            bit_width=bit_width,
            **kwargs,
        )
        return qc.id

    def log_hardware(self, run: UnifiedRun, **kwargs: Any) -> None:
        """Log hardware stats to Postgres (structured summary data)."""
        log_hardware_stats(
            session=run.pg_session,
            experiment_id=run.pg_experiment_id,
            **kwargs,
        )

    def finish_run(
        self,
        run: UnifiedRun,
        final_metrics: dict[str, float] | None = None,
        status: str = "completed",
        error_message: str | None = None,
        dataset: str = "wikitext2",
    ) -> dict[str, Any]:
        """Finalise the run: write summary metrics to Postgres, close W&B."""
        # Merge explicit final metrics into summary
        if final_metrics:
            run._summary_metrics.update(final_metrics)

        elapsed = time.time() - run._start_time

        # Write summary metrics to Postgres (one row per metric)
        for name, value in run._summary_metrics.items():
            try:
                log_metrics(
                    session=run.pg_session,
                    experiment_id=run.pg_experiment_id,
                    dataset=dataset,
                    metric_name=name,
                    value=value,
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to write metric '{name}' to Postgres: {e}. "
                    f"Summary data is incomplete."
                ) from e

        # Update experiment status
        update_experiment_status(
            run.pg_session,
            run.pg_experiment_id,
            status,
            error_message=error_message,
        )

        # Finalise W&B
        if run.wandb_run is not None:
            try:
                for k, v in run._summary_metrics.items():
                    run.wandb_run.summary[k] = v
                run.wandb_run.summary["elapsed_seconds"] = elapsed
                run.wandb_run.summary["status"] = status
                run.wandb_run.finish()
                logger.info(f"W&B run finished: {run.wandb_run_url}")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to finalize W&B run: {e}. "
                    f"Run may be left open in W&B dashboard."
                ) from e

        # Close DB session (best-effort cleanup after data is committed)
        try:
            run.pg_session.close()
        except Exception as e:
            logger.error(f"Failed to close DB session cleanly: {e}")

        summary = {
            "run_id": run.run_id,
            "pg_experiment_id": run.pg_experiment_id,
            "wandb_run_id": run.wandb_run_id,
            "status": status,
            "elapsed_seconds": elapsed,
            "metrics": run._summary_metrics,
        }
        logger.info(f"Run finished: {run.run_id} ({status}, {elapsed:.1f}s)")
        return summary

    # ------------------------------------------------------------------
    # Read path – pull data from W&B via Postgres cross-references
    # ------------------------------------------------------------------

    @property
    def wandb_api(self) -> Any:
        """Lazy-init the W&B public API client."""
        if self._wandb_api is None:
            if not WANDB_AVAILABLE:
                raise RuntimeError("wandb is not installed")
            self._wandb_api = wandb.Api()
        return self._wandb_api

    def get_run_history(
        self,
        experiment_id: int,
        keys: list[str] | None = None,
        db_url: str | None = None,
    ) -> pd.DataFrame:
        """Pull full metric history from W&B using the Postgres cross-reference."""
        session = get_session(db_url or self.db_url)
        exp = session.query(Experiment).filter(Experiment.id == experiment_id).first()
        session.close()

        if exp is None:
            raise ValueError(f"Experiment {experiment_id} not found")

        wandb_run_id = getattr(exp, "wandb_run_id", None)
        if not wandb_run_id:
            raise ValueError(f"Experiment {experiment_id} has no W&B run linked")

        entity = self.wandb_entity or ""
        path = f"{entity}/{self.wandb_project}/{wandb_run_id}".lstrip("/")
        api_run = self.wandb_api.run(path)

        if keys:
            return api_run.history(keys=keys)
        return api_run.history()

    def get_run_artifacts(self, experiment_id: int, db_url: str | None = None) -> list[Any]:
        """Pull artifacts from W&B using the Postgres cross-reference."""
        session = get_session(db_url or self.db_url)
        exp = session.query(Experiment).filter(Experiment.id == experiment_id).first()
        session.close()

        if exp is None:
            raise ValueError(f"Experiment {experiment_id} not found")

        wandb_run_id = getattr(exp, "wandb_run_id", None)
        if not wandb_run_id:
            return []

        entity = self.wandb_entity or ""
        path = f"{entity}/{self.wandb_project}/{wandb_run_id}".lstrip("/")
        api_run = self.wandb_api.run(path)
        return list(api_run.logged_artifacts())

    def get_run_config(self, experiment_id: int, db_url: str | None = None) -> dict[str, Any]:
        """Pull run config from W&B."""
        session = get_session(db_url or self.db_url)
        exp = session.query(Experiment).filter(Experiment.id == experiment_id).first()
        session.close()

        if exp is None:
            raise ValueError(f"Experiment {experiment_id} not found")

        wandb_run_id = getattr(exp, "wandb_run_id", None)
        if not wandb_run_id:
            return {}

        entity = self.wandb_entity or ""
        path = f"{entity}/{self.wandb_project}/{wandb_run_id}".lstrip("/")
        api_run = self.wandb_api.run(path)
        return dict(api_run.config)
