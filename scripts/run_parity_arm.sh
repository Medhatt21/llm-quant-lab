#!/usr/bin/env bash
# Controlled cross-hardware parity arm (IISWC #414 rebuttal).
#
# Runs the parity subset (experiments/manifests/parity_subset.txt) at n=3 seeds
# on ONE platform under the pinned torch 2.9.1 stack, writing per-seed rows via
# scripts/run_cuda_arm.sh. Intended to be run once on the NVIDIA A10G host
# (after re-provisioning the venv at torch 2.9.1) and once on a networked AMD
# node, so scripts/merge_paired_results.py can produce a stack_matched=True
# paired table.
#
# NVIDIA host (re-pin torch to match the AMD 2.9.1 release, then run):
#   TORCH_PIN=2.9.1 TORCH_CUDA_TAG=cu128 bash scripts/setup_cuda_arm_venv.sh
#   source .cuda-arm.env
#   bash scripts/run_parity_arm.sh 0
#
# The AMD arm is produced by scripts/run_trial_repeats.sh inside the ROCm dev
# container (already torch 2.9.1+rocm7.2.0); this wrapper is the NVIDIA-side
# equivalent so both arms share the seed-templating and CSV schema.
set -euo pipefail

GPU_ID="${1:-0}"
SEEDS=(${PARITY_SEEDS:-42 43 44})
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/experiments/manifests/parity_subset.txt"

# Verify the pinned stack before spending GPU hours; a mismatched torch build
# is exactly the confound this arm exists to remove.
EXPECT_TORCH="${EXPECT_TORCH:-2.9.1}"
ACT_TORCH="$(python -c 'import torch;print(torch.__version__)' 2>/dev/null || echo none)"
if [[ "$ACT_TORCH" != ${EXPECT_TORCH}* ]]; then
    echo "[parity] REFUSING TO RUN: torch is '$ACT_TORCH', expected '${EXPECT_TORCH}*'." >&2
    echo "         Re-provision: TORCH_PIN=${EXPECT_TORCH} TORCH_CUDA_TAG=cu128 bash scripts/setup_cuda_arm_venv.sh" >&2
    exit 2
fi
echo "[parity] torch=$ACT_TORCH gpu=$GPU_ID seeds=${SEEDS[*]}"

grep -vE '^\s*#|^\s*$' "$MANIFEST" | awk '{print $1}' | while read -r cfg; do
    name="$(basename "$cfg" .yml)"
    for s in "${SEEDS[@]}"; do
        seeded="experiments/configs/${name}__seed${s}.yml"
        # Template the seed (handles both `seed: &seed N` and `seed: N`).
        sed -E "s/^(\s*seed:\s*&seed\s*)[0-9]+/\1${s}/; s/^(\s*seed:\s*)[0-9]+\$/\1${s}/" \
            "$REPO_ROOT/$cfg" > "$REPO_ROOT/$seeded"
        echo "[parity] === $seeded on GPU $GPU_ID ==="
        bash "$REPO_ROOT/scripts/run_cuda_arm.sh" "$seeded" "$GPU_ID"
    done
done

echo "[parity] done. Merge with:"
echo "    python scripts/merge_paired_results.py --master reproduction_results.csv \\"
echo "        --cuda reports/cuda_arm/cuda_results.csv --out reproduction_results_paired.csv \\"
echo "        --amd-torch ${EXPECT_TORCH}+rocm7.2.0"
