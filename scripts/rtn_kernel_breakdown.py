"""Capture and pretty-print the kernel-level breakdown of a RTN-quantized
forward pass on AMD MI300X.

Output is a kernel-by-kernel table sorted by CUDA time, plus a JSON
summary that aggregates GEMM vs non-GEMM device time. Used by §5.1 of the
IISWC 2026 draft to show that the LLMC fake-quant path executes through
FP16 GEMM (`aten::addmm` / `aten::mm`), with zero device-time in integer
GEMM kernels.

Usage:
    python scripts/rtn_kernel_breakdown.py --model facebook/opt-125m \\
        --bit 4 --gpu 3 --out reports/dispatch_traces/opt125m_rtn_w4.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import torch
from torch import nn
from torch.profiler import ProfilerActivity, profile


GEMM_LIKE_NAMES = {
    "aten::addmm",
    "aten::mm",
    "aten::bmm",
    "aten::baddbmm",
    "aten::matmul",
    "aten::linear",
}
INTEGER_GEMM_HINTS = ("igemm", "int8", "int4", "i8gemm", "i4gemm", "qgemm", "_int_mm")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--gpu", default="3")
    ap.add_argument("--bit", type=int, default=4)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    os.environ["HIP_VISIBLE_DEVICES"] = args.gpu

    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[trace] loading {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float16
    ).cuda().eval()

    def rtn(weight: torch.Tensor, bit: int) -> torch.Tensor:
        qmax = 2 ** (bit - 1) - 1
        scale = weight.abs().amax(dim=-1, keepdim=True).clamp_min(1e-8) / qmax
        return torch.round(weight / scale).clamp(-qmax - 1, qmax) * scale

    with torch.no_grad():
        for m in model.modules():
            if isinstance(m, nn.Linear):
                m.weight.copy_(rtn(m.weight, args.bit))

    text = ("AMD MI300X runs quantized LLMs " * 32)[: args.seq_len * 4]
    inputs = tok(text, return_tensors="pt", truncation=True,
                 max_length=args.seq_len).to("cuda")

    with torch.no_grad():
        for _ in range(2):
            model(**inputs)
            torch.cuda.synchronize()

    print("[trace] profiling ...", flush=True)
    with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as p:
        with torch.no_grad():
            for _ in range(args.steps):
                model(**inputs)
                torch.cuda.synchronize()

    avgs = list(p.key_averages())
    rows = []
    total_dev_us = 0.0
    for evt in avgs:
        if evt.device_time_total <= 0:
            continue
        rows.append({
            "name": evt.key,
            "calls": int(evt.count),
            "self_device_us": float(evt.device_time_total),
            "device_total_us": float(evt.device_time_total),
        })
        total_dev_us += evt.device_time_total
    rows.sort(key=lambda r: -r["self_device_us"])

    gemm_us = 0.0
    integer_gemm_us = 0.0
    fp16_gemm_us = 0.0
    for r in rows:
        n = r["name"]
        is_gemm_like = any(n.startswith(g) for g in GEMM_LIKE_NAMES)
        is_integer = any(h in n.lower() for h in INTEGER_GEMM_HINTS)
        if is_gemm_like:
            gemm_us += r["self_device_us"]
            if is_integer:
                integer_gemm_us += r["self_device_us"]
            else:
                fp16_gemm_us += r["self_device_us"]

    summary = {
        "model": args.model,
        "bit": args.bit,
        "gpu": args.gpu,
        "seq_len": args.seq_len,
        "steps": args.steps,
        "total_device_us": total_dev_us,
        "gemm_share_pct": gemm_us / total_dev_us * 100 if total_dev_us else 0,
        "integer_gemm_share_pct": integer_gemm_us / total_dev_us * 100 if total_dev_us else 0,
        "fp16_gemm_share_pct": fp16_gemm_us / total_dev_us * 100 if total_dev_us else 0,
        "top_kernels": rows[:25],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2))
    print(f"[trace] wrote {args.out}")
    print(f"  total device time:        {total_dev_us:9.1f} us")
    print(f"  GEMM share:               {summary['gemm_share_pct']:6.2f}%")
    print(f"  ...integer-GEMM share:    {summary['integer_gemm_share_pct']:6.2f}%")
    print(f"  ...FP16-GEMM share:       {summary['fp16_gemm_share_pct']:6.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
