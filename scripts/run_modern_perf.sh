#!/usr/bin/env bash
# Modern-model serving-performance benchmark on AMD MI300X (IISWC #414).
#
# Runs `vllm bench throughput` on a cached model at a given precision and
# records throughput, model-weight memory (from the vLLM log), GPU power (host
# rocm-smi poll), and energy per 1k output tokens. No W&B, no network: models
# are read from the local HF cache and prompts are synthetic.
#
# Usage: scripts/run_modern_perf.sh <model> <bf16|fp16|fp8> <gpu_id> [vllm_img]
set -euo pipefail

MODEL="${1:?usage: run_modern_perf.sh <model> <fmt> <gpu> [img]}"
FMT="${2:-bf16}"
GPU_ID="${3:-7}"
VLLM_IMG="${4:-rocm/vllm:rocm7.0.0_vllm_0.11.2_20251210}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHORT="$(basename "$MODEL")"

# vLLM's offline hub resolution is flaky; resolve the local snapshot dir and
# pass that as --model. Models live in one of two cache roots: modern models in
# /data/.cache/huggingface, the original corpus (OPT/BLOOM/Llama-2/...) in
# /data/huggingface. Mount both and point --model at whichever has it.
FLAT="models--$(echo "$MODEL" | sed 's#/#--#g')"
if [[ -d "/data/.cache/huggingface/hub/${FLAT}" ]]; then
    HREF=/data/.cache/huggingface; CREF=/hf-cache
elif [[ -d "/data/huggingface/hub/${FLAT}" ]]; then
    HREF=/data/huggingface; CREF=/hf-cache2
else
    HREF=""
fi
if [[ -n "$HREF" ]]; then
    # A repo can have several snapshots; pick the one that actually holds
    # weights (some snapshots are config-only refs).
    SNAP_DIR=""
    for s in ${HREF}/hub/${FLAT}/snapshots/*/; do
        if ls "$s"*.safetensors "$s"*.bin >/dev/null 2>&1; then SNAP_DIR="$s"; break; fi
    done
    [[ -z "$SNAP_DIR" ]] && SNAP_DIR="$(ls -d ${HREF}/hub/${FLAT}/snapshots/*/ 2>/dev/null | head -1)"
    MODEL_ARG="${CREF}/hub/$(echo "$SNAP_DIR" | sed "s#${HREF}/hub/##")"
else
    MODEL_ARG="$MODEL"
fi
OUT="$REPO_ROOT/reports/modern_perf"
mkdir -p "$OUT"
JSON="$OUT/${SHORT}__${FMT}.json"
SUMMARY="$OUT/${SHORT}__${FMT}__summary.json"
POWER="$OUT/${SHORT}__${FMT}.power.csv"
LOG="$OUT/${SHORT}__${FMT}.log"

NUM_PROMPTS="${NUM_PROMPTS:-200}"
INPUT_LEN="${INPUT_LEN:-1024}"
OUTPUT_LEN="${OUTPUT_LEN:-256}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.85}"

DTYPE="auto"; QUANT=()
case "$FMT" in
  fp16) DTYPE="float16" ;;
  bf16) DTYPE="bfloat16" ;;
  fp8)  DTYPE="auto"; QUANT=(--quantization fp8) ;;
  native) DTYPE="auto" ;;  # pre-quantized checkpoint; let vLLM auto-detect
esac

CNAME="perfbench_${SHORT}__${FMT}_$$"
RAM="$OUT/${SHORT}__${FMT}.ram.csv"
echo "ts,power_w,gpu_pct,vram_used_b" > "$POWER"
echo "ts,host_ram_gib" > "$RAM"
poll_pid=""; ram_pid=""
trap '[[ -n "${poll_pid:-}" ]] && kill "$poll_pid" 2>/dev/null; [[ -n "${ram_pid:-}" ]] && kill "$ram_pid" 2>/dev/null || true' EXIT
( while true; do
    # Combined CSV row: card,Power(W),GPUuse(%),GFXActivity,VRAMtotal(B),VRAMused(B)
    r=$(rocm-smi --showpower --showuse --showmeminfo vram -d "$GPU_ID" --csv 2>/dev/null \
        | awk -F, 'NR==2 {print $2","$3","$6}')
    [[ -n "$r" ]] && printf '%s,%s\n' "$(date +%s)" "$r" >> "$POWER"
    sleep 0.3
  done ) & poll_pid=$!
# Host RAM used by the benchmark container (peak), via docker stats. Look the
# container up by name filter (robust to exact-name timing/formatting issues).
( while true; do
    cid=$(docker ps -q --filter "name=$CNAME" 2>/dev/null | head -1)
    if [[ -n "$cid" ]]; then
        mem=$(docker stats --no-stream --format '{{.MemUsage}}' "$cid" 2>/dev/null | awk '{print $1}')
        if [[ -n "$mem" ]]; then
            gib=$(echo "$mem" | sed -E 's/GiB//; s/MiB/*0.0009765625/; s/GB/*0.931/; s/MB/*0.000931/' | bc -l 2>/dev/null || echo "")
            [[ -n "$gib" ]] && printf '%s,%s\n' "$(date +%s)" "$gib" >> "$RAM"
        fi
    fi
    sleep 2
  done ) & ram_pid=$!

echo "[perf] $MODEL fmt=$FMT gpu=$GPU_ID img=$VLLM_IMG"
started=$(date +%s)
docker run --rm --name "$CNAME" \
  --device=/dev/kfd --device=/dev/dri --group-add video --group-add render \
  --ipc=host --shm-size=16g --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -e HIP_VISIBLE_DEVICES="$GPU_ID" -e HF_HOME=/hf-cache -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v "$REPO_ROOT:/workspace" -v /data/.cache/huggingface:/hf-cache -v /data/huggingface:/hf-cache2 --workdir /workspace \
  "$VLLM_IMG" \
  vllm bench throughput --model "$MODEL_ARG" \
    --num-prompts "$NUM_PROMPTS" --input-len "$INPUT_LEN" --output-len "$OUTPUT_LEN" \
    --max-model-len "$MAX_MODEL_LEN" --dtype "$DTYPE" \
    --gpu-memory-utilization "$GPU_MEM_UTIL" "${QUANT[@]}" \
    --output-json "/workspace/reports/modern_perf/${SHORT}__${FMT}.json" \
  > "$LOG" 2>&1 || echo "[perf] vLLM returned nonzero (see $LOG)"
finished=$(date +%s)
kill "$poll_pid" 2>/dev/null || true; poll_pid=""
kill "$ram_pid" 2>/dev/null || true; ram_pid=""

WEIGHT_GB="$(grep -oE 'Model loading took [0-9.]+ ?GiB' "$LOG" | grep -oE '[0-9.]+' | tail -1 || true)"
PEAK_RAM="$(awk -F, 'NR>1 && $2+0>m {m=$2} END{if(m>0) printf "%.1f", m}' "$RAM" 2>/dev/null || true)"

python3 - "$JSON" "$POWER" "$SUMMARY" "$MODEL" "$FMT" "$GPU_ID" "$((finished-started))" "${WEIGHT_GB:-}" "${PEAK_RAM:-}" <<'PY'
import json, statistics, sys
from pathlib import Path
js, pw, out, model, fmt, gpu, dur, wgb, hram = sys.argv[1:10]
bench = {}
if Path(js).exists():
    try: bench = json.loads(Path(js).read_text())
    except json.JSONDecodeError: pass
pwr, util, vram_b = [], [], []
if Path(pw).exists():
    for i, ln in enumerate(Path(pw).read_text().splitlines()):
        if not i or "," not in ln: continue
        f = ln.split(",")  # ts,power_w,gpu_pct,vram_used_b
        try: pwr.append(float(f[1]))
        except (ValueError, IndexError): pass
        try: util.append(float(f[2]))
        except (ValueError, IndexError): pass
        try: vram_b.append(float(f[3]))
        except (ValueError, IndexError): pass
tps = bench.get("tokens_per_second") or bench.get("total_token_throughput")
active = None
if pwr:
    s = sorted(pwr); active = statistics.fmean(s[int(len(s)*0.75):] or s[-1:])
summ = {
  "model": model, "format": fmt, "gpu": gpu, "duration_s": int(dur),
  "tokens_per_second": round(tps,1) if tps else None,
  "requests_per_second": bench.get("requests_per_second"),
  "model_weight_gb": float(wgb) if wgb else None,
  "host_ram_gb": float(hram) if hram else None,
  "peak_vram_gb": round(max(vram_b)/1e9, 1) if vram_b else None,
  "mean_gpu_util_pct": round(statistics.fmean([u for u in util if u > 5]), 1) if any(u > 5 for u in util) else None,
  "active_power_w": round(active,1) if active else None,
  "peak_power_w": max(pwr) if pwr else None,
  "energy_per_1k_tok_j": round(active/tps*1000,2) if (active and tps) else None,
  "n_power_samples": len(pwr),
  "vllm_bench": bench,
}
Path(out).write_text(json.dumps(summ, indent=2))
print(f"[perf] {model} {fmt}: tok/s={summ['tokens_per_second']} wt={summ['model_weight_gb']} "
      f"ram={summ['host_ram_gb']} util={summ['mean_gpu_util_pct']}% "
      f"active_w={summ['active_power_w']} E/1k={summ['energy_per_1k_tok_j']}")
PY
echo "[perf] done -> $SUMMARY"
