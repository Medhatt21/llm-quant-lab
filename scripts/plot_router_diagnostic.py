"""Per-layer router-disruption figure for the Qwen3-30B-A3B diagnostic.

Reads reports/moe_probe/qwen3_moe_sq.json and renders per-layer top-1 expert
flip rate, showing that SmoothQuant W8A8 routing disruption is localized to the
deep layers. Saved into the paper figures dir.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "reports" / "moe_probe" / "qwen3_moe_sq.json"
OUT = REPO / "papers" / "iiswc2026" / "figures"


def main() -> int:
    d = json.loads(SRC.read_text())
    per = d["per_layer_flip_rate"]
    layers = sorted(int(k) for k in per)
    rates = [per[str(k)] * 100 for k in layers]
    overall = d["top1_flip_rate_overall"] * 100

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.bar(layers, rates, color="#a855f7", alpha=0.85, width=0.8)
    ax.axhline(overall, color="#ef4444", ls="--", lw=1.3,
               label=f"overall {overall:.1f}%")
    ax.set_xlabel("MoE layer index", fontsize=9)
    ax.set_ylabel("top-1 expert flip rate (%)", fontsize=9)
    ax.set_title(
        f"Router disruption under SmoothQuant W8A8 — {d['model']}\n"
        f"({d['num_experts']} experts, top-8; {d['n_aligned_records']:,} token-routes; "
        f"Jaccard {d['jaccard_topk_mean']:.3f}, KL {d['kl_mean']:.4f})",
        fontsize=8.5, fontweight="bold")
    ax.legend(fontsize=8, frameon=True)
    ax.grid(axis="y", alpha=0.3)
    ax.set_xlim(-1, max(layers) + 1)
    fig.tight_layout()

    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"qwen3_router_disruption.{ext}", dpi=300, bbox_inches="tight")
    print(f"[plot] wrote {OUT}/qwen3_router_disruption.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
