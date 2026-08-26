#!/usr/bin/env bash
# Run vllm bench throughput on a model and log result to W&B with the
# iiswc-2026-tools-track tag.
#
# Uses the pinned rocm/vllm image (digest in REPRODUCIBILITY.md). Streams
# rocm-smi --showpower polling on the host concurrently to compute mean GPU
# power draw during the run.
#
# Usage:
#   scripts/run_throughput_vllm.sh <model> [<format>] [<gpu>]
#
# Example:
#   scripts/run_throughput_vllm.sh meta-llama/Meta-Llama-3-8B-Instruct fp16 3
set -euo pipefail

MODEL="${1:?usage: run_throughput_vllm.sh <model> [<format>] [<gpu>]}"
FORMAT="${2:-fp16}"   # one of: fp16, bf16, fp8, awq, gptq
GPU_ID="${3:-3}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHORT="$(basename "$MODEL")"
OUT_DIR="$REPO_ROOT/reports/throughput"
RESULTS_JSON="$OUT_DIR/${SHORT}__${FORMAT}.json"
SUMMARY_JSON="$OUT_DIR/${SHORT}__${FORMAT}__summary.json"
POWER_LOG="$OUT_DIR/${SHORT}__${FORMAT}.power.csv"
LOG="$OUT_DIR/${SHORT}__${FORMAT}.log"
mkdir -p "$OUT_DIR"

VLLM_IMG="rocm/vllm:rocm7.0.0_vllm_0.11.2_20251210"

HF_TOKEN_VAL="$(grep -m1 ^HF_TOKEN= "$REPO_ROOT/.env" | cut -d= -f2- || true)"
WANDB_API_KEY_VAL="$(grep -m1 ^WANDB_API_KEY= "$REPO_ROOT/.env" | cut -d= -f2- || true)"
WANDB_PROJECT_VAL="$(grep -m1 ^WANDB_PROJECT= "$REPO_ROOT/.env" | cut -d= -f2- || true)"
WANDB_ENTITY_VAL="$(grep -m1 ^WANDB_ENTITY= "$REPO_ROOT/.env" | cut -d= -f2- || true)"

# Default vLLM bench knobs — tuned to be fast (a few minutes) on MI300X.
NUM_PROMPTS="${NUM_PROMPTS:-100}"
INPUT_LEN="${INPUT_LEN:-512}"
OUTPUT_LEN="${OUTPUT_LEN:-128}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
DTYPE="auto"
QUANT_FLAG=()
case "$FORMAT" in
    fp16) DTYPE="float16" ;;
    bf16) DTYPE="bfloat16" ;;
    auto) DTYPE="auto" ;;
    fp8) DTYPE="auto"; QUANT_FLAG=(--quantization fp8) ;;
    awq) DTYPE="auto"; QUANT_FLAG=(--quantization awq) ;;
    gptq) DTYPE="auto"; QUANT_FLAG=(--quantization gptq) ;;
esac

# Start rocm-smi power poller in the background (host-side).
echo "ts,power_w" > "$POWER_LOG"
poll_pid=""
trap '[[ -n "${poll_pid:-}" ]] && kill "$poll_pid" 2>/dev/null || true' EXIT
( while true; do
    val=$(rocm-smi --showpower -d "$GPU_ID" --csv 2>/dev/null \
        | awk -F, 'NR>1 && $1!~/^$/ && $2~/[0-9]/ {print $2; exit}')
    if [[ -n "$val" ]]; then
        printf '%s,%s\n' "$(date +%s)" "$val" >> "$POWER_LOG"
    fi
    sleep 0.2
  done ) &
poll_pid=$!

started=$(date +%s)
echo "[throughput] launching vLLM bench throughput on GPU $GPU_ID for $MODEL ($FORMAT) ..."
docker run --rm \
    --device=/dev/kfd --device=/dev/dri \
    --group-add video --group-add render \
    --ipc=host --shm-size=16g \
    --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
    -e HIP_VISIBLE_DEVICES="$GPU_ID" \
    -e HF_TOKEN="$HF_TOKEN_VAL" \
    -e HF_HOME=/hf-cache \
    -v "$REPO_ROOT:/workspace" \
    -v /data/.cache/huggingface:/hf-cache \
    --workdir /workspace \
    "$VLLM_IMG" \
    vllm bench throughput \
        --model "$MODEL" \
        --num-prompts "$NUM_PROMPTS" \
        --input-len "$INPUT_LEN" \
        --output-len "$OUTPUT_LEN" \
        --max-model-len "$MAX_MODEL_LEN" \
        --dtype "$DTYPE" \
        --gpu-memory-utilization "${GPU_MEM_UTIL:-0.6}" \
        "${QUANT_FLAG[@]}" \
        --output-json "/workspace/reports/throughput/${SHORT}__${FORMAT}.json" \
    > "$LOG" 2>&1 || rc=$?
finished=$(date +%s)
duration=$((finished - started))

kill "$poll_pid" 2>/dev/null || true
poll_pid=""

# Aggregate power readings and the bench JSON into a summary.
python3 - "$RESULTS_JSON" "$POWER_LOG" "$SUMMARY_JSON" "$MODEL" "$FORMAT" "$GPU_ID" "$duration" <<'PY'
import json
import statistics
import sys
from pathlib import Path

results, power, summary, model, fmt, gpu, dur_s = sys.argv[1:8]
res_path = Path(results)
pwr_path = Path(power)

bench = {}
if res_path.exists():
    try:
        bench = json.loads(res_path.read_text())
    except json.JSONDecodeError:
        pass

pwr = []
if pwr_path.exists():
    for i, line in enumerate(pwr_path.read_text().splitlines()):
        if i == 0 or "," not in line:
            continue
        try:
            pwr.append(float(line.split(",")[1]))
        except ValueError:
            pass

summary_obj = {
    "model": model,
    "format": fmt,
    "gpu": gpu,
    "duration_s": int(dur_s),
    "mean_power_w": statistics.fmean(pwr) if pwr else None,
    "peak_power_w": max(pwr) if pwr else None,
    "approx_energy_j": (statistics.fmean(pwr) * int(dur_s)) if pwr else None,
    "n_power_samples": len(pwr),
    "vllm_bench": bench,
}
Path(summary).write_text(json.dumps(summary_obj, indent=2))
print(f"[summary] {summary} -> mean_power={summary_obj['mean_power_w']} duration_s={summary_obj['duration_s']}")
PY

# Log to W&B from the dev container (which has wandb installed).
if [[ -n "$WANDB_API_KEY_VAL" ]]; then
    rsync -a "$REPO_ROOT/scripts/" /home/ubuntu/apps/llm-quant-lab/scripts/ 2>/dev/null || true
    rsync -a "$REPO_ROOT/reports/throughput/" /home/ubuntu/apps/llm-quant-lab/reports/throughput/ 2>/dev/null || true
    docker exec \
        -e WANDB_API_KEY="$WANDB_API_KEY_VAL" \
        -e WANDB_PROJECT="$WANDB_PROJECT_VAL" \
        -e WANDB_ENTITY="$WANDB_ENTITY_VAL" \
        -e WANDB_SILENT=true \
        llm-quant-devvvvv \
        python -c "
import json, os, wandb
data = json.loads(open('/workspace/reports/throughput/${SHORT}__${FORMAT}__summary.json').read())
run = wandb.init(
    project=os.environ.get('WANDB_PROJECT', 'llm-quant-lab'),
    entity=os.environ.get('WANDB_ENTITY') or None,
    name=f'throughput_${SHORT}__${FORMAT}_GPU${GPU_ID}',
    group=f'throughput_${SHORT}',
    tags=['iiswc-2026-tools-track', 'throughput', '${SHORT}'.lower(), '${FORMAT}'],
    config={'model': data['model'], 'format': data['format'], 'gpu_id': data['gpu'], 'hardware': 'MI300X'},
    notes='IISWC 2026 throughput point (R-4 mitigation).',
    reinit=True,
)
for k, v in data.items():
    if k == 'vllm_bench': continue
    if isinstance(v, (int, float)) and v is not None:
        run.summary[k] = v
for k, v in (data.get('vllm_bench') or {}).items():
    if isinstance(v, (int, float)):
        run.summary[f'vllm_{k}'] = v
run.finish()
print('[wandb] logged', run.url)
" 2>&1 | tail -5
fi

echo "[throughput] done in ${duration}s -> $SUMMARY_JSON"
