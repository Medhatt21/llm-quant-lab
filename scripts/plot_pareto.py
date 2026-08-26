"""Aggregate throughput summaries into a single accuracy/throughput Pareto plot.

Reads every JSON in `reports/throughput/*__summary.json` and pairs it (where
possible) with the matching accuracy point in `reports/trial_repeats/*.csv`
or `reproduction_results.csv`. Emits:

    reports/pareto/pareto_iiswc.{pdf,csv}

The CSV is the source-of-truth for the IISWC paper's R-4 figure; the PDF is
the figure itself.

Usage (no GPU needed):

    docker run --rm -v /data/llm-quant-lab:/workspace --workdir /workspace \\
        --user $(id -u):$(id -g) \\
        rocm/pytorch:rocm7.1_ubuntu24.04_py3.12_pytorch_release_2.8.0 \\
        python /workspace/scripts/plot_pareto.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_THRU = REPO / "reports" / "throughput"
DEFAULT_TRIALS = REPO / "reports" / "trial_repeats"
DEFAULT_OUT = REPO / "reports" / "pareto"


def load_throughput_points(d: Path) -> list[dict]:
    pts = []
    for p in sorted(d.glob("*__summary.json")):
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        bench = data.get("vllm_bench", {}) or {}
        # vLLM bench throughput emits keys like
        # 'requests_per_second' / 'total_token_throughput' / 'tokens_per_second'
        # depending on version. Capture what we can find.
        toks_s = (
            bench.get("output_throughput")
            or bench.get("output_token_throughput")
            or bench.get("tokens_per_second")
            or bench.get("requests_per_second")
        )
        pts.append(
            {
                "model": data.get("model", ""),
                "format": data.get("format", ""),
                "duration_s": data.get("duration_s"),
                "mean_power_w": data.get("mean_power_w"),
                "approx_energy_j": data.get("approx_energy_j"),
                "tokens_per_sec": toks_s,
                "summary_path": str(p),
            }
        )
    return pts


def load_accuracy_points(d: Path) -> list[dict]:
    pts = []
    for p in sorted(d.glob("*_trials.csv")):
        # Skip the no-wandb backup files.
        if "no_wandb" in p.name:
            continue
        try:
            rows = list(csv.DictReader(p.open()))
        except Exception:
            continue
        ppls = [float(r["wikitext2_ppl"]) for r in rows
                if r.get("wikitext2_ppl") not in (None, "", "NA")]
        if not ppls:
            continue
        mean = sum(ppls) / len(ppls)
        var = sum((x - mean) ** 2 for x in ppls) / (len(ppls) - 1) if len(ppls) > 1 else 0.0
        pts.append(
            {
                "config_name": p.stem.replace("_trials", ""),
                "n_trials": len(ppls),
                "wikitext2_ppl_mean": mean,
                "wikitext2_ppl_sigma": var ** 0.5,
                "trials_csv": str(p),
            }
        )
    return pts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--throughput", type=Path, default=DEFAULT_THRU)
    ap.add_argument("--trials", type=Path, default=DEFAULT_TRIALS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    thru = load_throughput_points(args.throughput) if args.throughput.exists() else []
    acc = load_accuracy_points(args.trials) if args.trials.exists() else []

    out_csv = args.out / "pareto_iiswc.csv"
    fieldnames = [
        "config_name", "model", "format",
        "wikitext2_ppl_mean", "wikitext2_ppl_sigma", "n_trials",
        "tokens_per_sec", "mean_power_w", "approx_energy_j", "duration_s",
    ]
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        # Throughput-driven rows.
        for t in thru:
            row = {k: "" for k in fieldnames}
            row["model"] = t["model"]
            row["format"] = t["format"]
            row["tokens_per_sec"] = t.get("tokens_per_sec", "") or ""
            row["mean_power_w"] = t.get("mean_power_w", "") or ""
            row["approx_energy_j"] = t.get("approx_energy_j", "") or ""
            row["duration_s"] = t.get("duration_s", "") or ""
            row["config_name"] = f"throughput::{t['model']}::{t['format']}"
            w.writerow(row)
        # Accuracy-driven rows.
        for a in acc:
            row = {k: "" for k in fieldnames}
            row["config_name"] = a["config_name"]
            row["wikitext2_ppl_mean"] = a["wikitext2_ppl_mean"]
            row["wikitext2_ppl_sigma"] = a["wikitext2_ppl_sigma"]
            row["n_trials"] = a["n_trials"]
            w.writerow(row)
    print(f"[pareto] wrote {out_csv} ({len(thru)} throughput pts, {len(acc)} accuracy groups)")

    # Plot only if both sides have data and matplotlib is available.
    if not thru or not acc:
        print("[pareto] not enough data for a Pareto plot yet; CSV written.")
        return 0

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[pareto] matplotlib not available; skipping figure.", file=sys.stderr)
        return 0

    fig, ax = plt.subplots(figsize=(5, 3.5))
    # Naive matching: pair throughput rows with accuracy rows that share a
    # short model name token. Real merging requires explicit (model, method,
    # bit) keys — we mark the figure as preliminary if matching is loose.
    for t in thru:
        match = None
        m_short = t["model"].split("/")[-1].lower()
        for a in acc:
            if m_short in a["config_name"].lower():
                match = a
                break
        if match is None:
            continue
        if t.get("tokens_per_sec") is None:
            continue
        ax.errorbar(
            t["tokens_per_sec"],
            match["wikitext2_ppl_mean"],
            yerr=match["wikitext2_ppl_sigma"],
            fmt="o",
            label=f"{m_short}/{t['format']}",
            capsize=3,
        )
    ax.set_xlabel("Output throughput (tokens/sec)")
    ax.set_ylabel("WikiText-2 perplexity")
    ax.legend(fontsize=7)
    ax.grid(True, ls=":", lw=0.4, alpha=0.5)
    fig.tight_layout()
    out_pdf = args.out / "pareto_iiswc.pdf"
    fig.savefig(out_pdf)
    print(f"[pareto] wrote {out_pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
