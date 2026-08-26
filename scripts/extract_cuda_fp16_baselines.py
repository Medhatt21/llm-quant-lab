#!/usr/bin/env python3
"""Harvest FP16 (pretrain) wikitext2 perplexities from CUDA-arm run logs.

Every quantized LLMC run evaluates at ``eval_pos: [pretrain, fake_quant]``, so
the FIRST ``EVAL: ppl on wikitext2 is X`` line in a run log is the perplexity of
the *unquantized* (FP16) model -- i.e. the FP16 baseline for that model. The
runner (scripts/run_cuda_arm.sh) records only the LAST (fake_quant) value, so
this script recovers the FP16 baselines that would otherwise be thrown away.

For each model it emits a per-model FP16 row file under
``reports/cuda_arm/rows/`` (schema-compatible with cuda_results.csv) so that
scripts/collect_cuda_results.sh folds them into the master CUDA CSV, and then
scripts/merge_paired_results.py can fill the FP16 ``nvidia_value`` cells.

Optionally logs each FP16 baseline to W&B under the ``nvidia-reproduction`` tag.

Usage:
    python scripts/extract_cuda_fp16_baselines.py [--wandb]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
# Keep the local ``wandb/`` output dir from shadowing the installed package.
sys.path = [p for p in sys.path if p not in ("", ".", str(_REPO_ROOT))]

OUT_DIR = _REPO_ROOT / "reports" / "cuda_arm"
ROWS_DIR = OUT_DIR / "rows"
CONFIG_DIR = _REPO_ROOT / "experiments" / "configs"

_PPL_RE = re.compile(r"EVAL: ppl on wikitext2 is ([0-9.]+)")
_TS_SUFFIX_RE = re.compile(r"_\d{8}T\d{6}Z$")
_HEADER = (
    "config_name,model,method,bit_width,wikitext2_ppl,llmc_duration_s,"
    "gpu_name,vllm_version,torch_version,timestamp,config_sha256"
)


def config_name_from_log(log_path: Path) -> str:
    stem = log_path.name[: -len(".log")] if log_path.name.endswith(".log") else log_path.stem
    return _TS_SUFFIX_RE.sub("", stem)


def model_for_config(config_name: str) -> str | None:
    cfg = CONFIG_DIR / f"{config_name}.yml"
    if not cfg.is_file():
        return None
    for line in cfg.read_text().splitlines():
        s = line.strip()
        if s.startswith("path:"):
            return s.split(":", 1)[1].strip()
    return None


def representative_env() -> dict[str, str]:
    """Pull gpu_name / torch_version from any existing per-run JSON."""
    for jp in sorted(OUT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(jp.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        return {
            "gpu_name": str(rec.get("gpu", "NVIDIA A10G")),
            "torch_version": str(rec.get("torch_version", "unknown")),
            "vllm_version": str(rec.get("vllm_version", "unknown")),
        }
    return {"gpu_name": "NVIDIA A10G", "torch_version": "unknown", "vllm_version": "unknown"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wandb", action="store_true", help="also log baselines to W&B")
    args = ap.parse_args()

    ROWS_DIR.mkdir(parents=True, exist_ok=True)

    # model -> (mtime, pretrain_ppl, config_name)
    best: dict[str, tuple[float, float, str]] = {}
    for log_path in OUT_DIR.glob("*.log"):
        text = log_path.read_text(errors="replace")
        ppls = _PPL_RE.findall(text)
        if not ppls:
            continue
        pretrain = float(ppls[0])  # first eval == pretrain == FP16
        cfg_name = config_name_from_log(log_path)
        model = model_for_config(cfg_name)
        if not model:
            continue
        mtime = log_path.stat().st_mtime
        cur = best.get(model)
        if cur is None or mtime > cur[0]:
            best[model] = (mtime, pretrain, cfg_name)

    if not best:
        print("[fp16] no pretrain perplexities found in logs", file=sys.stderr)
        return 0

    env = representative_env()
    ts = "extracted"
    wrote = 0
    records = []
    for model, (_, ppl, cfg_name) in sorted(best.items()):
        slug = model.split("/")[-1]
        row = (
            f"{slug}_fp16_w16,{model},fp16,16,{ppl},,"
            f"{env['gpu_name']},{env['vllm_version']},{env['torch_version']},{ts},from:{cfg_name}"
        )
        (ROWS_DIR / f"zz_fp16_{slug}.csv").write_text(row + "\n")
        records.append({"model": model, "ppl": ppl, "slug": slug, "from": cfg_name})
        wrote += 1
        print(f"[fp16] {model:40s} ppl={ppl:.6g}  (from {cfg_name})")

    print(f"[fp16] wrote {wrote} FP16 baseline row files into {ROWS_DIR}")

    if args.wandb and os.environ.get("WANDB_API_KEY"):
        try:
            import wandb
        except ImportError:
            print("[fp16] wandb not importable; skipping W&B logging", file=sys.stderr)
            return 0
        for rec in records:
            run = wandb.init(
                project=os.environ.get("WANDB_PROJECT", "llm-quant-lab"),
                entity=os.environ.get("WANDB_ENTITY") or None,
                name=f"{rec['slug']}_fp16_w16",
                job_type="cuda-arm-reproduction",
                tags=["nvidia-reproduction", "cuda-arm", "fp16", "w16"],
                config={
                    "model": rec["model"],
                    "method": "fp16",
                    "bit_width": 16,
                    "hardware_arm": "cuda",
                    "gpu_name": env["gpu_name"],
                    "torch_version": env["torch_version"],
                    "derived_from": rec["from"],
                    "note": "FP16 baseline extracted from pretrain eval of a quantized run",
                },
                reinit=True,
            )
            run.log({"wikitext2_ppl": rec["ppl"]})
            run.summary["wikitext2_ppl"] = rec["ppl"]
            run.finish()
        print(f"[fp16] logged {len(records)} FP16 baselines to W&B")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
