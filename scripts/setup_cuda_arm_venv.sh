#!/usr/bin/env bash
# Provision a Python virtualenv for the NVIDIA paired-hardware arm WITHOUT
# docker and WITHOUT sudo. Uses `uv` (single user-level binary; installed to
# ~/.local/bin if missing).
#
# What this provides:
#   - .venv-cuda-arm/  : Python virtualenv with pinned dependencies
#   - .cuda-arm.env    : `source` this before running scripts/run_cuda_arm.sh
#
# What it intentionally OMITS:
#   - vllm: not needed for LLMC fake-quant runs. The CUDA arm produces the
#     same kind of accuracy numbers the AMD column reports (perplexity), and
#     LLMC fake-quant runs through plain transformers+accelerate.
#   - sglang, deepspeed, fast_hadamard_transform, qtorch: optional LLMC
#     extras that emit warnings but don't block GPTQ/AWQ/RTN/SmoothQuant.
#
# Prereqs on the NVIDIA host:
#   - Python 3.10–3.12 on PATH (uv can install one if your system Python
#     is too old; see UV_PYTHON below)
#   - CUDA toolkit visible to torch (typically CUDA 12.x driver; no compile
#     needed because torch ships prebuilt wheels)
#   - ~10 GB free in the install location (torch + transformers caches)
#
# Usage:
#   bash scripts/setup_cuda_arm_venv.sh
#   source .cuda-arm.env
#   bash scripts/run_cuda_arm.sh experiments/configs/gptq_opt125m.yml 0
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv-cuda-arm}"
ENV_FILE="$REPO_ROOT/.cuda-arm.env"

# CUDA build of torch. Common choices:
#   cu121 (CUDA 12.1)  — broadest compatibility
#   cu124 (CUDA 12.4)  — recent
#   cu118 (CUDA 11.8)  — older clusters
# Override with TORCH_CUDA_TAG=cuXXX before invoking this script.
TORCH_CUDA_TAG="${TORCH_CUDA_TAG:-cu124}"

# Pinned versions — keep close to the AMD-side stack so paired numbers are
# minimally confounded by software-version drift. transformers 5.1.0 matches
# the ROCm side; torch is the latest cu* build that vendors LLMC's Triton
# kernels work with.
# transformers 5.1.0 refuses to torch.load() .bin checkpoints unless torch>=2.6
# (security restriction), and many HF models still ship .bin. torch 2.6.0+cu124
# is the combo validated on the `nvidia` branch.
TORCH_PIN="${TORCH_PIN:-2.6.0}"
# torchvision release that pairs with torch 2.6.0 (see pytorch.org compat table).
TORCHVISION_PIN="${TORCHVISION_PIN:-0.21.0}"
TRANSFORMERS_PIN="${TRANSFORMERS_PIN:-5.1.0}"

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        echo "[setup] uv already on PATH: $(uv --version)"
        return
    fi
    if [[ -x "$HOME/.local/bin/uv" ]]; then
        export PATH="$HOME/.local/bin:$PATH"
        echo "[setup] uv found at \$HOME/.local/bin (added to PATH)"
        return
    fi
    echo "[setup] installing uv to ~/.local/bin (no sudo) ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "[setup] ERROR: uv install did not put binary on PATH." >&2
        echo "        Add '$HOME/.local/bin' to your PATH and re-run." >&2
        exit 1
    fi
    echo "[setup] uv installed: $(uv --version)"
}

create_venv() {
    if [[ -d "$VENV_DIR" ]]; then
        echo "[setup] reusing existing venv: $VENV_DIR"
        return
    fi
    echo "[setup] creating venv at $VENV_DIR ..."
    uv venv --python ">=3.10,<3.13" "$VENV_DIR"
}

install_deps() {
    echo "[setup] installing pinned dependencies ..."
    # uv pip will activate the venv implicitly via --python
    local python_bin="$VENV_DIR/bin/python"

    # torch (CUDA build). The PyTorch CUDA wheels live on a dedicated index;
    # uv handles --index-url cleanly.
    # torchvision must match the torch version; LLMC's eval package imports it
    # unconditionally (llmc/eval/eval_acc.py: `from torchvision import transforms`).
    uv pip install --python "$python_bin" \
        --index-url "https://download.pytorch.org/whl/${TORCH_CUDA_TAG}" \
        --extra-index-url https://pypi.org/simple \
        --index-strategy unsafe-best-match \
        "torch==${TORCH_PIN}+${TORCH_CUDA_TAG}" \
        "torchvision==${TORCHVISION_PIN}+${TORCH_CUDA_TAG}" \
        "nvidia-cusparselt-cu12"

    # Everything else from PyPI.
    uv pip install --python "$python_bin" \
        "transformers==${TRANSFORMERS_PIN}" \
        "accelerate>=0.30" \
        "datasets>=2.16" \
        "tokenizers>=0.20" \
        "sentencepiece>=0.2" \
        "safetensors>=0.4" \
        "pillow>=10" \
        "einops>=0.7" \
        "pyyaml>=6" \
        "numpy>=1.26,<2.3" \
        "pandas>=2.0" \
        "loguru>=0.7" \
        "easydict>=1.13" \
        "scipy>=1.11" \
        "human-eval" \
        "lm-eval[api]>=0.4.0"
}

write_env_file() {
    cat > "$ENV_FILE" <<'EOF'
# Source this file before running scripts/run_cuda_arm.sh.
# Relocatable: derives the repo root from this file's own location, so the
# repo can be moved or used by another user without editing absolute paths.
_CUDA_ARM_REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export PATH="${_CUDA_ARM_REPO}/.venv-cuda-arm/bin:${PATH}"
export PYTHONPATH="${_CUDA_ARM_REPO}/vendors/lightcompress:${_CUDA_ARM_REPO}:${PYTHONPATH:-}"
# torch>=2.6 cu124 wheels need the bundled NVIDIA libs (esp. libcusparseLt) on
# the loader path. Add every nvidia/*/lib dir shipped inside the venv.
_NV_LIBS="$(echo "${_CUDA_ARM_REPO}"/.venv-cuda-arm/lib/python*/site-packages/nvidia/*/lib 2>/dev/null | tr ' ' ':')"
if [ -n "${_NV_LIBS}" ] && [ "${_NV_LIBS}" != "*" ]; then
    export LD_LIBRARY_PATH="${_NV_LIBS}:${LD_LIBRARY_PATH:-}"
fi
# HF model/dataset cache. Default to a sibling dir of the repo so it lands on
# the same (roomy) filesystem as the checkout instead of a quota-limited $HOME.
# Override by exporting HF_HOME before sourcing this file.
: ${HF_HOME:="$(dirname "${_CUDA_ARM_REPO}")/hf-cache"}
export HF_HOME
unset _CUDA_ARM_REPO _NV_LIBS
EOF
    echo "[setup] wrote $ENV_FILE"
}

smoke_test() {
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    echo "[setup] smoke-checking imports ..."
    "$VENV_DIR/bin/python" - <<'PY'
import sys
print(f"  python  {sys.version.split()[0]}")
import torch
print(f"  torch   {torch.__version__}  cuda_available={torch.cuda.is_available()} devices={torch.cuda.device_count()}")
import transformers
print(f"  transformers {transformers.__version__}")
# llmc lives in vendors/lightcompress on PYTHONPATH; just probe the package
# can be imported without GPU activity.
import importlib
spec = importlib.util.find_spec("llmc")
print(f"  llmc importable: {spec is not None}")
PY
}

main() {
    ensure_uv
    create_venv
    install_deps
    write_env_file
    smoke_test
    cat <<EOF

[setup] Done. Next steps on this host:

    source .cuda-arm.env
    bash scripts/run_cuda_arm.sh experiments/configs/gptq_opt125m.yml 0

The first run will download OPT-125M (~250 MB) into \$HF_HOME and
produce a row in reports/cuda_arm/cuda_results.csv.

To merge that row into the master reproduction CSV:

    python scripts/merge_paired_results.py \\
        --master reproduction_results.csv \\
        --cuda  reports/cuda_arm/cuda_results.csv \\
        --out   reproduction_results_paired.csv

EOF
}

main "$@"
