"""Summarise all W&B runs tagged `iiswc-2026-tools-track`.

Used as a sanity check before submission: produces a CSV listing every
filterable run, its key summary metrics, and the wall-clock when it ran.

Usage (inside the dev container):

    python scripts/wandb_summarize_iiswc.py \\
        --tag iiswc-2026-tools-track \\
        --out reports/wandb_iiswc_summary.csv

If --out is given the rows are written to CSV; otherwise a short summary is
printed to stdout.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

try:
    import wandb
except ImportError:
    print("wandb not installed", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="iiswc-2026-tools-track")
    ap.add_argument("--project", default=os.environ.get("WANDB_PROJECT", "llm-quant-lab"))
    ap.add_argument("--entity", default=os.environ.get("WANDB_ENTITY"))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    api = wandb.Api()
    path = f"{args.entity}/{args.project}" if args.entity else args.project
    runs = list(api.runs(path, filters={"tags": {"$in": [args.tag]}}, per_page=200))

    if not runs:
        print(f"[wandb-summary] no runs tagged '{args.tag}' in {path}")
        return 0

    rows: list[dict[str, str]] = []
    for r in runs:
        cfg = r.config or {}
        summ = r.summary or {}
        rows.append(
            {
                "id": r.id,
                "name": r.name,
                "state": r.state,
                "group": r.group or "",
                "tags": "|".join(r.tags or []),
                "method": str(cfg.get("method", "")),
                "model": str(cfg.get("model", "")),
                "bit": str(cfg.get("bit_width", "")),
                "seed": str(cfg.get("seed", "")),
                "gpu_id": str(cfg.get("gpu_id", "")),
                "hardware": str(cfg.get("hardware", "")),
                "wikitext2_ppl": str(summ.get("wikitext2_ppl", "")),
                "llmc_duration_s": str(summ.get("llmc_duration_s", "")),
                "created_at": str(getattr(r, "created_at", "")),
                "url": r.url,
            }
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"[wandb-summary] wrote {len(rows)} runs to {args.out}")
    else:
        print(f"[wandb-summary] {len(rows)} runs tagged '{args.tag}' in {path}")
        groups: dict[str, int] = {}
        for r in rows:
            g = r["group"] or "(no group)"
            groups[g] = groups.get(g, 0) + 1
        for g, n in sorted(groups.items()):
            print(f"  {g}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
