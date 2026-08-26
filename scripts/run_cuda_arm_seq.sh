#!/usr/bin/env bash
# Sequentially run a manifest of LLMC configs through the CUDA arm on the local
# A10G (login-node, no Slurm), skipping any config that already has a result
# row. Each successful run is appended to reports/cuda_arm/cuda_results.csv and
# logged to W&B under the nvidia-reproduction tag by run_cuda_arm.sh.
#
# Usage:
#   bash scripts/run_cuda_arm_seq.sh [manifest] [gpu-id]
#
# Default manifest: experiments/manifests/missing_feasible_a10g.txt
set -uo pipefail   # no -e: one failing config must not abort the batch.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MANIFEST="${1:-experiments/manifests/missing_feasible_a10g.txt}"
GPU_ID="${2:-0}"
ROWS_DIR="reports/cuda_arm/rows"
PROGRESS="reports/cuda_arm/seq_progress.log"
mkdir -p "$ROWS_DIR"

log() { echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$PROGRESS"; }

if [[ ! -f "$MANIFEST" ]]; then
    log "ERROR: manifest not found: $MANIFEST"; exit 2
fi

total=$(grep -cve '^[[:space:]]*$' "$MANIFEST")
log "=== batch start: $total configs from $MANIFEST (gpu=$GPU_ID) ==="

i=0
while IFS= read -r cfg; do
    [[ -z "$cfg" ]] && continue
    i=$((i + 1))
    name="$(basename "$cfg" .yml)"
    if [[ -f "$ROWS_DIR/${name}.csv" ]]; then
        log "($i/$total) SKIP $name (already has a result row)"
        continue
    fi
    if [[ ! -f "$cfg" ]]; then
        log "($i/$total) SKIP $name (config file missing)"
        continue
    fi
    log "($i/$total) RUN  $name"
    start=$(date +%s)
    if bash scripts/run_cuda_arm.sh "$cfg" "$GPU_ID" >>"$PROGRESS" 2>&1; then
        dur=$(( $(date +%s) - start ))
        ppl="$(awk -F, 'END{print $5}' "$ROWS_DIR/${name}.csv" 2>/dev/null)"
        log "($i/$total) OK   $name ppl=${ppl:-?} (${dur}s)"
    else
        dur=$(( $(date +%s) - start ))
        log "($i/$total) FAIL $name (${dur}s) -- continuing"
    fi
done < "$MANIFEST"

log "=== batch done ==="
