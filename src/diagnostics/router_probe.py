"""Router probe: log MoE gate decisions pre- and post-quantization.

This is the Day-1 diagnostic harness for the companion paper "Smoothing Breaks
the Router: Diagnosing and Repairing SmoothQuant Failure on Mixture-of-Experts
LLMs". It hooks every MoE gate (router) module in a HuggingFace MoE model and,
for each forward pass, logs:

    layer_idx, token_idx, top1_expert, top2_expert,
    top1_prob, softmax_entropy, gate_logits (truncated)

The purpose is to compare router decisions between an FP16 baseline and a
quantized variant on the same tokens, and to compute:

    - top-1 expert flip rate (fraction of tokens where top-1 changes)
    - top-k Jaccard distance over the k routed experts
    - per-token KL between FP16 softmax and quantized softmax
    - per-layer flip-rate distribution (is failure concentrated or spread?)

Usage from a notebook or script:

    from src.diagnostics.router_probe import RouterProbe

    probe = RouterProbe()
    probe.attach(model)
    with torch.no_grad():
        for batch in calibration_loader:
            model(**batch)
    probe.detach()
    df = probe.to_dataframe()      # rows: one per (layer, token)
    summary = probe.summary()      # mean flip rate per layer

Compare two probes:

    diff = RouterProbe.compare(fp16_probe, sq_probe)
    diff["top1_flip_rate_overall"]  # scalar
    diff["per_layer_flip_rate"]     # dict[layer_idx -> rate]
    diff["jaccard_topk"]            # mean Jaccard over top-2

The probe walks the model graph and matches gate modules by HF naming
convention. The default matcher recognises:

    Mixtral / Qwen2-MoE / Qwen3-MoE: name contains 'gate' and parent is the
        MoE block (e.g. 'model.layers.{i}.block_sparse_moe.gate').
    DeepSeek-MoE: 'mlp.gate' under each layer.
    Llama-4 (Scout / Maverick): 'feed_forward.router' or 'router'.

Override via the `gate_matcher` callable if your model deviates.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import torch
from torch import nn


# Default regex matchers. A module qualifies as a gate iff its qualified name
# matches any of these patterns AND it is a Linear-like module whose
# out_features is small (== number of experts).
#
# IMPORTANT: we deliberately do NOT match `.gate_proj` — in SwiGLU / Qwen /
# Llama MoE experts, `...experts.{j}.gate_proj` is a *dense FFN* projection
# (hidden -> intermediate), not the router. Matching it pollutes the probe
# with tens of thousands of non-router modules and inflates flip rates. The
# real MoE router is `...mlp.gate` (Qwen3-MoE / DeepSeek-MoE),
# `...block_sparse_moe.gate` (Mixtral), or `...feed_forward.router` (Llama-4).
DEFAULT_GATE_PATTERNS = (
    r"\.mlp\.gate$",
    r"block_sparse_moe\.gate$",
    r"feed_forward\.router$",
    r"\.router$",
    r"\.moe_gate$",
)

# A router Linear emits one logit per expert. Real deployments top out around
# 256 experts (DeepSeek-V3: 256, Qwen3-MoE: 128, Mixtral: 8). Any Linear whose
# out_features exceeds this cannot be a router and is almost certainly an FFN
# projection that happens to match a name pattern.
DEFAULT_MAX_GATE_OUT_FEATURES = 512


@dataclass
class RouterRecord:
    """One observation of the router output for one token at one layer."""

    layer_name: str
    layer_idx: int
    token_global_idx: int
    top1_expert: int
    top2_expert: int
    top1_prob: float
    top2_prob: float
    entropy: float
    # Full softmax over experts, stored only when the owning probe has
    # store_probs=True. Kept as a compact tuple[float, ...] so KL divergence
    # between two aligned runs can be computed post-hoc. None otherwise.
    probs: tuple[float, ...] | None = None


@dataclass
class RouterProbe:
    """Hook-based recorder of MoE router decisions during forward passes.

    The probe is stateful: call attach(model), run forward passes, call detach()
    to remove hooks. The recorded data lives in `self.records`.
    """

    gate_patterns: tuple[str, ...] = DEFAULT_GATE_PATTERNS
    gate_matcher: Callable[[str, nn.Module], bool] | None = None
    max_gate_out_features: int = DEFAULT_MAX_GATE_OUT_FEATURES
    max_records: int = 5_000_000  # safety cap
    store_probs: bool = False  # keep full expert softmax for KL computation
    output_is_probs: bool = False  # hooked module already emits softmax probs
    output_index: int = 0  # which element to read when the module returns a tuple

    records: list[RouterRecord] = field(default_factory=list)
    _hooks: list[torch.utils.hooks.RemovableHandle] = field(default_factory=list)
    _layer_index: dict[str, int] = field(default_factory=dict)
    _token_counter: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # ------------------------------------------------------------------
    # Attachment / detachment
    # ------------------------------------------------------------------

    def _is_gate(self, name: str, module: nn.Module) -> bool:
        if self.gate_matcher is not None:
            return self.gate_matcher(name, module)
        if not isinstance(module, nn.Linear):
            return False
        if not any(re.search(p, name) for p in self.gate_patterns):
            return False
        # Guard against FFN projections that slip through a name match: a
        # router's output dimension is the (small) expert count.
        if module.out_features > self.max_gate_out_features:
            return False
        return True

    def attach(self, model: nn.Module) -> int:
        """Register hooks on every module that matches the gate predicate.

        Returns the number of gates hooked. Raises if zero — that almost
        always means the matcher is wrong for your model architecture.
        """
        self.detach()
        layer_idx = 0
        seen_layers: dict[str, int] = {}
        for name, module in model.named_modules():
            if not self._is_gate(name, module):
                continue
            # Extract a layer index from the qualified name (e.g.
            # "model.layers.5.block_sparse_moe.gate" -> 5). Fall back to
            # monotonic counter.
            m = re.search(r"\.layers\.(\d+)\.", name)
            if m:
                this_idx = int(m.group(1))
            else:
                this_idx = seen_layers.get(name, layer_idx)
                layer_idx += 1
            seen_layers[name] = this_idx
            self._layer_index[name] = this_idx
            handle = module.register_forward_hook(self._make_hook(name))
            self._hooks.append(handle)

        if not self._hooks:
            raise RuntimeError(
                "RouterProbe.attach() found no gate modules. The default "
                "matcher targets HF MoE naming conventions; pass "
                "gate_matcher=... if your model uses a different layout."
            )
        return len(self._hooks)

    def detach(self) -> None:
        for h in self._hooks:
            h.remove()
        self._hooks.clear()

    # ------------------------------------------------------------------
    # Hook factory
    # ------------------------------------------------------------------

    def _make_hook(self, name: str) -> Callable:
        layer_idx = self._layer_index[name]

        def _hook(_module: nn.Module, _inp: tuple, out: torch.Tensor) -> None:
            # `out` is the gate logits, shape (..., num_experts). Flatten
            # leading dims to get a 2D (token, expert) tensor.
            if not isinstance(out, torch.Tensor):
                # Some implementations return a tuple, e.g. Qwen3MoeTopKRouter
                # returns (router_probs, router_scores, router_indices).
                out = (
                    out[self.output_index]
                    if isinstance(out, (tuple, list)) and len(out) > self.output_index
                    else None
                )
            if out is None or out.dim() < 2:
                return
            vals = out.detach().reshape(-1, out.shape[-1])  # (T, E)
            with torch.no_grad():
                if self.output_is_probs:
                    # Already a softmax distribution; renormalise defensively.
                    probs = vals.float().clamp_min(0.0)
                    probs = probs / probs.sum(dim=-1, keepdim=True).clamp_min(1e-12)
                else:
                    probs = torch.softmax(vals.float(), dim=-1)
                top2_vals, top2_idx = torch.topk(probs, k=min(2, probs.shape[-1]), dim=-1)
                # Per-token softmax entropy in nats.
                entropy = -(probs * (probs.clamp_min(1e-12).log())).sum(dim=-1)

            probs_cpu = probs.cpu() if self.store_probs else None
            base = self._token_counter[name]
            for i in range(vals.shape[0]):
                if len(self.records) >= self.max_records:
                    return
                self.records.append(
                    RouterRecord(
                        layer_name=name,
                        layer_idx=layer_idx,
                        token_global_idx=base + i,
                        top1_expert=int(top2_idx[i, 0].item()),
                        top2_expert=int(top2_idx[i, 1].item()) if top2_idx.shape[-1] > 1 else -1,
                        top1_prob=float(top2_vals[i, 0].item()),
                        top2_prob=float(top2_vals[i, 1].item()) if top2_vals.shape[-1] > 1 else 0.0,
                        entropy=float(entropy[i].item()),
                        probs=tuple(probs_cpu[i].tolist()) if probs_cpu is not None else None,
                    )
                )
            self._token_counter[name] = base + vals.shape[0]

        return _hook

    # ------------------------------------------------------------------
    # Aggregation & comparison
    # ------------------------------------------------------------------

    def to_dataframe(self):
        """Return a pandas DataFrame of all records, or None if pandas is missing."""
        try:
            import pandas as pd
        except ImportError:
            return None
        return pd.DataFrame([r.__dict__ for r in self.records])

    def summary(self) -> dict[str, Any]:
        """Per-layer aggregate stats."""
        per_layer: dict[int, list[RouterRecord]] = defaultdict(list)
        for r in self.records:
            per_layer[r.layer_idx].append(r)
        out: dict[int, dict[str, float]] = {}
        for idx, recs in per_layer.items():
            mean_top1_prob = sum(r.top1_prob for r in recs) / len(recs)
            mean_entropy = sum(r.entropy for r in recs) / len(recs)
            out[idx] = {
                "n_tokens": len(recs),
                "mean_top1_prob": mean_top1_prob,
                "mean_entropy": mean_entropy,
            }
        return {
            "n_records": len(self.records),
            "n_gates": len(self._layer_index),
            "per_layer": out,
        }

    @staticmethod
    def compare(probe_a: "RouterProbe", probe_b: "RouterProbe") -> dict[str, Any]:
        """Compute flip-rate, Jaccard and (optional) KL between two aligned runs.

        Alignment requires the same model, same calibration data, and same
        layer set. Records are aligned by ``(layer_name, token_global_idx)``.
        Keying on ``layer_name`` (not ``layer_idx``) is important: two matched
        gate modules can share the same numeric layer index (e.g. a dense +
        a MoE block, or a mis-configured matcher), which would silently
        cross-align unrelated tokens if keyed on the index alone.

        If both probes were run with ``store_probs=True`` the per-token KL
        divergence ``KL(P_a || P_b)`` over the expert softmax is also returned;
        otherwise the KL fields are ``None``.
        """
        # Index a's records by (layer_name, token_global_idx).
        a_idx: dict[tuple[str, int], RouterRecord] = {}
        for r in probe_a.records:
            a_idx[(r.layer_name, r.token_global_idx)] = r

        per_layer_total: dict[int, int] = defaultdict(int)
        per_layer_flips: dict[int, int] = defaultdict(int)
        jaccard_sum = 0.0
        jaccard_count = 0
        kl_sum = 0.0
        kl_count = 0

        total = 0
        flips = 0
        for r_b in probe_b.records:
            r_a = a_idx.get((r_b.layer_name, r_b.token_global_idx))
            if r_a is None:
                continue
            total += 1
            per_layer_total[r_b.layer_idx] += 1
            flipped = r_a.top1_expert != r_b.top1_expert
            if flipped:
                flips += 1
                per_layer_flips[r_b.layer_idx] += 1
            top2_a = {r_a.top1_expert, r_a.top2_expert} - {-1}
            top2_b = {r_b.top1_expert, r_b.top2_expert} - {-1}
            inter = len(top2_a & top2_b)
            union = len(top2_a | top2_b)
            if union:
                jaccard_sum += 1 - (inter / union)
                jaccard_count += 1
            if r_a.probs is not None and r_b.probs is not None and len(r_a.probs) == len(r_b.probs):
                kl = 0.0
                for pa, pb in zip(r_a.probs, r_b.probs):
                    if pa > 0.0:
                        kl += pa * math.log(pa / max(pb, 1e-12))
                kl_sum += kl
                kl_count += 1

        per_layer_rate = {
            idx: per_layer_flips[idx] / n for idx, n in per_layer_total.items()
        }
        return {
            "n_aligned_records": total,
            "top1_flip_rate_overall": flips / total if total else float("nan"),
            "per_layer_flip_rate": per_layer_rate,
            "jaccard_topk_mean": jaccard_sum / jaccard_count if jaccard_count else float("nan"),
            "kl_mean": kl_sum / kl_count if kl_count else None,
            "n_kl_records": kl_count,
        }


__all__ = [
    "RouterProbe",
    "RouterRecord",
    "DEFAULT_GATE_PATTERNS",
    "DEFAULT_MAX_GATE_OUT_FEATURES",
]
