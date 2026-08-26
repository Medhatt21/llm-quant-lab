"""WikiText-2 perplexity under BF16 vs W8A8-FP8 fake-quant (IISWC #414).

Gives the accuracy side of the FP8 accuracy-vs-throughput trade-off, on the same
models as the serving-performance grid. Fully offline: reads the cached
WikiText-2 parquet directly and the model from the local HF cache.

FP8 fake-quant mirrors what FP8 serving does: per-output-channel E4M3 weights and
per-token dynamic E4M3 activations on every Linear. Standard GPTQ-style ppl:
concatenate the test split, non-overlapping 2048-token windows, exp(mean NLL).

Usage (ROCm dev container, one GPU):
    HIP_VISIBLE_DEVICES=7 python scripts/fp8_perplexity.py --model Qwen/Qwen3-32B
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

OUT = Path(__file__).resolve().parent.parent / "reports" / "modern_accuracy"
FP8_MAX = 448.0  # E4M3


def wikitext_text() -> str:
    pq = []
    for root in ("/data/.cache/huggingface", "/data/huggingface"):
        pq = glob.glob(f"{root}/hub/datasets--wikitext/snapshots/*/"
                       "wikitext-2-raw-v1/test-*.parquet")
        if pq:
            break
    import pandas as pd
    df = pd.read_parquet(pq[0])
    return "\n\n".join(df["text"].tolist())


def fp8_weight(w: torch.Tensor) -> torch.Tensor:
    s = (w.abs().amax(dim=-1, keepdim=True) / FP8_MAX).clamp_min(1e-8)
    q = (w / s).clamp(-FP8_MAX, FP8_MAX).to(torch.float8_e4m3fn).to(w.dtype) * s
    return q


def act_fp8_hook(_m, inp):
    x = inp[0]
    s = (x.abs().amax(dim=-1, keepdim=True).float() / FP8_MAX).clamp_min(1e-8)
    xq = (x.float() / s).clamp(-FP8_MAX, FP8_MAX).to(torch.float8_e4m3fn).to(x.dtype) * s.to(x.dtype)
    return (xq,) + inp[1:]


@torch.no_grad()
def perplexity(model, input_ids, seqlen=2048) -> float:
    dev = model.device
    n = input_ids.shape[1]
    nlls, ntok = 0.0, 0
    for i in range(0, n - seqlen, seqlen):
        chunk = input_ids[:, i:i + seqlen].to(dev)
        out = model(chunk, labels=chunk)
        nlls += out.loss.float().item() * (seqlen - 1)
        ntok += seqlen - 1
    return float(torch.exp(torch.tensor(nlls / ntok)))


@torch.no_grad()
def run() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--seqlen", type=int, default=2048)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    short = args.model.split("/")[-1]

    tok = AutoTokenizer.from_pretrained(args.model)
    ids = tok(wikitext_text(), return_tensors="pt").input_ids
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.bfloat16,
                                                 device_map="cuda:0").eval()

    bf16 = perplexity(model, ids, args.seqlen)
    print(f"[fp8ppl] {short} BF16 wikitext2 ppl = {bf16:.4f}", flush=True)

    # Apply FP8 fake-quant to every Linear: weights + input activations.
    hooks = []
    for m in model.modules():
        if isinstance(m, torch.nn.Linear):
            m.weight.data = fp8_weight(m.weight.data)
            hooks.append(m.register_forward_pre_hook(act_fp8_hook))
    fp8 = perplexity(model, ids, args.seqlen)
    for h in hooks:
        h.remove()
    print(f"[fp8ppl] {short} FP8  wikitext2 ppl = {fp8:.4f}", flush=True)

    res = {"model": args.model, "bf16_ppl": round(bf16, 4), "fp8_ppl": round(fp8, 4),
           "delta_pct": round((fp8 - bf16) / bf16 * 100, 2),
           "n_linear_quantized": len(hooks)}
    (OUT / f"{short}__fp8ppl.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(run())
