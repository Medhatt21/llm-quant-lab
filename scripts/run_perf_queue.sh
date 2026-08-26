#!/usr/bin/env bash
# Serving-performance grid on modern models (IISWC #414), GPU 7.
# Waits until GPU 7 VRAM is free (accuracy jobs done) before each run, so it can
# be launched behind the accuracy queue on the same GPU.
#
# Usage: scripts/run_perf_queue.sh
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU=7

# Gate on the accuracy queue finishing first, to avoid racing for GPU 7 between
# its sequential jobs. Skip the gate by setting SKIP_ACC_GATE=1.
ACC_OUT="$REPO_ROOT/reports/modern_accuracy/queue.out"
if [[ "${SKIP_ACC_GATE:-0}" != "1" ]]; then
    echo "[perfq] waiting for accuracy queue to finish ..."
    while ! grep -q "all done ->" "$ACC_OUT" 2>/dev/null; do sleep 60; done
    echo "[perfq] accuracy queue done; starting perf grid."
fi

# (model, format) pairs. BF16 is certain; FP8 is best-effort (on-the-fly vLLM).
PAIRS=(
  "qwen/Qwen3-30B-A3B|bf16"
  "Qwen/Qwen3-32B|bf16"
  "google/gemma-3-27b-it|bf16"
  "qwen/Qwen3-30B-A3B|fp8"
  "Qwen/Qwen3-32B|fp8"
  "google/gemma-3-27b-it|fp8"
  "RedHatAI/Llama-4-Scout-17B-16E-Instruct-FP8-dynamic|fp8"
)

wait_free() {
    while true; do
        v=$(rocm-smi 2>/dev/null | awk -v g="$GPU" 'NR>6 && $1==g {print $(NF-1)}' | tr -d '%')
        [[ -n "$v" && "$v" -lt 12 ]] && break
        sleep 30
    done
    sleep 5
}

for pair in "${PAIRS[@]}"; do
    model="${pair%%|*}"; fmt="${pair##*|}"
    echo "[perfq] waiting for GPU $GPU free before $model $fmt ..."
    wait_free
    echo "[perfq] === $model $fmt ==="
    bash "$REPO_ROOT/scripts/run_modern_perf.sh" "$model" "$fmt" "$GPU" || echo "[perfq] $model $fmt failed"
done
echo "[perfq] done"
