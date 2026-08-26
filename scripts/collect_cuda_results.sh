#!/usr/bin/env bash
# Rebuild reports/cuda_arm/cuda_results.csv from the per-config row files in
# reports/cuda_arm/rows/. This is the race-free source of truth after a
# parallel Slurm array run (scripts/run_cuda_arm.slurm), since each array task
# writes its own rows/<config>.csv file.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ROWS_DIR="reports/cuda_arm/rows"
CSV="reports/cuda_arm/cuda_results.csv"
HEADER="config_name,model,method,bit_width,wikitext2_ppl,llmc_duration_s,gpu_name,vllm_version,torch_version,timestamp,config_sha256"

if [[ ! -d "$ROWS_DIR" ]] || ! ls "$ROWS_DIR"/*.csv >/dev/null 2>&1; then
    echo "[collect] no row files in $ROWS_DIR; nothing to do." >&2
    exit 0
fi

{
    echo "$HEADER"
    cat "$ROWS_DIR"/*.csv
} > "$CSV"

echo "[collect] wrote $(( $(wc -l < "$CSV") - 1 )) rows -> $CSV"
