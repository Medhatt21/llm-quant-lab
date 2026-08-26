# NVIDIA Box Runbook (IISWC #414)

**Single source of truth for the agent/operator on the NVIDIA A10G host.**
Goal: produce the "Our NVIDIA" numbers for the rebuttal under the *same software
stack* as the AMD runs (PyTorch 2.9.1), so the AMD-vs-NVIDIA comparison in
`papers/iiswc2026/rebuttal.pdf` (Table 1) becomes controlled instead of
confounded by a library-version difference.

## Why this matters (read once)

Every NVIDIA cell we have today was run on `torch 2.6.0+cu124`; the AMD corpus is
on `torch 2.9.1+rocm7.2.0`. So all current paired cells are `stack_matched=False`:
an AMD-vs-NVIDIA gap could be the hardware *or* the two-minor-version PyTorch
difference. Re-running NVIDIA on torch 2.9.1 removes the version variable. What
survives is CUDA vs ROCm on the same PyTorch release, i.e. the true hardware
axis. This is also what confirms the paper's 3-bit finding (is the 3-bit gap a
NVIDIA software-stack effect, or real hardware?).

## Pinned stack (must match the AMD side)

| Component | Value |
| --- | --- |
| torch | `2.9.1` (`+cu126/cu128/cu130`, pick the tag matching the box's CUDA driver via `nvidia-smi`) |
| transformers | `5.1.0` |
| LightCompress | the vendored commit in this repo (`git -C vendors/lightcompress rev-parse HEAD`) |
| model revision | pin the HF commit hash, not a branch |
| calibration | identical `name`, `n_samples`, `seq_len`, `seed` as the YAML |
| eval | WikiText-2, `seq_len 2048`, `bs 1` |
| seeds | 42, 43, 44 (n=3) |

## Setup (once)

```bash
git clone git@github.com:Medhatt21/llm-quant-lab.git && cd llm-quant-lab   # if needed
TORCH_PIN=2.9.1 TORCH_CUDA_TAG=cu128 bash scripts/setup_cuda_arm_venv.sh    # match cuXXX to the driver
source .cuda-arm.env
python -c "import torch,transformers; print(torch.__version__, transformers.__version__)"  # expect 2.9.1+cuXXX, 5.1.0
git -C vendors/lightcompress rev-parse HEAD    # record the LLMC commit
```

## Task 1 (do first): same-stack parity subset

Turns Table 1 into a controlled comparison and validates the 3-bit finding.

```bash
bash scripts/run_parity_arm.sh 0    # refuses to run unless torch==2.9.1*; GPTQ/RTN on OPT-125M/2.7B, n=3
```

## Task 2: fill the blank "Our NVIDIA" cells in Table 1

These are the interesting rows where we do not yet have an NVIDIA number. Run
each config (they already exist in `experiments/configs/`) with the same script:

```bash
for id in 2569 2572 2664 2668 2562 2658 2662 ; do
  cfg=$(ls experiments/configs/${id}_*.yml); bash scripts/run_cuda_arm.sh "$cfg" 0
done
```
- 2569 AWQ Llama-2-7B, 2572 AWQ Llama-2-13B, 2664 AWQ Llama-30B
- 2668 AWQ Mistral-7B-Instruct  (the +40.9% "instruct drift" row)
- 2562 SmoothQuant Llama-2-7B, 2658 SmoothQuant Llama-7B, 2662 SmoothQuant Mixtral-8x7B (the MoE collapse)

For full coverage, also run the remaining feasible corpus configs:
`experiments/manifests/feasible_ungated_a10g.txt` (ungated) and
`experiments/manifests/feasible_gated_a10g.txt` (needs an HF token).

## Task 3 (optional): close the RTN 2x2 toolkit-version bisection

Three of four cells exist (pinned-stack RTN OPT-125M = 30.4717 on both vendors).
The missing one is {old LightCompress commit} x {CUDA}:

```bash
git -C vendors/lightcompress stash
git -C vendors/lightcompress checkout <OLD_CORPUS_COMMIT>
bash scripts/run_cuda_arm.sh experiments/configs/2542_rtn_w4.yml 0
git -C vendors/lightcompress checkout -
```

## Task 4 (optional): cross-hardware serving performance

To add an AMD-vs-NVIDIA performance comparison to Table 2, run the same harness
used on AMD (needs the models cached locally):

```bash
bash scripts/run_modern_perf.sh meta-llama/Meta-Llama-3-8B-Instruct bf16 0   # + fp8
python scripts/fp8_perplexity.py --model meta-llama/Meta-Llama-3-8B-Instruct  # FP8 accuracy
```

## Merge and hand back

```bash
python scripts/merge_paired_results.py \
  --master reproduction_results.csv \
  --cuda reports/cuda_arm/cuda_results.csv \
  --out reproduction_results_paired.csv \
  --amd-torch 2.9.1+rocm7.2.0
grep -E "True" reproduction_results_paired.csv | head   # new rows should be stack_matched=True
```

Hand back: `reports/cuda_arm/cuda_results.csv` (new torch-2.9.1 rows), and confirm
`stack_matched=True`. Then the numbers merge straight into Table 1 / Table 2.
