#!/usr/bin/env bash
# Run n=3 multi-seed trials of an LLMC config and aggregate mean ± sigma.
#
# Each trial runs the same YAML with a different `base.seed` to surface the
# variance contribution from calibration sample selection. Output is appended
# to reports/trial_repeats/<config_name>_trials.csv with columns:
#
#   trial,seed,wikitext2_ppl,llmc_duration_s,host_gpu,timestamp
#
# Usage:
#   scripts/run_trial_repeats.sh experiments/configs/gptq_opt125m.yml [seeds...]
#
# Defaults to seeds 42 43 44 (n=3). Pass any number of trailing integers to
# override.
set -euo pipefail

CONFIG_REL="${1:?usage: run_trial_repeats.sh <config-rel-path> [seeds...]}"
shift || true
SEEDS=("${@:-42 43 44}")

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$(basename "$CONFIG_REL" .yml)"
OUT_DIR="$REPO_ROOT/reports/trial_repeats"
OUT_CSV="$OUT_DIR/${NAME}_trials.csv"
mkdir -p "$OUT_DIR"

if [[ ! -f "$OUT_CSV" ]]; then
    echo "trial,seed,wikitext2_ppl,llmc_duration_s,host_gpu,timestamp" > "$OUT_CSV"
fi

# We sync /data → /home/ubuntu/apps before each trial so the running dev
# container (which mounts /home/ubuntu/apps) sees the latest config.
sync_into_container() {
    rsync -a "$REPO_ROOT/scripts/" /home/ubuntu/apps/llm-quant-lab/scripts/
    rsync -a "$REPO_ROOT/experiments/configs/" /home/ubuntu/apps/llm-quant-lab/experiments/configs/
}

GPU_ID="${HIP_VISIBLE_DEVICES:-3}"
HF_TOKEN_VAL="$(grep -m1 ^HF_TOKEN= "$REPO_ROOT/.env" | cut -d= -f2- || true)"
WANDB_API_KEY_VAL="$(grep -m1 ^WANDB_API_KEY= "$REPO_ROOT/.env" | cut -d= -f2- || true)"
WANDB_PROJECT_VAL="$(grep -m1 ^WANDB_PROJECT= "$REPO_ROOT/.env" | cut -d= -f2- || true)"
WANDB_ENTITY_VAL="$(grep -m1 ^WANDB_ENTITY= "$REPO_ROOT/.env" | cut -d= -f2- || true)"

run_one_trial() {
    local trial="$1" seed="$2"
    local seeded_cfg="experiments/configs/${NAME}__seed${seed}.yml"
    # Template a per-seed config in /data so we can preserve provenance.
    sed -E "s/^(\s*seed:\s*&seed\s*)[0-9]+/\1${seed}/; s/^(\s*seed:\s*)[0-9]+\$/\1${seed}/" \
        "$REPO_ROOT/$CONFIG_REL" > "$REPO_ROOT/$seeded_cfg"
    sync_into_container
    local ts
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    echo "[trial $trial seed=$seed] launching on GPU $GPU_ID ..."
    local log
    log="$OUT_DIR/${NAME}__seed${seed}.log"
    # Run via the wandb wrapper so each trial is a tagged W&B run filterable
    # by tag 'iiswc-2026-tools-track'. The wrapper itself shells out to
    # torchrun + llmc.
    docker exec \
        -e HIP_VISIBLE_DEVICES="$GPU_ID" \
        -e HF_TOKEN="$HF_TOKEN_VAL" \
        -e WANDB_API_KEY="$WANDB_API_KEY_VAL" \
        -e WANDB_PROJECT="$WANDB_PROJECT_VAL" \
        -e WANDB_ENTITY="$WANDB_ENTITY_VAL" \
        -e WANDB_SILENT=true \
        llm-quant-devvvvv \
        python /workspace/scripts/wandb_run_llmc.py \
            --config "/workspace/$seeded_cfg" \
            --gpu "$GPU_ID" \
            --extra-tag "trial_repeats_n3" \
            --extra-tag "headline" \
        > "$log" 2>&1
    local ppl dur
    ppl="$(grep -oE 'EVAL: ppl on wikitext2 is [0-9.]+' "$log" | tail -1 | awk '{print $NF}')"
    dur="$(grep -oE 'llmc_duration_time: [0-9.]+' "$log" | tail -1 | awk '{print $2}')"
    echo "  -> ppl=${ppl:-NA}  duration=${dur:-NA}s"
    printf '%d,%d,%s,%s,%s,%s\n' "$trial" "$seed" "${ppl:-NA}" "${dur:-NA}" "MI300X#${GPU_ID}" "$ts" >> "$OUT_CSV"
}

i=1
for s in "${SEEDS[@]}"; do
    run_one_trial "$i" "$s"
    i=$((i+1))
done

echo
echo "=== Trial summary for $NAME (CSV: $OUT_CSV) ==="
python3 - <<PY
import csv
import math
from pathlib import Path

rows = list(csv.DictReader(Path("$OUT_CSV").open()))
ppls = []
for r in rows:
    if r["trial"] and r["wikitext2_ppl"] not in {"NA", ""}:
        try:
            ppls.append(float(r["wikitext2_ppl"]))
        except ValueError:
            pass
n = len(ppls)
if n == 0:
    print("  (no valid trials parsed)")
else:
    mean = sum(ppls)/n
    var = sum((p-mean)**2 for p in ppls)/(n-1) if n > 1 else 0.0
    sigma = math.sqrt(var)
    print(f"  n={n}  ppl mean={mean:.3f}  sigma={sigma:.3f}  cv={sigma/mean*100 if mean else 0:.2f}%")
    print(f"  trials: {ppls}")
PY
