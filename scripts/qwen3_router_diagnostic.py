"""Router-disruption diagnostic on a modern MoE (Qwen3-30B-A3B).

Exercises a current MoE (rather than Mixtral) and shows the tool diagnosing a
mismatch rather than merely detecting one, across the dense/MoE taxonomy.

It measures how W8A8 SmoothQuant-style quantization perturbs the MoE router,
using the (corrected) src.diagnostics.router_probe.RouterProbe:

  Pass 1 (BF16 baseline): run calibration text, capture router logits AND the
          per-channel abs-max of each MoE block's input hidden state.
  Transform: for every MoE layer apply the standard SmoothQuant migration on
          the router-input pathway -- s_j = act_max_j^a / wgt_max_j^(1-a),
          folded into post_attention_layernorm, weights scaled by diag(s) --
          then fake-quantize activations (per-token INT8) and the consuming
          weights (per-output-channel INT8). This is the SmoothQuant W8A8
          operation restricted to the pathway the router reads.
  Pass 2 (quantized): re-run the SAME tokens, capture router logits.
  Compare: top-1 expert flip rate, top-k Jaccard, per-token softmax KL, and
          per-layer flip-rate localization.

Fully offline: model + tokenizer are read from the local HF cache and the
calibration text is embedded below (no dataset download). This is a mechanism
diagnostic; reproducing LLMC's exact SmoothQuant end-to-end (with WikiText-2
perplexity) is the camera-ready step -- see PAIRED_PARITY_PROTOCOL.md.

Usage (inside the ROCm dev container, one GPU):
    HIP_VISIBLE_DEVICES=7 python scripts/qwen3_router_diagnostic.py --smoke
    HIP_VISIBLE_DEVICES=7 python scripts/qwen3_router_diagnostic.py \
        --model qwen/Qwen3-30B-A3B --alpha 0.5 --seqs 24 --seqlen 256
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.diagnostics.router_probe import RouterProbe  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "moe_probe"

# Embedded calibration text (no download). Varied domains so activation
# statistics are not degenerate.
CALIB_TEXT = [
    "The mitochondria is the powerhouse of the cell, generating ATP through oxidative phosphorylation across the inner membrane.",
    "In distributed systems, consensus protocols such as Raft and Paxos guarantee agreement despite node failures and network partitions.",
    "Quantization reduces the numerical precision of neural network weights and activations to lower memory footprint and accelerate inference.",
    "The Treaty of Westphalia in 1648 established the modern notion of state sovereignty in international relations.",
    "A monad in category theory is a monoid in the category of endofunctors, equipped with unit and multiplication natural transformations.",
    "Photosynthesis converts carbon dioxide and water into glucose and oxygen using light energy captured by chlorophyll.",
    "Mixture-of-experts models route each token to a small subset of expert feed-forward networks selected by a learned gating function.",
    "The central limit theorem states that the normalized sum of independent random variables converges to a normal distribution.",
    "Rust's borrow checker enforces memory safety at compile time without a garbage collector by tracking ownership and lifetimes.",
    "The Silk Road connected trade between East Asia, Central Asia, the Middle East, and the Mediterranean for over a millennium.",
    "Gradient descent iteratively updates parameters in the direction of steepest descent of a differentiable loss function.",
    "Coral reefs support roughly a quarter of all marine species despite covering less than one percent of the ocean floor.",
]


@torch.no_grad()
def run() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen/Qwen3-30B-A3B")
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--seqs", type=int, default=24)
    ap.add_argument("--seqlen", type=int, default=256)
    ap.add_argument("--smoke", action="store_true",
                    help="load, attach probe, one short forward, then exit")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dev = "cuda:0"
    t0 = time.time()
    print(f"[diag] loading tokenizer+model {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map=dev,
    )
    model.eval()
    print(f"[diag] loaded in {time.time()-t0:.0f}s", flush=True)

    # Build calibration batches (repeat/truncate the embedded text).
    text = (CALIB_TEXT * ((args.seqs // len(CALIB_TEXT)) + 1))[: args.seqs]
    enc = tok(text, return_tensors="pt", padding="max_length", truncation=True,
              max_length=args.seqlen)
    input_ids = enc["input_ids"].to(dev)
    attn = enc["attention_mask"].to(dev)

    # -- Locate MoE blocks (transformers 5.x fused Qwen3-MoE layout):
    #   blk.mlp                    Qwen3MoeSparseMoeBlock
    #   blk.mlp.gate               Qwen3MoeTopKRouter (has .weight [E, H])
    #   blk.mlp.experts.gate_up_proj  Parameter [E, 2*I, H]  (reads block input)
    #   blk.mlp.experts.down_proj     Parameter [E, H, I]    (reads intermediate)
    #   blk.post_attention_layernorm  RMSNorm (the MoE-block input norm)
    layers = model.model.layers
    moe = []
    for i, blk in enumerate(layers):
        mlp = getattr(blk, "mlp", None)
        gate = getattr(mlp, "gate", None) if mlp is not None else None
        experts = getattr(mlp, "experts", None) if mlp is not None else None
        if gate is None or not hasattr(gate, "weight") or experts is None:
            continue
        if not hasattr(experts, "gate_up_proj"):
            continue
        ln = getattr(blk, "post_attention_layernorm", None)
        moe.append({"idx": i, "mlp": mlp, "gate": gate, "experts": experts, "ln": ln})
    print(f"[diag] found {len(moe)} MoE layers", flush=True)

    # The Qwen3 router is a custom module (not nn.Linear) whose forward returns
    # (router_probs, router_scores, router_indices) -- already softmaxed.
    def router_matcher(name: str, mod: torch.nn.Module) -> bool:
        return type(mod).__name__ == "Qwen3MoeTopKRouter"

    def make_probe() -> RouterProbe:
        return RouterProbe(gate_matcher=router_matcher, output_is_probs=True,
                           store_probs=True)

    if args.smoke:
        probe = make_probe()
        n = probe.attach(model)
        print(f"[diag][smoke] probe hooked {n} routers (expected {len(moe)})")
        model(input_ids=input_ids[:2], attention_mask=attn[:2])
        probe.detach()
        print(f"[diag][smoke] captured {len(probe.records)} router records; "
              f"sample={probe.records[0] if probe.records else None}")
        assert n == len(moe), "router count mismatch"
        assert len(probe.records) > 0
        print("[diag][smoke] OK")
        return 0

    # -- Pass 1: BF16 baseline probe + activation abs-max collection.
    act_max: dict[int, torch.Tensor] = {}
    hooks = []

    def mk_collector(idx):
        def _pre(_m, inp):
            x = inp[0]
            a = x.abs().amax(dim=tuple(range(x.dim() - 1))).float()  # (hidden,)
            prev = act_max.get(idx)
            act_max[idx] = a if prev is None else torch.maximum(prev, a)
        return _pre

    for e in moe:
        hooks.append(e["mlp"].register_forward_pre_hook(mk_collector(e["idx"])))

    base_probe = make_probe()
    base_probe.attach(model)
    print("[diag] pass 1 (BF16 baseline) ...", flush=True)
    for b in range(0, input_ids.shape[0], 2):
        model(input_ids=input_ids[b:b+2], attention_mask=attn[b:b+2])
    base_probe.detach()
    for h in hooks:
        h.remove()
    print(f"[diag] pass1 records={len(base_probe.records)}", flush=True)

    # -- Transform: SmoothQuant migration + W8A8 fake-quant on router pathway.
    # The router (gate.weight [E,H]) and the experts' gate_up_proj [E,2I,H] both
    # read the MoE block input (dim H); down_proj reads the intermediate and is
    # left untouched (out of the gating pathway). We report exactly this scope.
    def fq_int8_lastdim(w: torch.Tensor) -> torch.Tensor:
        # symmetric per-output-channel INT8 fake-quant (scale over input dim).
        s = w.abs().amax(dim=-1, keepdim=True) / 127.0
        s = s.clamp_min(1e-8)
        return (torch.round(w / s).clamp_(-127, 127) * s).to(w.dtype)

    a = args.alpha
    for e in moe:
        idx = e["idx"]
        amax = act_max[idx].to(dev).float() + 1e-6  # (H,)
        gate_w = e["gate"].weight  # (E, H)
        gup = e["experts"].gate_up_proj  # (E, 2I, H)
        # per-input-channel weight abs-max across both consumers.
        wmax = torch.maximum(
            gate_w.abs().amax(dim=0).float(),           # (H,)
            gup.abs().amax(dim=(0, 1)).float(),          # (H,)
        ) + 1e-6
        s = (amax.pow(a) / wmax.pow(1 - a)).clamp_min(1e-6)  # (H,)
        # fold 1/s into the input RMSNorm weight (h' = h / s).
        if e["ln"] is not None and hasattr(e["ln"], "weight"):
            e["ln"].weight.data = (e["ln"].weight.data.float() / s).to(e["ln"].weight.dtype)
        # scale consumer input columns by s, then per-output-channel INT8.
        gate_w.data = fq_int8_lastdim(gate_w.data.float() * s.view(1, -1)).to(gate_w.dtype)
        gup.data = fq_int8_lastdim(gup.data.float() * s.view(1, 1, -1)).to(gup.dtype)

    # activation fake-quant (per-token dynamic INT8) on the router + experts
    # input (the shared block-input hidden state).
    def mk_act_quant():
        def _pre(_m, inp):
            x = inp[0]
            sc = (x.abs().amax(dim=-1, keepdim=True).float() / 127.0).clamp_min(1e-8)
            xq = (torch.round(x.float() / sc).clamp_(-127, 127) * sc).to(x.dtype)
            return (xq,) + inp[1:]
        return _pre

    aq_hooks = []
    for e in moe:
        aq_hooks.append(e["gate"].register_forward_pre_hook(mk_act_quant()))
        aq_hooks.append(e["experts"].register_forward_pre_hook(mk_act_quant()))

    # -- Pass 2: quantized probe on the SAME tokens.
    q_probe = make_probe()
    q_probe.attach(model)
    print("[diag] pass 2 (SmoothQuant W8A8) ...", flush=True)
    for b in range(0, input_ids.shape[0], 2):
        model(input_ids=input_ids[b:b+2], attention_mask=attn[b:b+2])
    q_probe.detach()
    for h in aq_hooks:
        h.remove()
    print(f"[diag] pass2 records={len(q_probe.records)}", flush=True)

    # -- Compare.
    diff = RouterProbe.compare(base_probe, q_probe)
    per_layer = diff.pop("per_layer_flip_rate")
    result = {
        "model": args.model,
        "alpha": a,
        "scheme": "SmoothQuant W8A8 (per-token act INT8, per-channel weight INT8) on router pathway",
        "n_moe_layers": len(moe),
        "num_experts": int(moe[0]["gate"].weight.shape[0]) if moe else None,
        "n_calib_seqs": args.seqs,
        "seqlen": args.seqlen,
        **{k: (round(v, 6) if isinstance(v, float) else v) for k, v in diff.items()},
        "per_layer_flip_rate": {str(k): round(v, 6) for k, v in sorted(per_layer.items())},
    }
    (OUT_DIR / "qwen3_moe_sq.json").write_text(json.dumps(result, indent=2))
    with (OUT_DIR / "qwen3_moe_sq_per_layer.csv").open("w") as fh:
        fh.write("layer_idx,flip_rate\n")
        for k, v in sorted(per_layer.items()):
            fh.write(f"{k},{v:.6f}\n")

    print(json.dumps(result, indent=2))
    print(f"[diag] wrote {OUT_DIR}/qwen3_moe_sq.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
