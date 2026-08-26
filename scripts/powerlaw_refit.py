"""Per-method power-law refit with bootstrap CIs.

Addresses reviewer rejection points R-5 / R-10:

R-5 — the pooled |delta| = alpha * N^beta fit (R^2 = 0.71) lumps 5 methods,
23 models, 4 bit-widths, 1 trial per cell. The fit is too heterogeneous to
support a "law" claim.

R-10 — Dettmers & Zettlemoyer (2023) already established that larger models
are more robust to quantization; our contribution must be a method-specific
exponent with a confidence interval, not a single pooled R^2.

What this script produces:

    reports/powerlaw/per_method_fit.csv
        method, n_points, alpha, alpha_ci_lo, alpha_ci_hi,
                          beta,  beta_ci_lo,  beta_ci_hi,
                          r2

    reports/powerlaw/per_method_fit.tex (booktabs)
    reports/powerlaw/per_method_curves.pdf

Run with the project venv:

    docker exec llm-quant-devvvvv python /workspace/scripts/powerlaw_refit.py
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO / "reproduction_results.csv"
OUT_DIR = REPO / "reports" / "powerlaw"

# Approximate parameter counts (in M params). Used only for the scaling fit.
# Source: each model's HF model card / paper. Update as needed.
PARAM_COUNT_M = {
    "facebook/opt-125m": 125,
    "facebook/opt-350m": 350,
    "facebook/opt-1.3b": 1_300,
    "facebook/opt-2.7b": 2_700,
    "facebook/opt-6.7b": 6_700,
    "facebook/opt-13b": 13_000,
    "facebook/opt-30b": 30_000,
    "facebook/opt-66b": 66_000,
    "facebook/opt-iml-30b": 30_000,
    "bigscience/bloom-560m": 560,
    "bigscience/bloom-1b1": 1_100,
    "bigscience/bloom-1b7": 1_700,
    "bigscience/bloom-3b": 3_000,
    "bigscience/bloom-7b1": 7_100,
    "huggyllama/llama-7b": 7_000,
    "huggyllama/llama-13b": 13_000,
    "huggyllama/llama-30b": 30_000,
    "huggyllama/llama-65b": 65_000,
    "meta-llama/Llama-2-7b-hf": 7_000,
    "meta-llama/Llama-2-13b-hf": 13_000,
    "meta-llama/Llama-2-70b-hf": 70_000,
    "meta-llama/Llama-3.1-8B": 8_000,
    "mistralai/Mistral-7B-v0.1": 7_000,
    "mistralai/Mistral-7B-Instruct-v0.2": 7_000,
    "mistralai/Mixtral-8x7B-v0.1": 47_000,  # active ~13B; total params used
    "mistralai/Mixtral-8x7B-Instruct-v0.1": 47_000,
}


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def filter_for_fit(rows: list[dict[str, str]], metric: str = "perplexity") -> list[dict[str, float]]:
    """Keep only rows with both AMD and paper values, and a known param count.

    The paper's power-law claim is on perplexity. Mixing perplexity and accuracy
    deltas is ill-defined (relative direction differs), so we filter to one metric.
    """
    fit_rows: list[dict[str, float]] = []
    for r in rows:
        if r.get("metric", "").strip() != metric:
            continue
        amd = r.get("amd_value", "").strip()
        paper = r.get("paper_value", "").strip()
        if not amd or not paper:
            continue
        try:
            amd_f = float(amd)
            paper_f = float(paper)
        except ValueError:
            continue
        if paper_f <= 0:
            continue
        # Skip the Mixtral SmoothQuant catastrophic outlier — it is the
        # subject of a separate failure-mode analysis and would dominate any
        # fit. Keep all other points.
        if (
            r["model"].startswith("mistralai/Mixtral")
            and r["method"].lower() == "smoothquant"
            and abs(amd_f - paper_f) / paper_f > 100
        ):
            continue
        params_m = PARAM_COUNT_M.get(r["model"])
        if params_m is None:
            continue
        delta_pct = abs(amd_f - paper_f) / paper_f * 100.0
        fit_rows.append(
            {
                "method": r["method"].lower(),
                "model": r["model"],
                "params_m": float(params_m),
                "abs_delta_pct": delta_pct,
            }
        )
    return fit_rows


def fit_power_law(params: np.ndarray, deltas: np.ndarray) -> tuple[float, float, float]:
    """Fit |delta_pct| = alpha * params^beta in log space. Returns (alpha, beta, r2)."""
    mask = (params > 0) & (deltas > 0)
    if mask.sum() < 3:
        return float("nan"), float("nan"), float("nan")
    x = np.log(params[mask])
    y = np.log(deltas[mask])
    beta, log_alpha = np.polyfit(x, y, 1)
    alpha = float(np.exp(log_alpha))
    y_hat = beta * x + log_alpha
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return alpha, float(beta), r2


def bootstrap_ci(
    params: np.ndarray,
    deltas: np.ndarray,
    n_boot: int = 1000,
    seed: int = 42,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Returns ((alpha_lo, alpha_hi), (beta_lo, beta_hi)) at 95% CI."""
    rng = np.random.default_rng(seed)
    n = len(params)
    if n < 3:
        return (float("nan"), float("nan")), (float("nan"), float("nan"))
    alphas, betas = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        a, b, _ = fit_power_law(params[idx], deltas[idx])
        if not np.isnan(a):
            alphas.append(a)
            betas.append(b)
    if not alphas:
        return (float("nan"), float("nan")), (float("nan"), float("nan"))
    alpha_lo, alpha_hi = np.percentile(alphas, [2.5, 97.5])
    beta_lo, beta_hi = np.percentile(betas, [2.5, 97.5])
    return (float(alpha_lo), float(alpha_hi)), (float(beta_lo), float(beta_hi))


def write_csv(out_path: Path, rows: list[dict[str, object]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_tex(out_path: Path, rows: list[dict[str, object]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"  \toprule",
        r"  Method & $N$ & $\hat{\alpha}$ (95\% CI) & $\hat{\beta}$ (95\% CI) & $R^2$ \\",
        r"  \midrule",
    ]
    for r in rows:
        if r["n_points"] < 3:
            continue
        lines.append(
            "  {method} & {n} & {alpha:.2f}\\,[{a_lo:.2f},\\,{a_hi:.2f}] & "
            "{beta:.3f}\\,[{b_lo:.3f},\\,{b_hi:.3f}] & {r2:.2f} \\\\".format(
                method=r["method"],
                n=int(r["n_points"]),
                alpha=float(r["alpha"]),
                a_lo=float(r["alpha_ci_lo"]),
                a_hi=float(r["alpha_ci_hi"]),
                beta=float(r["beta"]),
                b_lo=float(r["beta_ci_lo"]),
                b_hi=float(r["beta_ci_hi"]),
                r2=float(r["r2"]),
            )
        )
    lines += [r"  \bottomrule", r"\end{tabular}"]
    out_path.write_text("\n".join(lines) + "\n")


def maybe_plot(out_path: Path, fit_rows: list[dict[str, float]]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not available; skipping curve PDF.", file=sys.stderr)
        return

    fig, ax = plt.subplots(figsize=(5, 3.5))
    methods = sorted({r["method"] for r in fit_rows})
    colors = plt.cm.tab10(np.linspace(0, 1, len(methods)))
    x_grid = np.logspace(2, 5, 100)  # 100M to 100B params

    for method, color in zip(methods, colors):
        sub = [r for r in fit_rows if r["method"] == method]
        if len(sub) < 3:
            continue
        params = np.array([r["params_m"] for r in sub])
        deltas = np.array([r["abs_delta_pct"] for r in sub])
        alpha, beta, _ = fit_power_law(params, deltas)
        if np.isnan(alpha):
            continue
        ax.scatter(params, deltas, color=color, s=18, alpha=0.6, label=f"{method} ({len(sub)})")
        ax.plot(x_grid, alpha * x_grid**beta, color=color, lw=1.0, ls="--")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Model size (M params)")
    ax.set_ylabel(r"$|\delta|$ vs. paper (\%)")
    ax.legend(loc="best", fontsize=7)
    ax.grid(True, which="both", ls=":", lw=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_path)
    print(f"[plot] wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"[error] CSV not found: {args.csv}", file=sys.stderr)
        return 1

    rows = filter_for_fit(load_rows(args.csv))
    if not rows:
        print("[error] no usable rows after filtering.", file=sys.stderr)
        return 1

    methods = sorted({r["method"] for r in rows})
    summary: list[dict[str, object]] = []
    for method in methods:
        sub = [r for r in rows if r["method"] == method]
        params = np.array([r["params_m"] for r in sub])
        deltas = np.array([r["abs_delta_pct"] for r in sub])
        alpha, beta, r2 = fit_power_law(params, deltas)
        (a_lo, a_hi), (b_lo, b_hi) = bootstrap_ci(params, deltas, n_boot=args.n_boot)
        summary.append(
            {
                "method": method,
                "n_points": len(sub),
                "alpha": alpha,
                "alpha_ci_lo": a_lo,
                "alpha_ci_hi": a_hi,
                "beta": beta,
                "beta_ci_lo": b_lo,
                "beta_ci_hi": b_hi,
                "r2": r2,
            }
        )

    # Pooled fit too (for direct comparison with the paper's R^2 = 0.71 claim).
    params_all = np.array([r["params_m"] for r in rows])
    deltas_all = np.array([r["abs_delta_pct"] for r in rows])
    a, b, r2 = fit_power_law(params_all, deltas_all)
    (a_lo, a_hi), (b_lo, b_hi) = bootstrap_ci(params_all, deltas_all, n_boot=args.n_boot)
    summary.append(
        {
            "method": "pooled",
            "n_points": len(rows),
            "alpha": a,
            "alpha_ci_lo": a_lo,
            "alpha_ci_hi": a_hi,
            "beta": b,
            "beta_ci_lo": b_lo,
            "beta_ci_hi": b_hi,
            "r2": r2,
        }
    )

    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "per_method_fit.csv", summary)
    write_tex(args.out / "per_method_fit.tex", summary)
    maybe_plot(args.out / "per_method_curves.pdf", rows)

    print(f"[done] wrote {args.out / 'per_method_fit.csv'}")
    for r in summary:
        n = int(r["n_points"])
        if n < 3:
            print(f"  {r['method']:14s} N={n} (insufficient for fit)")
            continue
        print(
            f"  {r['method']:14s} N={n:3d}  "
            f"alpha={r['alpha']:6.3f} [{r['alpha_ci_lo']:.3f}, {r['alpha_ci_hi']:.3f}]  "
            f"beta={r['beta']:+.3f} [{r['beta_ci_lo']:+.3f}, {r['beta_ci_hi']:+.3f}]  "
            f"R2={r['r2']:.2f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
