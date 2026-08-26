"""Corrected serving-efficiency summary (IISWC #414 rebuttal).

Note that reports/throughput/*__summary.json compute
`approx_energy_j = mean_power_w * duration_s`, where `duration_s` spans the
entire run (model load + idle + benchmark, ~112-116 s) while the vLLM
benchmark itself lasted only ~3.2 s. That number therefore overstates the
per-benchmark energy and mixes in loading/idle power.

This script recomputes a defensible serving-efficiency metric from the raw
per-sample power logs:

  - active_power_w : mean power over the high-power tail (top quartile of
    samples), a proxy for steady-state serving power (the load/idle ramp sits
    in the lower quartiles).
  - energy_per_1k_tokens_j : active_power_w / tokens_per_second * 1000, the
    metric that actually reflects inference efficiency.

It also flags runs whose `vllm_bench` is empty (no valid throughput captured),
so they are not silently presented as efficiency cells.

Output: reports/throughput/corrected_summary.{json,md}
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TDIR = REPO / "reports" / "throughput"


def active_power(power_csv: Path) -> tuple[float, float, int]:
    vals = []
    with power_csv.open() as fh:
        for row in csv.DictReader(fh):
            try:
                vals.append(float(row["power_w"]))
            except (KeyError, ValueError):
                pass
    if not vals:
        return 0.0, 0.0, 0
    vals_sorted = sorted(vals)
    q75_idx = int(len(vals_sorted) * 0.75)
    tail = vals_sorted[q75_idx:] or vals_sorted[-1:]
    return statistics.fmean(tail), max(vals), len(vals)


def main() -> int:
    rows = []
    for summ in sorted(TDIR.glob("*__summary.json")):
        d = json.loads(summ.read_text())
        stem = summ.name.replace("__summary.json", "")
        bench = d.get("vllm_bench") or {}
        tps = bench.get("tokens_per_second")
        power_csv = TDIR / f"{stem}.power.csv"
        act_w, peak_w, n = active_power(power_csv) if power_csv.exists() else (0.0, 0.0, 0)
        rec = {
            "model": d.get("model"),
            "format": d.get("format"),
            "gpu": d.get("gpu"),
            "tokens_per_second": round(tps, 1) if tps else None,
            "has_valid_benchmark": bool(tps),
            "active_power_w": round(act_w, 1),
            "peak_power_w": round(peak_w, 1),
            "reported_mean_power_w": d.get("mean_power_w"),
            "reported_energy_j_FULL_WINDOW": round(d.get("approx_energy_j", 0), 1),
            "energy_per_1k_tokens_j": round(act_w / tps * 1000, 2) if tps else None,
            "n_power_samples": n,
            "note": "" if tps else "no valid vLLM benchmark captured (vllm_bench empty)",
        }
        rows.append(rec)

    (TDIR / "corrected_summary.json").write_text(json.dumps(rows, indent=2))

    lines = ["# Corrected serving-efficiency summary", "",
             "Energy recomputed over steady-state serving power (top-quartile of "
             "power samples), not the full load+idle window. `reported_energy_j_"
             "FULL_WINDOW` is the old (overstated) number, kept for transparency.",
             "",
             "| model | fmt | tok/s | active W | peak W | E/1k-tok (J) | old E (J, full window) | note |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(
            f"| {r['model'].split('/')[-1]} | {r['format']} | {r['tokens_per_second']} | "
            f"{r['active_power_w']} | {r['peak_power_w']} | {r['energy_per_1k_tokens_j']} | "
            f"{r['reported_energy_j_FULL_WINDOW']} | {r['note']} |")
    (TDIR / "corrected_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n[energy] wrote {TDIR}/corrected_summary.{{json,md}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
