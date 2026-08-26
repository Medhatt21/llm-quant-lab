#!/usr/bin/env bash
# Complete serving-performance grid: base (BF16) vs quantized (FP8), across
# modern dense and MoE models, on one MI300X, all on the nightly vLLM image
# (which supports FP8 on ROCm). Captures throughput, model-weight memory, GPU
# utilization, power, and energy per 1k tokens.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU=7
IMG="rocm/vllm-dev:nightly"
MODELS=(
  "meta-llama/Meta-Llama-3-8B-Instruct"
  "microsoft/phi-4"
  "google/gemma-3-27b-it"
  "Qwen/Qwen3-32B"
  "qwen/Qwen3-30B-A3B"
)
for m in "${MODELS[@]}"; do
  for fmt in bf16 fp8; do
    echo "[grid2] === $m $fmt ==="
    bash "$REPO/scripts/run_modern_perf.sh" "$m" "$fmt" "$GPU" "$IMG" || echo "[grid2] $m $fmt FAILED"
  done
done
# Llama-4-Scout ships as a compressed-tensors FP8 checkpoint: auto-detect (native).
echo "[grid2] === Llama-4-Scout (native FP8 ckpt) ==="
bash "$REPO/scripts/run_modern_perf.sh" "RedHatAI/Llama-4-Scout-17B-16E-Instruct-FP8-dynamic" native "$GPU" "$IMG" || echo "[grid2] Llama-4-Scout FAILED"
echo "[grid2] done"
