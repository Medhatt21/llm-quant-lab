"""Repeatability + verdict-stability analysis for the IISWC #414 rebuttal.

Quantifies run-to-run repeatability and resolves the statistical unit behind
the reported experiment count. It:

1. Reports corpus units honestly: N metric rows vs M unique configurations.
2. Ingests every available multi-seed trial (AMD MI300X trial_repeats/*.csv
   and NVIDIA A10G seeded rows in reports/cuda_arm/cuda_results.csv) and
   computes per (config, platform): n, mean, sample SD, CV, min, max.
3. Computes the cross-hardware paired delta where both platforms have the
   same config, and flags whether the two arms shared a torch build.
4. Computes verdict stability at 2% / 5% / 10% thresholds against the paper
   reference value: a verdict is "stable" only if all trials agree.

Deterministic methods (RTN, LLM.int8()) that do not consume calibration
statistics are labelled process-reproducibility checks, not independent
calibration trials — their zero variance is reported as "no variation at
reported precision", not as evidence of statistical equivalence.

Outputs: reports/repeatability/{summary.csv, summary.md, corpus_units.json}
Run (host or container):
    python scripts/repeatability_analysis.py
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MASTER = REPO / "reproduction_results.csv"
TRIALS_DIR = REPO / "reports" / "trial_repeats"
CUDA_CSV = REPO / "reports" / "cuda_arm" / "cuda_results.csv"
OUT_DIR = REPO / "reports" / "repeatability"

# Methods whose LLMC implementation does not consume calibration statistics:
# repeated seeds are process-reproducibility checks, not independent trials.
DETERMINISTIC = {"rtn", "llmint8"}

AMD_TORCH = "2.9.1+rocm7.2.0"


def cv(xs: list[float]) -> float:
    m = statistics.fmean(xs)
    if m == 0 or len(xs) < 2:
        return 0.0
    return statistics.stdev(xs) / m * 100.0


def corpus_units() -> dict:
    rows = list(csv.DictReader(MASTER.open()))
    ids = {r["experiment_id"] for r in rows}
    ids_ref = {r["experiment_id"] for r in rows if r.get("paper_value", "")}
    by_method = defaultdict(int)
    for r in rows:
        by_method[r["method"]] += 1
    return {
        "metric_rows": len(rows),
        "unique_configurations": len(ids),
        "metric_rows_with_paper_ref": sum(1 for r in rows if r.get("paper_value", "")),
        "unique_configurations_with_paper_ref": len(ids_ref),
        "metric_rows_by_method": dict(by_method),
    }


def paper_ref_for(model_substr: str, method: str, bit: str) -> tuple[float, str] | None:
    """Look up the corpus paper_value + experiment_id for a config."""
    for r in csv.DictReader(MASTER.open()):
        if (
            r.get("dataset") == "wikitext2"
            and r.get("metric") == "perplexity"
            and r["method"].lower() == method
            and str(r.get("bit_width")) == str(bit)
            and model_substr in r["model"]
            and r.get("paper_value", "")
        ):
            try:
                return float(r["paper_value"]), r["experiment_id"]
            except ValueError:
                return None
    return None


def verdict_at(rel_pct: float, thr_close: float, thr_far: float) -> str:
    a = abs(rel_pct)
    if a < thr_close:
        return "match"
    if a < thr_far:
        return "close"
    return "worse" if rel_pct > 0 else "better"


def stability(trials: list[float], paper: float) -> dict:
    """Verdict stability across thresholds; stable iff all trials agree."""
    out = {}
    for close, far in [(2, 4), (5, 10), (10, 20)]:
        verdicts = {verdict_at((t - paper) / paper * 100.0, close, far) for t in trials}
        out[f"thr{close}"] = {
            "verdicts": sorted(verdicts),
            "stable": len(verdicts) == 1,
        }
    return out


def collect() -> list[dict]:
    """One record per (config, platform) with trial stats."""
    groups: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    meta: dict[tuple, dict] = {}

    # AMD MI300X trials.
    for f in sorted(TRIALS_DIR.glob("*_trials.csv")):
        name = f.stem.replace("_trials", "")
        m = re.match(r"(gptq|rtn|awq|smoothquant|llmint8)_([a-z0-9\.\-]+)", name)
        method = m.group(1) if m else name.split("_")[0]
        model = m.group(2) if m else name
        for row in csv.DictReader(f.open()):
            v = row.get("wikitext2_ppl", "")
            if v in ("", "NA"):
                continue
            key = (method, model, "amd_mi300x", AMD_TORCH)
            groups[key].append(float(v))
            meta[key] = {"source": str(f.relative_to(REPO))}

    # NVIDIA A10G seeded rows from the cuda arm.
    if CUDA_CSV.exists():
        seed_rows: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        torch_of: dict[tuple, str] = {}
        for row in csv.DictReader(CUDA_CSV.open()):
            cn = row.get("config_name", "")
            sm = re.search(r"__seed(\d+)$", cn)
            if not sm:
                continue
            base = re.sub(r"__seed\d+$", "", cn)
            bm = re.match(r"(gptq|rtn|awq|smoothquant|llmint8)_([a-z0-9\.\-]+)", base)
            method = bm.group(1) if bm else row["method"].lower()
            model = bm.group(2) if bm else "?"
            k = (method, model, "nvidia_a10g")
            seed_rows[k].append(float(row["wikitext2_ppl"]))
            torch_of[k] = row.get("torch_version", "unknown")
        for (method, model, plat), vals in seed_rows.items():
            key = (method, model, plat, torch_of[(method, model, plat)])
            groups[key] = vals
            meta[key] = {"source": str(CUDA_CSV.relative_to(REPO))}

    records = []
    for (method, model, platform, torch_v), vals in sorted(groups.items()):
        n = len(vals)
        mean = statistics.fmean(vals)
        sd = statistics.stdev(vals) if n > 1 else 0.0
        model_sub = {"opt125m": "opt-125m", "opt2.7b": "opt-2.7b"}.get(model, model)
        bit = "8" if method in ("smoothquant", "llmint8") else ("4" if method != "rtn" else "4")
        ref = paper_ref_for(model_sub, method, bit)
        rec = {
            "method": method,
            "model": model,
            "platform": platform,
            "torch": torch_v,
            "n": n,
            "mean_ppl": round(mean, 4),
            "sd_ppl": round(sd, 4),
            "cv_pct": round(cv(vals), 3),
            "min_ppl": round(min(vals), 4),
            "max_ppl": round(max(vals), 4),
            "deterministic_method": method in DETERMINISTIC,
            "trial_type": "process-repro" if method in DETERMINISTIC else "calibration",
            "trials": [round(v, 6) for v in vals],
            "source": meta[(method, model, platform, torch_v)]["source"],
        }
        if ref:
            paper, expid = ref
            rec["experiment_id"] = expid
            rec["paper_value"] = paper
            rec["verdict_stability"] = stability(vals, paper)
        records.append(rec)
    return records


def cross_hardware(records: list[dict]) -> list[dict]:
    by_cfg: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for r in records:
        by_cfg[(r["method"], r["model"])][r["platform"]] = r
    out = []
    for (method, model), plats in by_cfg.items():
        if "amd_mi300x" in plats and "nvidia_a10g" in plats:
            a, n = plats["amd_mi300x"], plats["nvidia_a10g"]
            delta = (a["mean_ppl"] - n["mean_ppl"]) / n["mean_ppl"] * 100.0
            out.append({
                "method": method,
                "model": model,
                "amd_mean": a["mean_ppl"],
                "nvidia_mean": n["mean_ppl"],
                "amd_vs_nvidia_pct": round(delta, 4),
                "stack_matched": a["torch"] == n["torch"],
                "amd_torch": a["torch"],
                "nvidia_torch": n["torch"],
                "note": "exact bitwise agreement" if a["mean_ppl"] == n["mean_ppl"] else "",
            })
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    units = corpus_units()
    records = collect()
    xhw = cross_hardware(records)

    (OUT_DIR / "corpus_units.json").write_text(json.dumps(units, indent=2))
    (OUT_DIR / "cross_hardware.json").write_text(json.dumps(xhw, indent=2))

    cols = ["method", "model", "platform", "torch", "n", "mean_ppl", "sd_ppl",
            "cv_pct", "min_ppl", "max_ppl", "trial_type", "source"]
    with (OUT_DIR / "summary.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({k: r.get(k, "") for k in cols})

    lines = ["# Repeatability & verdict-stability summary", ""]
    lines.append(f"- Corpus: **{units['metric_rows']} metric measurements from "
                 f"{units['unique_configurations']} unique configurations** "
                 f"({units['metric_rows_with_paper_ref']} measurements across "
                 f"{units['unique_configurations_with_paper_ref']} configs have paper refs).")
    lines.append("")
    lines.append("## Per-config repeatability")
    lines.append("")
    lines.append("| method | model | platform | torch | n | mean | SD | CV% | type |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in records:
        lines.append(f"| {r['method']} | {r['model']} | {r['platform']} | {r['torch']} | "
                     f"{r['n']} | {r['mean_ppl']} | {r['sd_ppl']} | {r['cv_pct']} | {r['trial_type']} |")
    lines.append("")
    lines.append("## Cross-hardware paired deltas (same config, both platforms)")
    lines.append("")
    lines.append("| method | model | AMD mean | NVIDIA mean | AMD-vs-NVIDIA % | stack_matched | note |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in xhw:
        lines.append(f"| {r['method']} | {r['model']} | {r['amd_mean']} | {r['nvidia_mean']} | "
                     f"{r['amd_vs_nvidia_pct']} | {r['stack_matched']} | {r['note']} |")
    lines.append("")
    lines.append("## Verdict stability (all trials must agree to be stable)")
    lines.append("")
    for r in records:
        if "verdict_stability" in r:
            vs = r["verdict_stability"]
            flags = ", ".join(f"{t}:{'stable' if v['stable'] else 'UNSTABLE'}"
                              for t, v in vs.items())
            lines.append(f"- {r['method']}/{r['model']}/{r['platform']} "
                         f"(vs paper {r.get('paper_value')}): {flags}")
    (OUT_DIR / "summary.md").write_text("\n".join(lines) + "\n")

    print("\n".join(lines))
    print(f"\n[repeatability] wrote {OUT_DIR}/summary.{{csv,md}}, corpus_units.json, cross_hardware.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
