#!/usr/bin/env python3
"""Log a single CUDA-arm reproduction run to Weights & Biases.

This is the NVIDIA-arm companion to ``scripts/run_cuda_arm.sh``. It reads the
per-run JSON emitted by that script and creates one W&B run tagged
``nvidia-reproduction`` so the paired-hardware reproductions are tracked
alongside the AMD/ROCm side.

Usage:
    python scripts/wandb_log_cuda_arm.py reports/cuda_arm/<config>.json

Environment (read from the process env; the runner exports these from .env):
    WANDB_API_KEY   required for online logging; if unset the run is skipped
    WANDB_PROJECT   defaults to "llm-quant-lab"
    WANDB_ENTITY    optional team/entity

Robustness: the repo root is intentionally removed from ``sys.path`` before
importing wandb, because the repo contains a local ``wandb/`` output directory
that would otherwise shadow the installed package as a namespace package.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# --- Strip the repo root from import paths so the local ``wandb/`` run-output
# directory cannot shadow the installed wandb package. ---
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path = [p for p in sys.path if p not in ("", ".", _REPO_ROOT)]

import wandb  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: wandb_log_cuda_arm.py <run-json>", file=sys.stderr)
        return 2

    json_path = Path(sys.argv[1])
    if not json_path.is_file():
        print(f"ERROR: no such JSON: {json_path}", file=sys.stderr)
        return 2

    if not os.environ.get("WANDB_API_KEY"):
        print("[wandb] WANDB_API_KEY unset; skipping W&B logging", file=sys.stderr)
        return 0

    with json_path.open() as fh:
        rec = json.load(fh)

    name = json_path.stem
    method = str(rec.get("method", "unknown")).lower()
    bit = rec.get("bit_width", 16)
    ppl = rec.get("wikitext2_ppl")
    dur = rec.get("llmc_duration_s")

    tags = ["nvidia-reproduction", "cuda-arm", method, f"w{bit}"]

    run = wandb.init(
        project=os.environ.get("WANDB_PROJECT", "llm-quant-lab"),
        entity=os.environ.get("WANDB_ENTITY") or None,
        name=name,
        job_type="cuda-arm-reproduction",
        tags=tags,
        config={
            "config": rec.get("config"),
            "config_sha256": rec.get("config_sha256"),
            "model": rec.get("model"),
            "method": method,
            "bit_width": bit,
            "gpu_name": rec.get("gpu"),
            "torch_version": rec.get("torch_version"),
            "vllm_version": rec.get("vllm_version"),
            "hardware_arm": "cuda",
            "timestamp_utc": rec.get("timestamp_utc"),
        },
        reinit=True,
    )

    metrics = {}
    if ppl is not None:
        metrics["wikitext2_ppl"] = ppl
    if dur is not None:
        metrics["llmc_duration_s"] = dur
    if metrics:
        run.log(metrics)
    # Surface the headline number in the run summary as well.
    if ppl is not None:
        run.summary["wikitext2_ppl"] = ppl

    run.finish()
    print(f"[wandb] logged {name} (ppl={ppl}) tags={tags}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
