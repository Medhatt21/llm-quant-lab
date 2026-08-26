"""Error-bar figure for the repeatability panel (IISWC #414 rebuttal).

Reads reports/repeatability/summary.csv and renders mean +/- SD per
(config, platform) with the CV annotated, so run-to-run variance is shown
explicitly rather than implied. Saved into the paper figures dir.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
SUMMARY = REPO / "reports" / "repeatability" / "summary.csv"
OUT = REPO / "papers" / "iiswc2026" / "figures"

PLAT_COLOR = {"amd_mi300x": "#ef4444", "nvidia_a10g": "#0ea5e9"}
PLAT_LABEL = {"amd_mi300x": "AMD MI300X (torch 2.9.1)", "nvidia_a10g": "NVIDIA A10G (torch 2.6.0)"}


def main() -> int:
    rows = [r for r in csv.DictReader(SUMMARY.open()) if r["n"]]
    configs = sorted({(r["method"], r["model"]) for r in rows})
    plats = ["amd_mi300x", "nvidia_a10g"]

    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.36
    x = np.arange(len(configs))
    for pi, plat in enumerate(plats):
        means, sds, cvs = [], [], []
        for cfg in configs:
            match = [r for r in rows if (r["method"], r["model"]) == cfg and r["platform"] == plat]
            if match:
                means.append(float(match[0]["mean_ppl"]))
                sds.append(float(match[0]["sd_ppl"]))
                cvs.append(float(match[0]["cv_pct"]))
            else:
                means.append(np.nan); sds.append(0.0); cvs.append(0.0)
        pos = x + (pi - 0.5) * width
        bars = ax.bar(pos, means, width, yerr=sds, capsize=5,
                      color=PLAT_COLOR[plat], alpha=0.85, label=PLAT_LABEL[plat],
                      error_kw={"elinewidth": 1.5, "ecolor": "#1a1a1a"})
        for xi, m, c in zip(pos, means, cvs):
            if not np.isnan(m):
                ax.text(xi, m + 0.35, f"CV {c:.2f}%", ha="center", va="bottom",
                        fontsize=7, color=PLAT_COLOR[plat], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{m.upper()}-W4\n{md}" for m, md in configs], fontsize=8)
    ax.set_ylabel("WikiText-2 perplexity (mean $\\pm$ SD, n=3)", fontsize=9)
    ax.set_title("Cross-hardware repeatability: n=3 calibration seeds per cell",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=7.5, frameon=True)
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(bottom=min(float(r["mean_ppl"]) for r in rows) - 2)
    fig.tight_layout()

    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"repeatability_errorbars.{ext}", dpi=300, bbox_inches="tight")
    print(f"[plot] wrote {OUT}/repeatability_errorbars.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
