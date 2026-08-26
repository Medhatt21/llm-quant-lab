"""Merge a CUDA-arm CSV (from scripts/run_cuda_arm.sh) into the master
reproduction_results.csv as the ``nvidia_value`` column.

Matching precedence (most to least specific):

1. ``experiment_id`` parsed from the CUDA ``config_name`` prefix (e.g.
   ``2525_gptq_w4`` -> experiment 2525). This is the *only* rigorous key: it
   ties a CUDA run to the exact YAML (and therefore the exact model revision,
   calibration set, seed, and quant config) that produced the AMD row.
2. Fallback ``(model, method, bit_width)`` for legacy CUDA rows whose
   ``config_name`` carries no numeric experiment id. These matches are marked
   ``key=loose`` so downstream analysis can exclude them.

For every matched row this script also records the NVIDIA-side provenance
(GPU, torch version, config sha) and a ``stack_matched`` flag comparing the
CUDA torch version against the pinned AMD stack. Because the archived CUDA
pilot ran on torch 2.6.0+cu124 while the AMD corpus is pinned to
2.9.1+rocm7.2.0, ``stack_matched`` is ``False`` for those rows: the artifact
now makes the software-version confound explicit instead of hiding it behind a
single ``nvidia_value`` number.

Usage:

    python scripts/merge_paired_results.py \\
        --master reproduction_results.csv \\
        --cuda  reports/cuda_arm/cuda_results.csv \\
        --out   reproduction_results_paired.csv \\
        --amd-torch 2.9.1+rocm7.2.0
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# Extra provenance columns appended to the paired output (never in master).
EXTRA_COLS = [
    "nvidia_gpu",
    "nvidia_torch_version",
    "nvidia_config_sha256",
    "match_key",
    "stack_matched",
]


def verdict(rel_pct: float) -> str:
    a = abs(rel_pct)
    if a < 5:
        return "match"
    if a < 10:
        return "close"
    if rel_pct <= -10:
        return "better"
    return "worse"


def experiment_id_from_name(config_name: str) -> str | None:
    m = re.match(r"^(\d+)", config_name or "")
    return m.group(1) if m else None


def torch_release(version: str) -> str:
    """Return the bare PyTorch release (``2.9.1``) from a full build string
    (``2.9.1+cu128`` / ``2.9.1+rocm7.2.0``). ``stack_matched`` compares releases
    because CUDA-vs-ROCm is the *intended* hardware axis of the paired study:
    once both arms run the same torch release, the local-suffix difference is
    exactly the backend we mean to compare, not a confound to hide."""
    return (version or "").split("+", 1)[0].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", type=Path, required=True)
    ap.add_argument("--cuda", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--amd-torch",
        default="2.9.1+rocm7.2.0",
        help="Pinned AMD torch build; CUDA rows on a different build are "
        "flagged stack_matched=False.",
    )
    args = ap.parse_args()

    if not args.master.exists():
        print(f"[error] master CSV not found: {args.master}", file=sys.stderr)
        return 1
    if not args.cuda.exists():
        print(f"[error] cuda-arm CSV not found: {args.cuda}", file=sys.stderr)
        return 1

    # Index CUDA results by experiment_id (strict) and (model, method, bit)
    # (loose). Later rows with the same key win, matching prior behaviour.
    cuda_by_expid: dict[str, dict[str, str]] = {}
    cuda_by_triple: dict[tuple[str, str, str], dict[str, str]] = {}
    with args.cuda.open(newline="") as fh:
        for row in csv.DictReader(fh):
            expid = experiment_id_from_name(row.get("config_name", ""))
            if expid is not None:
                cuda_by_expid[expid] = row
            triple = (row["model"], row["method"].lower(), str(row["bit_width"]))
            cuda_by_triple[triple] = row

    matched = matched_loose = unmatched_master = 0
    matched_expids: set[str] = set()
    matched_triples: set[tuple[str, str, str]] = set()
    out_rows: list[dict[str, str]] = []

    with args.master.open(newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        out_fields = fieldnames + [c for c in EXTRA_COLS if c not in fieldnames]
        for row in reader:
            for c in EXTRA_COLS:
                row.setdefault(c, "")
            if row.get("dataset") != "wikitext2" or row.get("metric") != "perplexity":
                out_rows.append(row)
                continue

            expid = str(row.get("experiment_id", "")).strip()
            triple = (row["model"], row["method"].lower(), str(row.get("bit_width", "16")))
            cuda = cuda_by_expid.get(expid)
            match_key = "experiment_id"
            if cuda is None:
                cuda = cuda_by_triple.get(triple)
                match_key = "loose"
            if cuda is None:
                unmatched_master += 1
                out_rows.append(row)
                continue

            try:
                amd = float(row["amd_value"])
                nvd = float(cuda["wikitext2_ppl"])
            except (KeyError, ValueError, TypeError):
                out_rows.append(row)
                continue

            cuda_torch = cuda.get("torch_version", "unknown")
            row["nvidia_value"] = f"{nvd:.6g}"
            row["nvidia_gpu"] = cuda.get("gpu_name", "")
            row["nvidia_torch_version"] = cuda_torch
            row["nvidia_config_sha256"] = cuda.get("config_sha256", "")
            row["match_key"] = match_key
            row["stack_matched"] = str(
                torch_release(cuda_torch) == torch_release(args.amd_torch)
            )
            if amd != 0:
                rel = (amd - nvd) / nvd * 100.0
                row["nvidia_diff_pct"] = f"{rel:.4f}"
                row["nvidia_verdict"] = verdict(rel)

            if match_key == "experiment_id":
                matched += 1
                matched_expids.add(expid)
            else:
                matched_loose += 1
                matched_triples.add(triple)
            out_rows.append(row)

    unmatched_cuda = [
        r for k, r in cuda_by_expid.items() if k not in matched_expids
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_fields)
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r.get(k, "") for k in out_fields})

    print(f"[merge] matched {matched} rows by experiment_id (strict)")
    print(f"[merge] matched {matched_loose} rows by (model,method,bit) (loose)")
    print(f"[merge] {unmatched_master} master perplexity rows had no CUDA match")
    print(f"[merge] {len(unmatched_cuda)} experiment-id CUDA rows unused:")
    for r in unmatched_cuda:
        print(f"           {r.get('config_name')}")
    print(f"[merge] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
