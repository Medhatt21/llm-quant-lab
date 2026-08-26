#!/usr/bin/env bash
# Reproduce the headline numbers from the IISWC 2026 Tools-track submission.
#
# What this does, in order:
#   1.  Verify that the pinned Docker image is present (or pull it).
#   2.  Re-fit the per-method power law from reproduction_results.csv with
#       1,000-sample bootstrap CIs (writes reports/powerlaw/).
#   3.  Auto-generate any missing experiment YAML configs from the CSV
#       (writes experiments/configs/).
#   4.  (Optional) Run the four headline LLMC experiments end-to-end on
#       MI300X if --run-gpu is passed and a ROCm device is visible.
#   5.  Print a short summary of what was produced.
#
# Usage:
#   bash scripts/reproduce_iiswc.sh                # analysis-only (no GPU)
#   bash scripts/reproduce_iiswc.sh --run-gpu      # also run 4 GPU configs
#
# Exit codes:
#   0 — success
#   1 — Docker missing or image pull failed
#   2 — pinned image found but cannot run python on host
#   3 — GPU run requested but no ROCm device visible
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Pinned image digest — keep in sync with REPRODUCIBILITY.md.
PINNED_IMAGE="rocm/pytorch@sha256:3e917342db23b080cc7aa274321b4a7f33eb321e71b9607d69c0cb4deaaa8820"
PINNED_TAG="rocm/pytorch:rocm7.1_ubuntu24.04_py3.12_pytorch_release_2.8.0"

# Headline experiments — small enough to run in <5 min each on MI300X.
HEADLINE_CONFIGS=(
    "experiments/configs/gptq_opt125m.yml"
    "experiments/configs/rtn_opt125m.yml"
    # add more as the corpus stabilizes
)

run_in_pinned() {
    docker run --rm \
        -v "$REPO_ROOT:/workspace" \
        --workdir /workspace \
        --user "$(id -u):$(id -g)" \
        "$PINNED_TAG" \
        "$@"
}

run_on_gpu() {
    docker run --rm \
        --device=/dev/kfd --device=/dev/dri \
        --group-add video --group-add render \
        --ipc=host --shm-size=16g \
        --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
        -v "$REPO_ROOT:/workspace" \
        --workdir /workspace/vendors/lightcompress \
        "$PINNED_TAG" \
        "$@"
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "ERROR: docker is not available on PATH." >&2
        exit 1
    fi
    if ! docker image inspect "$PINNED_TAG" >/dev/null 2>&1; then
        echo "Pulling pinned image $PINNED_IMAGE ..."
        docker pull "$PINNED_IMAGE" || { echo "ERROR: pull failed." >&2; exit 1; }
    fi
}

step_powerlaw_refit() {
    echo "[1/3] Re-fitting per-method power law with bootstrap CIs ..."
    run_in_pinned python /workspace/scripts/powerlaw_refit.py
}

step_generate_configs() {
    echo "[2/3] Auto-generating experiment configs from CSV ..."
    run_in_pinned python /workspace/scripts/generate_configs.py
}

step_run_headline() {
    echo "[3/3] Running headline experiments on the visible ROCm device ..."
    if ! command -v rocm-smi >/dev/null 2>&1; then
        echo "ERROR: rocm-smi not found; refusing to run GPU step." >&2
        exit 3
    fi
    for cfg in "${HEADLINE_CONFIGS[@]}"; do
        if [[ ! -f "$REPO_ROOT/$cfg" ]]; then
            echo "  skip (missing): $cfg"
            continue
        fi
        echo "  --> $cfg"
        run_on_gpu python -m llmc --config "/workspace/$cfg" --task_id 0
    done
}

main() {
    local run_gpu=0
    for arg in "$@"; do
        case "$arg" in
            --run-gpu) run_gpu=1 ;;
            -h|--help)
                sed -n '1,30p' "$0"; exit 0 ;;
            *) echo "Unknown arg: $arg" >&2; exit 1 ;;
        esac
    done

    require_docker
    step_powerlaw_refit
    step_generate_configs
    if [[ "$run_gpu" -eq 1 ]]; then
        step_run_headline
    else
        echo "[3/3] GPU step skipped (pass --run-gpu to enable)."
    fi

    echo
    echo "=== reproduce_iiswc.sh complete ==="
    echo "Outputs:"
    echo "  reports/powerlaw/per_method_fit.csv"
    echo "  reports/powerlaw/per_method_fit.tex"
    echo "  reports/powerlaw/per_method_curves.pdf"
    echo "  experiments/configs/<exp_id>_<method>_w<bit>.yml"
    if [[ "$run_gpu" -eq 1 ]]; then
        echo "  vendors/lightcompress/save_path/* (per headline config)"
    fi
}

main "$@"
