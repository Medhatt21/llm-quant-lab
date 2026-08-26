#!/usr/bin/env bash
# Classify experiments/configs/*.yml by whether the target model fits on a
# single 23 GB GPU (e.g. the A10G nodes on the AUS HPC `gpu` partition) in
# fp16 fake-quant, and whether the model is gated on HuggingFace.
#
# Writes these manifests under experiments/manifests/:
#   feasible_ungated_a10g.txt  - quantized, <=~8B params, no HF token. Run now.
#   feasible_gated_a10g.txt    - quantized, <=~8B params, needs HF_TOKEN+license.
#   too_big_for_a10g.txt       - quantized, >23 GB in fp16; needs a bigger GPU.
#   fp16_baselines.txt         - FP16-only configs. NOTE: the vendored
#       LightCompress build requires a `quant:`/`sparse:` block, so these
#       standalone FP16 configs do not run as-is. They are also redundant:
#       every quantized run emits the FP16 (pretrain) perplexity first, then
#       the quantized number, so the FP16 baseline is captured for free.
#
# Each manifest is a plain list of config paths (one per line), suitable for a
# Slurm array (see scripts/run_cuda_arm.slurm).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CFG_DIR="experiments/configs"
OUT_DIR="experiments/manifests"
mkdir -p "$OUT_DIR"

# Models that fit on a 23 GB A10G in fp16 fake-quant AND are ungated on HF.
UNGATED_FIT='facebook/opt-125m facebook/opt-350m facebook/opt-1.3b facebook/opt-2.7b facebook/opt-6.7b huggyllama/llama-7b bigscience/bloom-560m bigscience/bloom-1b1 bigscience/bloom-1b7 bigscience/bloom-3b bigscience/bloom-7b1'

# Models that fit on a 23 GB A10G but are gated (need HF_TOKEN + license accept).
GATED_FIT='meta-llama/Llama-2-7b-hf mistralai/Mistral-7B-v0.1 mistralai/Mistral-7B-Instruct-v0.2 meta-llama/Llama-3.1-8B'

ungated="$OUT_DIR/feasible_ungated_a10g.txt"
gated="$OUT_DIR/feasible_gated_a10g.txt"
toobig="$OUT_DIR/too_big_for_a10g.txt"
fp16="$OUT_DIR/fp16_baselines.txt"
: > "$ungated"; : > "$gated"; : > "$toobig"; : > "$fp16"

in_set() { local needle="$1" hay="$2"; [[ " $hay " == *" $needle "* ]]; }

for f in "$CFG_DIR"/*.yml; do
    model="$(grep -E '^[[:space:]]*path:' "$f" | head -1 | awk '{print $2}')"
    # FP16-only configs (no quant section) can't run on this LLMC build; bucket
    # them separately regardless of model size.
    if ! grep -qE '^[[:space:]]*method:' "$f"; then
        echo "$f" >> "$fp16"
    elif in_set "$model" "$UNGATED_FIT"; then
        echo "$f" >> "$ungated"
    elif in_set "$model" "$GATED_FIT"; then
        echo "$f" >> "$gated"
    else
        echo "$f" >> "$toobig"
    fi
done

for m in "$ungated" "$gated" "$toobig" "$fp16"; do sort -o "$m" "$m"; done

printf '[manifests] ungated/fit (run now) : %3d configs -> %s\n' "$(wc -l < "$ungated")" "$ungated"
printf '[manifests] gated/fit (needs token): %3d configs -> %s\n' "$(wc -l < "$gated")" "$gated"
printf '[manifests] too big for A10G       : %3d configs -> %s\n' "$(wc -l < "$toobig")" "$toobig"
printf '[manifests] fp16 baselines (skip)  : %3d configs -> %s\n' "$(wc -l < "$fp16")" "$fp16"
