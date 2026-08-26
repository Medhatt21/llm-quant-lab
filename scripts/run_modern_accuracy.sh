#!/usr/bin/env bash
# Sequentially run LLMC PTQ on modern models inside the ROCm dev container
# (lql-work), fully offline, parsing pretrain (FP16) and fake_quant WikiText-2
# perplexity. Waits for the GPU to be free (no running llmc) before each job.
#
# Usage: scripts/run_modern_accuracy.sh cfg1.yml cfg2.yml ...
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$REPO_ROOT/reports/modern_accuracy"
CSV="$OUT/results.csv"
mkdir -p "$OUT"
[ -f "$CSV" ] || echo "config,model,method,bit,fp16_ppl,quant_ppl,delta_pct,duration_s" > "$CSV"

CTR=lql-work
PORT=29540

wait_for_gpu() {
    # Bracket trick avoids pgrep matching its own command line.
    while docker exec "$CTR" bash -lc 'pgrep -f "[l]lmc --config" >/dev/null 2>&1'; do
        sleep 30
    done
}

for cfg in "$@"; do
    name="$(basename "$cfg" .yml)"
    log="$OUT/${name}.log"
    echo "[acc] waiting for GPU (no running llmc) before $name ..."
    wait_for_gpu
    echo "[acc] === running $name ==="
    PORT=$((PORT+1))
    start=$(date +%s)
    docker exec \
      -e HF_HOME=/data/.cache/huggingface \
      -e HF_DATASETS_CACHE=/data/huggingface/datasets \
      -e HF_HUB_OFFLINE=1 -e HF_DATASETS_OFFLINE=1 -e HIP_VISIBLE_DEVICES=7 \
      "$CTR" bash -lc "cd /workspace/vendors/lightcompress && torchrun --nproc_per_node=1 --master_port=$PORT -m llmc --config /workspace/experiments/configs/${name}.yml --task_id 0" \
      > "$log" 2>&1
    dur=$(( $(date +%s) - start ))

    # Parse ppl values: take the field after 'is' (avoid the '2' in 'wikitext2')
    # and collapse torchrun's adjacent double-logging with uniq. First unique =
    # pretrain (FP16), second = fake_quant.
    mapfile -t ppls < <(grep -oE 'ppl on wikitext2 is [0-9.]+' "$log" | awk '{print $NF}' | uniq)
    fp16="${ppls[0]:-NA}"; quant="${ppls[1]:-NA}"
    model="$(grep -E '^\s*path:' "$REPO_ROOT/experiments/configs/${name}.yml" | head -1 | awk '{print $2}')"
    method="$(grep -E '^\s*method:' "$REPO_ROOT/experiments/configs/${name}.yml" | head -1 | awk '{print $2}')"
    bit="$(grep -E '^\s*bit:' "$REPO_ROOT/experiments/configs/${name}.yml" | head -1 | awk '{print $2}')"
    delta="NA"
    if [[ "$fp16" != "NA" && "$quant" != "NA" ]]; then
        delta=$(python3 -c "print(f'{($quant-$fp16)/$fp16*100:.2f}')" 2>/dev/null || echo NA)
    fi
    echo "$name,$model,$method,$bit,$fp16,$quant,$delta,$dur" >> "$CSV"
    echo "[acc] $name: fp16=$fp16 quant=$quant delta=${delta}% (${dur}s)"
done
echo "[acc] all done -> $CSV"
