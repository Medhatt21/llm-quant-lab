"""Wrap an LLMC run with a Weights & Biases context.

Used by scripts/run_trial_repeats.sh and scripts/reproduce_iiswc.sh so every
LLMC invocation in the IISWC paper push lands in W&B under a stable, filterable
tag.  Default tag set: ['iiswc-2026-tools-track', '<method>', '<model_family>'].

This is intentionally a thin wrapper: it does NOT modify LLMC, it just
launches torchrun and parses the resulting log to log perplexity + duration to
the active wandb run.

Conventions:

    project     = $WANDB_PROJECT  (default 'llm-quant-lab')
    entity      = $WANDB_ENTITY   (optional)
    tags        = ['iiswc-2026-tools-track', method, model_family, hardware]
    name        = '{method}_{model_short}_w{bit}_seed{seed}_GPU{gpu}'
    group       = '{method}_{model_short}_w{bit}'   (lets us aggregate seeds)
    config      = full YAML as a wandb.config dict
    artifact    = full YAML attached as an input artifact

Usage (inside the dev container):

    python scripts/wandb_run_llmc.py \\
        --config experiments/configs/gptq_opt125m__seed42.yml \\
        --gpu 3 \\
        --extra-tag headline_n3
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import wandb
import yaml


def parse_yaml_config(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh)


def short_model_name(model_path: str) -> str:
    return model_path.split("/")[-1].lower()


def model_family(model_path: str) -> str:
    name = short_model_name(model_path)
    for prefix in ("opt-", "bloom-", "llama-3", "llama-2", "llama-",
                   "mistral", "mixtral", "qwen", "deepseek", "ministral"):
        if name.startswith(prefix):
            return prefix.rstrip("-")
    return name.split("-")[0]


def parse_llmc_log(text: str) -> dict[str, float | None]:
    ppl_re = re.compile(r"EVAL: ppl on wikitext2 is ([0-9]+(?:\.[0-9]+)?)")
    dur_re = re.compile(r"llmc_duration_time: ([0-9]+(?:\.[0-9]+)?)")
    ppl_m = list(ppl_re.finditer(text))
    dur_m = list(dur_re.finditer(text))
    return {
        "wikitext2_ppl": float(ppl_m[-1].group(1)) if ppl_m else None,
        "llmc_duration_s": float(dur_m[-1].group(1)) if dur_m else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True,
                    help="Path to LLMC YAML config (relative to repo root).")
    ap.add_argument("--gpu", type=str, default=os.environ.get("HIP_VISIBLE_DEVICES", "0"),
                    help="GPU id to bind to (HIP_VISIBLE_DEVICES).")
    ap.add_argument("--extra-tag", action="append", default=[],
                    help="Additional W&B tag (repeatable).")
    ap.add_argument("--master-port", type=int,
                    default=29500 + (os.getpid() % 500))
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the wandb metadata and exit without launching torchrun.")
    args = ap.parse_args()

    config_path: Path = args.config.resolve()
    if not config_path.exists():
        # Try relative to /workspace (the dev container's mount).
        alt = Path("/workspace") / args.config
        if alt.exists():
            config_path = alt
        else:
            print(f"[wandb-llmc] config not found: {args.config}", file=sys.stderr)
            return 1

    cfg = parse_yaml_config(config_path)
    model = cfg.get("model", {}).get("path", "unknown")
    model_short = short_model_name(model)
    family = model_family(model)
    method = (cfg.get("quant", {}).get("method") or "fp16").lower()
    bit = cfg.get("quant", {}).get("weight", {}).get("bit") or 16
    seed = cfg.get("base", {}).get("seed") or 42
    hardware = "MI300X" if os.environ.get("HIP_VISIBLE_DEVICES", "") else "unknown"

    tags = ["iiswc-2026-tools-track", method, family, hardware]
    tags.extend(args.extra_tag)

    run_name = f"{method}_{model_short}_w{bit}_seed{seed}_GPU{args.gpu}"
    group = f"{method}_{model_short}_w{bit}"

    project = os.environ.get("WANDB_PROJECT", "llm-quant-lab")
    entity = os.environ.get("WANDB_ENTITY") or None

    if args.dry_run:
        print(f"[wandb-llmc] would run name={run_name!r} tags={tags!r} project={project!r}")
        return 0

    run = wandb.init(
        project=project,
        entity=entity,
        name=run_name,
        group=group,
        tags=tags,
        notes=f"IISWC 2026 Tools-track reproduction. Config: {config_path.name}",
        config={
            "method": method,
            "model": model,
            "model_short": model_short,
            "model_family": family,
            "bit_width": bit,
            "seed": seed,
            "gpu_id": args.gpu,
            "hardware": hardware,
            "config_path": str(config_path),
            "raw_config": cfg,
        },
        reinit=True,
        settings=wandb.Settings(start_method="thread"),
    )
    assert run is not None

    try:
        run.log_artifact(str(config_path), name=f"config-{config_path.stem}", type="llmc-config")
    except Exception as exc:
        # Don't fail the run if artifact upload misbehaves; the YAML is in the
        # commit anyway.
        print(f"[wandb-llmc] artifact upload skipped: {exc}", file=sys.stderr)

    # Inside the dev container, vendors/lightcompress is the LLMC working dir.
    cwd = Path("/workspace/vendors/lightcompress")
    cmd = [
        "torchrun", "--nproc_per_node=1", "--nnodes=1",
        f"--master_port={args.master_port}",
        "-m", "llmc",
        "--config", str(config_path),
        "--task_id", "0",
    ]
    env = os.environ.copy()
    env["HIP_VISIBLE_DEVICES"] = args.gpu

    print(f"[wandb-llmc] launching: {shlex.join(cmd)}", flush=True)
    started = dt.datetime.utcnow()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    finished = dt.datetime.utcnow()

    log_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    parsed = parse_llmc_log(log_text)

    run.summary["wandb_started_utc"] = started.isoformat()
    run.summary["wandb_finished_utc"] = finished.isoformat()
    run.summary["torchrun_returncode"] = proc.returncode
    if parsed["wikitext2_ppl"] is not None:
        run.log({"wikitext2_ppl": parsed["wikitext2_ppl"]})
        run.summary["wikitext2_ppl"] = parsed["wikitext2_ppl"]
    if parsed["llmc_duration_s"] is not None:
        run.log({"llmc_duration_s": parsed["llmc_duration_s"]})
        run.summary["llmc_duration_s"] = parsed["llmc_duration_s"]

    # Attach the raw log so it shows up in the W&B run page.
    log_path = Path("/tmp") / f"{run_name}.log"
    log_path.write_text(log_text)
    try:
        run.log_artifact(str(log_path), name=f"log-{run_name}", type="llmc-log")
    except Exception:
        pass

    run.finish(exit_code=0 if proc.returncode == 0 else 1)
    # Backwards-compatible echoes so callers that grep the LLMC log format
    # (e.g. scripts/run_trial_repeats.sh) keep working.
    if parsed["wikitext2_ppl"] is not None:
        print(f"EVAL: ppl on wikitext2 is {parsed['wikitext2_ppl']}", flush=True)
    if parsed["llmc_duration_s"] is not None:
        print(f"llmc_duration_time: {parsed['llmc_duration_s']}", flush=True)
    print(
        f"[wandb-llmc] done: ppl={parsed['wikitext2_ppl']} "
        f"dur={parsed['llmc_duration_s']}s rc={proc.returncode}",
        flush=True,
    )
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
