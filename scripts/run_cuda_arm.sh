#!/usr/bin/env bash
# Run an LLMC config on a CUDA host and append a row to the paired-results CSV.
#
# This script is the NVIDIA arm of the paired-hardware reproduction described
# in REPRODUCIBILITY.md. The output CSV column schema is identical to the
# ROCm-side AMD column so the two can be merged without transformation.
#
# No docker, no sudo required. On a fresh NVIDIA host:
#
#   1. bash scripts/setup_cuda_arm_venv.sh   # provisions .venv-cuda-arm/
#   2. bash scripts/run_cuda_arm.sh <config-yml> [<gpu-id>]
#
# The runner auto-sources .cuda-arm.env (created by step 1) which activates
# the venv and sets PYTHONPATH=vendors/lightcompress so 'torchrun -m llmc'
# finds the vendored LightCompress.
#
# Output:
#   reports/cuda_arm/<config-name>.json      raw run metadata + ppl
#   reports/cuda_arm/cuda_results.csv        appended one row per invocation
#
# Example:
#   bash scripts/run_cuda_arm.sh experiments/configs/gptq_opt125m.yml 0
set -euo pipefail

CONFIG_REL="${1:?usage: run_cuda_arm.sh <config-rel-path> [gpu-id]}"
GPU_ID="${2:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Auto-source the venv created by scripts/setup_cuda_arm_venv.sh, if present.
# This is the no-docker, no-sudo path: the env file activates the project's
# Python venv and points PYTHONPATH at vendors/lightcompress.
if [[ -f "$REPO_ROOT/.cuda-arm.env" ]]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.cuda-arm.env"
fi

# Pull W&B credentials and an HF token (for gated models) out of .env without
# sourcing the whole file (which would clobber CUDA_VISIBLE_DEVICES etc.).
if [[ -f "$REPO_ROOT/.env" ]]; then
    while IFS='=' read -r _k _v; do
        case "$_k" in
            WANDB_API_KEY|WANDB_PROJECT|WANDB_ENTITY|HF_TOKEN)
                [[ -n "${!_k:-}" ]] || export "$_k=$_v" ;;
        esac
    done < <(grep -E '^(WANDB_API_KEY|WANDB_PROJECT|WANDB_ENTITY|HF_TOKEN)=' "$REPO_ROOT/.env")
fi

NAME="$(basename "$CONFIG_REL" .yml)"
OUT_DIR="$REPO_ROOT/reports/cuda_arm"
LOG="$OUT_DIR/${NAME}_$(date -u +%Y%m%dT%H%M%SZ).log"
JSON="$OUT_DIR/${NAME}.json"
CSV="$OUT_DIR/cuda_results.csv"
mkdir -p "$OUT_DIR"

# Ensure we have python + torch (which provides torch.distributed.run, the
# relocatable equivalent of the `torchrun` console script). We invoke it as a
# module so a moved venv with stale console-script shebangs still works.
if ! command -v python >/dev/null 2>&1 || ! python -c 'import torch' >/dev/null 2>&1; then
    echo "ERROR: python with torch not found on PATH." >&2
    echo "       Run 'bash scripts/setup_cuda_arm_venv.sh' first" >&2
    echo "       (no docker / no sudo required)." >&2
    exit 2
fi

if [[ ! -f "$CSV" ]]; then
    echo "config_name,model,method,bit_width,wikitext2_ppl,llmc_duration_s,gpu_name,vllm_version,torch_version,timestamp,config_sha256" > "$CSV"
fi

# Capture the CUDA-side environment so the merged CSV is self-describing.
GPU_NAME="$(nvidia-smi --id="$GPU_ID" --query-gpu=name --format=csv,noheader 2>/dev/null || echo unknown)"
TORCH_VERSION="$(python -c 'import torch; print(torch.__version__)' 2>/dev/null || echo unknown)"
VLLM_VERSION="$(python -c 'import vllm; print(vllm.__version__)' 2>/dev/null || echo unknown)"
CFG_SHA="$(sha256sum "$REPO_ROOT/$CONFIG_REL" | awk '{print $1}')"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# Pull model + method + bit-width out of the YAML for the CSV row.
# Note: FP16 baseline configs have no `method:`/`bit:` fields, and grep returns
# nonzero on no-match; with `set -euo pipefail` that would abort the script, so
# tolerate missing optional fields with `|| true` and sensible defaults.
MODEL="$(grep -E '^[[:space:]]*path:' "$REPO_ROOT/$CONFIG_REL" | head -1 | awk '{print $2}' || true)"
METHOD="$(grep -E '^[[:space:]]*method:' "$REPO_ROOT/$CONFIG_REL" | head -1 | awk '{print $2}' | tr 'A-Z' 'a-z' || true)"
METHOD="${METHOD:-fp16}"
BIT="$(grep -E '^[[:space:]]*bit:' "$REPO_ROOT/$CONFIG_REL" | head -1 | awk '{print $2}' || true)"
BIT="${BIT:-16}"

echo "[cuda-arm] config=$CONFIG_REL model=$MODEL method=$METHOD bit=$BIT gpu=$GPU_ID"

# Run LLMC. We use torchrun on a single GPU with a unique master port so
# multiple invocations on the same host don't collide.
CUDA_VISIBLE_DEVICES="$GPU_ID" \
    python -m torch.distributed.run --nproc_per_node=1 --nnodes=1 --master_port=$((29500 + RANDOM % 500)) \
    -m llmc \
    --config "$REPO_ROOT/$CONFIG_REL" \
    --task_id 0 \
    > "$LOG" 2>&1

PPL="$(grep -oE 'EVAL: ppl on wikitext2 is [0-9.]+' "$LOG" | tail -1 | awk '{print $NF}')"
DUR="$(grep -oE 'llmc_duration_time: [0-9.]+' "$LOG" | tail -1 | awk '{print $2}')"

if [[ -z "${PPL:-}" ]]; then
    echo "[cuda-arm] ERROR: no perplexity emitted; see $LOG" >&2
    exit 1
fi

cat > "$JSON" <<JSON
{
  "config": "$CONFIG_REL",
  "config_sha256": "$CFG_SHA",
  "model": "$MODEL",
  "method": "$METHOD",
  "bit_width": $BIT,
  "wikitext2_ppl": $PPL,
  "llmc_duration_s": $DUR,
  "gpu": "$GPU_NAME",
  "torch_version": "$TORCH_VERSION",
  "vllm_version": "$VLLM_VERSION",
  "timestamp_utc": "$TS"
}
JSON

ROW="$(printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' \
    "$NAME" "$MODEL" "$METHOD" "$BIT" "$PPL" "$DUR" \
    "$GPU_NAME" "$VLLM_VERSION" "$TORCH_VERSION" "$TS" "$CFG_SHA")"

# Per-config row file: race-free under parallel Slurm arrays (each task writes
# its own file). scripts/collect_cuda_results.sh rebuilds the master CSV from
# these. We also append to the shared CSV for the convenience of single runs.
mkdir -p "$OUT_DIR/rows"
printf '%s\n' "$ROW" > "$OUT_DIR/rows/${NAME}.csv"
printf '%s\n' "$ROW" >> "$CSV"

echo "[cuda-arm] done: ppl=$PPL  dur=${DUR}s  -> $JSON"
echo "[cuda-arm] wrote row -> $OUT_DIR/rows/${NAME}.csv (and appended to $CSV)"

# Log this run to W&B under the nvidia-reproduction tag (non-fatal on failure).
if [[ -n "${WANDB_API_KEY:-}" ]]; then
    WANDB_SILENT="${WANDB_SILENT:-true}" \
        python "$REPO_ROOT/scripts/wandb_log_cuda_arm.py" "$JSON" \
        || echo "[cuda-arm] WARN: W&B logging failed (non-fatal)" >&2
fi
