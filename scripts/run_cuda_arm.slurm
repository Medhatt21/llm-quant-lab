#!/usr/bin/env bash
#SBATCH --job-name=cuda-arm
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a10g:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --output=reports/cuda_arm/slurm/%x_%A_%a.out
#SBATCH --error=reports/cuda_arm/slurm/%x_%A_%a.out
# =============================================================================
# Slurm array job: run the LLM-Quant-Lab CUDA arm on the A10G `gpu` partition.
# No docker, no sudo.
#
# Each array task processes a CHUNK of the manifest (round-robin by line), so a
# whole manifest can be covered with a SMALL array. This matters here because
# the `gpu-long-iamer-001` QOS caps total submitted jobs at 10 -- a 1-task-per-
# config array of dozens of configs is rejected. With e.g. --array=1-8 you get
# 8 parallel nodes, each chewing through its slice sequentially.
#
# Usage (from the repo root):
#   # ungated quantized set, 8 nodes in parallel:
#   sbatch --array=1-8 scripts/run_cuda_arm.slurm
#
#   # a different manifest (e.g. gated models; needs HF_TOKEN exported):
#   MANIFEST=experiments/manifests/feasible_gated_a10g.txt \
#     sbatch --array=1-4 scripts/run_cuda_arm.slurm
#
#   # a single explicit config (no array):
#   sbatch scripts/run_cuda_arm.slurm experiments/configs/gptq_opt125m.yml
#
# Results land in reports/cuda_arm/ (per-config rows in reports/cuda_arm/rows/).
# Rebuild the master CSV afterwards with scripts/collect_cuda_results.sh.
# =============================================================================
set -uo pipefail   # NOTE: no `-e`; we want one failing config to not abort the chunk.

# Resolve repo root from this script's location (Slurm copies the submit dir).
REPO_ROOT="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO_ROOT"
mkdir -p reports/cuda_arm/slurm

MANIFEST="${MANIFEST:-experiments/manifests/feasible_ungated_a10g.txt}"

echo "[slurm] node=$(hostname) job=${SLURM_JOB_ID:-?} task=${SLURM_ARRAY_TASK_ID:-none}/${SLURM_ARRAY_TASK_COUNT:-1} manifest=$MANIFEST"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

run_one() {
    local cfg="$1"
    if [[ -z "$cfg" || ! -f "$cfg" ]]; then
        echo "[slurm] SKIP missing config: '${cfg:-<empty>}'" >&2
        return 0
    fi
    echo "[slurm] === running $cfg ==="
    # run_cuda_arm.sh sources .cuda-arm.env (venv + PYTHONPATH + LD_LIBRARY_PATH
    # + HF_HOME). The allocated GPU is always visible as index 0 in the job.
    if bash scripts/run_cuda_arm.sh "$cfg" 0; then
        echo "[slurm] OK  $cfg"
    else
        echo "[slurm] FAIL $cfg (rc=$?) -- continuing" >&2
    fi
}

# Mode 1: explicit config argument.
if [[ $# -ge 1 ]]; then
    run_one "$1"
    exit 0
fi

# Mode 2: chunked array. Process every manifest line assigned to this task by
# stride = number of array tasks (round-robin balances big models across tasks).
NTASKS="${SLURM_ARRAY_TASK_COUNT:-1}"
IDX="${SLURM_ARRAY_TASK_ID:-1}"
lineno=0
while IFS= read -r cfg; do
    [[ -z "$cfg" ]] && continue
    lineno=$((lineno + 1))
    if (( (lineno - 1) % NTASKS == (IDX - 1) )); then
        run_one "$cfg"
    fi
done < "$MANIFEST"

echo "[slurm] task ${IDX}/${NTASKS} finished its chunk."
