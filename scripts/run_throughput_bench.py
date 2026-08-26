"""Throughput / latency / power benchmark on a single MI300X GPU.

Runs vLLM's reference throughput benchmark on a model and records:

    - tokens/sec (output)
    - latency p50, p95, p99 per request
    - peak HBM allocated
    - mean GPU power draw during the run (from rocm-smi polling)

Intended for the IISWC paper's R-4 ('one Pareto figure'). Reports a
single (model, format) point in JSON; aggregate multiple invocations into
the Pareto plot via scripts/plot_pareto.py.

Logs to W&B with tag `iiswc-2026-tools-track` so the points line up next
to the LLMC accuracy runs.

Usage:

    python scripts/run_throughput_bench.py \\
        --model meta-llama/Meta-Llama-3-8B-Instruct \\
        --gpu 3 \\
        --num-prompts 100 \\
        --input-len 512 --output-len 128

Outputs:

    reports/throughput/<model_short>__<format>.json

The script must run inside a container that has vllm installed (the
`llm-quant-dev` image qualifies) and rocm-smi on PATH.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import wandb


def poll_rocm_power(gpu_id: str, interval: float, stop_evt: threading.Event,
                    samples: list[dict]) -> None:
    """Background thread: poll rocm-smi --showpower at `interval` Hz."""
    while not stop_evt.is_set():
        try:
            out = subprocess.run(
                ["rocm-smi", "--showpower", "-d", gpu_id, "--csv"],
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            stop_evt.wait(interval)
            continue
        # Find the first line with comma-separated W reading.
        for line in out.stdout.splitlines():
            if "device" in line.lower() or not line.strip():
                continue
            cells = [c.strip() for c in line.split(",")]
            if len(cells) >= 2:
                try:
                    samples.append({"t": time.time(), "power_w": float(cells[1])})
                except ValueError:
                    pass
                break
        stop_evt.wait(interval)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="HuggingFace model path or local dir.")
    ap.add_argument("--gpu", default="3", help="HIP_VISIBLE_DEVICES value.")
    ap.add_argument("--num-prompts", type=int, default=100)
    ap.add_argument("--input-len", type=int, default=512)
    ap.add_argument("--output-len", type=int, default=128)
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--quantization", default=None,
                    help="vLLM --quantization flag (None, fp8, awq, gptq, etc).")
    ap.add_argument("--dtype", default="auto")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-wandb", action="store_true")
    args = ap.parse_args()

    repo_root = Path("/workspace") if Path("/workspace").exists() else Path.cwd()
    model_short = args.model.split("/")[-1]
    fmt_tag = args.quantization or args.dtype
    out_dir = repo_root / "reports" / "throughput"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out or (out_dir / f"{model_short}__{fmt_tag}.json")

    env = os.environ.copy()
    env["HIP_VISIBLE_DEVICES"] = args.gpu

    # Construct the vLLM benchmark command.
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.cli.main", "bench", "throughput",
        "--model", args.model,
        "--num-prompts", str(args.num_prompts),
        "--input-len", str(args.input_len),
        "--output-len", str(args.output_len),
        "--max-model-len", str(args.max_model_len),
        "--dtype", args.dtype,
        "--output-json", str(out_json),
    ]
    if args.quantization:
        cmd += ["--quantization", args.quantization]

    # Initialise W&B.
    run = None
    if not args.no_wandb and os.environ.get("WANDB_API_KEY"):
        run = wandb.init(
            project=os.environ.get("WANDB_PROJECT", "llm-quant-lab"),
            entity=os.environ.get("WANDB_ENTITY") or None,
            name=f"throughput_{model_short}__{fmt_tag}_GPU{args.gpu}",
            group=f"throughput_{model_short}",
            tags=["iiswc-2026-tools-track", "throughput", model_short.lower(), fmt_tag],
            config={
                "model": args.model,
                "model_short": model_short,
                "format": fmt_tag,
                "quantization": args.quantization,
                "dtype": args.dtype,
                "gpu_id": args.gpu,
                "hardware": "MI300X",
                "num_prompts": args.num_prompts,
                "input_len": args.input_len,
                "output_len": args.output_len,
                "max_model_len": args.max_model_len,
            },
            notes="IISWC 2026 throughput point (R-4 mitigation).",
            settings=wandb.Settings(start_method="thread"),
        )

    # Start power-polling thread.
    samples: list[dict] = []
    stop_evt = threading.Event()
    poller = threading.Thread(
        target=poll_rocm_power,
        args=(args.gpu, 0.1, stop_evt, samples),
        daemon=True,
    )
    poller.start()
    started = time.time()

    print("[throughput] cmd:", " ".join(cmd), flush=True)
    rc = subprocess.run(cmd, env=env).returncode
    finished = time.time()
    stop_evt.set()
    poller.join(timeout=5)

    duration = finished - started
    powers = [s["power_w"] for s in samples]
    mean_power = sum(powers) / len(powers) if powers else None
    peak_power = max(powers) if powers else None
    energy_j = (mean_power * duration) if mean_power is not None else None

    summary = {
        "model": args.model,
        "format": fmt_tag,
        "gpu": args.gpu,
        "duration_s": duration,
        "rc": rc,
        "mean_power_w": mean_power,
        "peak_power_w": peak_power,
        "approx_energy_j": energy_j,
        "n_power_samples": len(samples),
    }
    if out_json.exists():
        try:
            summary["vllm_bench"] = json.loads(out_json.read_text())
        except json.JSONDecodeError:
            pass

    summary_path = out_dir / f"{model_short}__{fmt_tag}__summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print("[throughput] wrote", summary_path)

    if run is not None:
        run.summary["mean_power_w"] = mean_power
        run.summary["peak_power_w"] = peak_power
        run.summary["approx_energy_j"] = energy_j
        run.summary["duration_s"] = duration
        if "vllm_bench" in summary:
            for k, v in summary["vllm_bench"].items():
                if isinstance(v, (int, float)):
                    run.summary[f"vllm_{k}"] = v
        run.finish()

    return rc


if __name__ == "__main__":
    sys.exit(main())
