"""Auto-generate LLMC YAML configs for every (model, method, bit-width) cell
in reproduction_results.csv.

Addresses reviewer rejection R-9: the repo currently ships 2 configs in
experiments/configs/ but the reproduction CSV has 174 rows. Each row should
be runnable as:

    python -m llmc --config experiments/configs/<experiment_id>.yml --task_id 0

Usage:

    docker run --rm -v /data/llm-quant-lab:/workspace --workdir /workspace \\
        --user $(id -u):$(id -g) \\
        rocm/pytorch:rocm7.1_ubuntu24.04_py3.12_pytorch_release_2.8.0 \\
        python /workspace/scripts/generate_configs.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO / "reproduction_results.csv"
DEFAULT_OUT = REPO / "experiments" / "configs"

# Map HuggingFace model path → LightCompress `model.type`.
MODEL_TYPE = {
    "facebook/opt-": "Opt",
    "bigscience/bloom-": "Bloom",
    "huggyllama/llama-": "Llama",
    "meta-llama/Llama-2-": "Llama",
    "meta-llama/Llama-3.1-": "Llama",
    "meta-llama/Llama-3-": "Llama",
    "mistralai/Mistral-": "Mistral",
    "mistralai/Mixtral-": "Mixtral",
    "mistralai/Ministral-": "Mistral",
    "Qwen/Qwen3-": "Qwen3",
    "Qwen/Qwen3.5-": "Qwen3",
}


def model_type_for(model: str) -> str:
    for prefix, mtype in MODEL_TYPE.items():
        if model.startswith(prefix):
            return mtype
    return "Llama"  # safe default


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def cell_key(r: dict[str, str]) -> tuple:
    return (r["experiment_id"], r["model"], r["method"].lower(), r["bit_width"])


def render_config(model: str, method: str, bit_width: int, exp_id: str) -> str:
    """Render an LLMC YAML config for one (model, method, bit) cell."""
    mtype = model_type_for(model)
    save_path = f"/workspace/.local/models/{exp_id}-{method}-w{bit_width}"
    seq_len = 2048
    n_calib = 128

    # Headers shared by all configs.
    head = (
        f"# LLM-Quant-Lab experiment {exp_id}\n"
        f"# Auto-generated from reproduction_results.csv by scripts/generate_configs.py.\n"
        f"# Method: {method.upper()}, model: {model}, bit width: {bit_width}\n"
        f"#\n"
        f"# Run inside the dev container:\n"
        f"#   cd /workspace/vendors/lightcompress\n"
        f"#   python -m llmc --config /workspace/experiments/configs/{exp_id}.yml --task_id 0\n"
        f"\n"
    )
    base = (
        "base:\n"
        "    seed: &seed 42\n"
        "model:\n"
        f"    type: {mtype}\n"
        f"    path: {model}\n"
        "    torch_dtype: auto\n"
    )

    # FP16 baseline — no quant block, just eval.
    if method == "fp16":
        return (
            head
            + base
            + (
                "calib:\n"
                "    name: wikitext2\n"
                "    download: True\n"
                f"    n_samples: {n_calib}\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    preproc: wikitext2_gptq\n"
                "    seed: *seed\n"
                "eval:\n"
                "    eval_pos: [pretrain]\n"
                "    name: wikitext2\n"
                "    download: True\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    inference_per_block: False\n"
                "save:\n"
                "    save_fake: False\n"
                f"    save_path: {save_path}\n"
            )
        )

    # GPTQ.
    if method == "gptq":
        return (
            head
            + base
            + (
                "calib:\n"
                "    name: wikitext2\n"
                "    download: True\n"
                f"    n_samples: {n_calib}\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    preproc: wikitext2_gptq\n"
                "    seed: *seed\n"
                "eval:\n"
                "    eval_pos: [pretrain, fake_quant]\n"
                "    name: wikitext2\n"
                "    download: True\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    inference_per_block: False\n"
                "quant:\n"
                "    method: GPTQ\n"
                "    weight:\n"
                f"        bit: {bit_width}\n"
                "        symmetric: False\n"
                "        granularity: per_group\n"
                "        group_size: 128\n"
                "    special:\n"
                "        actorder: True\n"
                "        static_groups: False\n"
                "        percdamp: 0.01\n"
                "        blocksize: 128\n"
                "        true_sequential: True\n"
                "    quant_out: True\n"
                "save:\n"
                "    save_fake: False\n"
                f"    save_path: {save_path}\n"
            )
        )

    # AWQ.
    if method == "awq":
        return (
            head
            + base
            + (
                "calib:\n"
                "    name: pileval\n"
                "    download: True\n"
                f"    n_samples: {n_calib}\n"
                "    bs: -1\n"
                "    seq_len: 512\n"
                "    preproc: pileval_awq\n"
                "    seed: *seed\n"
                "eval:\n"
                "    eval_pos: [pretrain, fake_quant]\n"
                "    name: wikitext2\n"
                "    download: True\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    inference_per_block: False\n"
                "quant:\n"
                "    method: Awq\n"
                "    weight:\n"
                f"        bit: {bit_width}\n"
                "        symmetric: True\n"
                "        granularity: per_group\n"
                "        group_size: 128\n"
                "    special:\n"
                "        trans: True\n"
                "        trans_version: v2\n"
                "        weight_clip: True\n"
                "save:\n"
                "    save_fake: False\n"
                f"    save_path: {save_path}\n"
            )
        )

    # SmoothQuant W8A8.
    if method == "smoothquant":
        return (
            head
            + base
            + (
                "calib:\n"
                "    name: pileval\n"
                "    download: True\n"
                "    n_samples: 512\n"
                "    bs: 1\n"
                "    seq_len: 512\n"
                "    preproc: txt_general_preproc\n"
                "    seed: *seed\n"
                "eval:\n"
                "    eval_pos: [pretrain, fake_quant]\n"
                "    name: wikitext2\n"
                "    download: True\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    inference_per_block: False\n"
                "quant:\n"
                "    method: SmoothQuant\n"
                "    weight:\n"
                f"        bit: {bit_width}\n"
                "        symmetric: True\n"
                "        granularity: per_channel\n"
                "    act:\n"
                f"        bit: {bit_width}\n"
                "        symmetric: True\n"
                "        granularity: per_token\n"
                "    special:\n"
                "        alpha: 0.5\n"
                "save:\n"
                "    save_trans: False\n"
                "    save_fake: False\n"
                f"    save_path: {save_path}\n"
            )
        )

    # LLM.int8().
    if method == "llmint8":
        return (
            head
            + base
            + (
                "calib:\n"
                "    name: wikitext2\n"
                "    download: True\n"
                f"    n_samples: {n_calib}\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    preproc: wikitext2_gptq\n"
                "    seed: *seed\n"
                "eval:\n"
                "    eval_pos: [pretrain, fake_quant]\n"
                "    name: wikitext2\n"
                "    download: True\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    inference_per_block: False\n"
                "quant:\n"
                "    method: LlmInt8\n"
                "    weight:\n"
                "        bit: 8\n"
                "        symmetric: True\n"
                "        granularity: per_channel\n"
                "    act:\n"
                "        bit: 8\n"
                "        symmetric: True\n"
                "        granularity: per_token\n"
                "    special:\n"
                "        threshold: 6.0\n"
                "save:\n"
                "    save_fake: False\n"
                f"    save_path: {save_path}\n"
            )
        )

    # RTN.
    if method == "rtn":
        return (
            head
            + base
            + (
                "calib:\n"
                "    name: wikitext2\n"
                "    download: True\n"
                f"    n_samples: {n_calib}\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    preproc: wikitext2_gptq\n"
                "    seed: *seed\n"
                "eval:\n"
                "    eval_pos: [pretrain, fake_quant]\n"
                "    name: wikitext2\n"
                "    download: True\n"
                "    bs: 1\n"
                f"    seq_len: {seq_len}\n"
                "    inference_per_block: False\n"
                "quant:\n"
                "    method: RTN\n"
                "    weight:\n"
                f"        bit: {bit_width}\n"
                "        symmetric: False\n"
                "        granularity: per_group\n"
                "        group_size: 128\n"
                "    quant_out: True\n"
                "save:\n"
                "    save_fake: False\n"
                f"    save_path: {save_path}\n"
            )
        )

    raise ValueError(f"Unknown method: {method}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing configs (e.g. gptq_opt125m.yml).",
    )
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"[error] CSV not found: {args.csv}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)

    # One YAML per unique (experiment_id, model, method, bit) cell.
    seen: set[tuple] = set()
    cells: dict[tuple, dict[str, str]] = {}
    for r in load_rows(args.csv):
        k = cell_key(r)
        if k in seen:
            continue
        seen.add(k)
        cells[k] = r

    methods_seen: dict[str, int] = defaultdict(int)
    written = skipped = 0
    for (exp_id, model, method, bit_str), r in cells.items():
        try:
            bit = int(bit_str) if bit_str else 16
        except ValueError:
            bit = 16
        path = args.out / f"{exp_id}_{method}_w{bit}.yml"
        if path.exists() and not args.overwrite:
            skipped += 1
            continue
        try:
            yaml = render_config(model, method, bit, exp_id)
        except ValueError as e:
            print(f"[warn] skipping {exp_id}: {e}", file=sys.stderr)
            continue
        path.write_text(yaml)
        methods_seen[method] += 1
        written += 1

    print(f"[done] wrote {written} configs to {args.out}, skipped {skipped} existing.")
    print(f"  by method:")
    for m, n in sorted(methods_seen.items()):
        print(f"    {m:14s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
