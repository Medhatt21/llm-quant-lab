# Running the CUDA arm on the AUS HPC (Slurm + A10G)

This is the cluster-specific companion to [`NVIDIA_SAME_STACK_RUNBOOK.md`](../NVIDIA_SAME_STACK_RUNBOOK.md).
It documents how to run the LLM-Quant-Lab CUDA reproduction arm on the AUS HPC
the right way: **no docker, no sudo, jobs submitted through Slurm** onto the
A10G GPU partition. (IT recommends Apptainer over Docker for the *full*
containerized lab stack, but the CUDA reproduction arm needs neither — it is a
plain Python venv + Slurm, which is the lightest and most portable path.)

## The cluster at a glance

| Thing | Value | Implication |
| --- | --- | --- |
| GPU partition | `gpu` — 90 nodes, each `gpu:a10g:1` (23 GB) | Lots of parallelism, but **only models that fit in ~23 GB** run here |
| RAM per GPU node | ~15.5 GB | `.bin` checkpoints (e.g. opt-6.7b) load the full state dict into CPU RAM — tight but works |
| Filesystems | `/shared` = huge NFS (use this); `/home` = shared but ~93 % full | Keep the repo, venv, and HF cache on `/shared`, **not** `/home` |
| Slurm QOS | `gpu-long-iamer-001` caps **total submitted jobs at 10** (group-wide) | Don't submit a 1-task-per-config array of dozens of jobs; use the chunked array below |
| Container tooling | `apptainer`, `singularity` present; `docker` here is a rootless Podman shim | Not needed for the CUDA arm |

### Which models can run here?

A single 23 GB A10G fits models up to ~8 B params in fp16 fake-quant. Run
`bash scripts/build_manifests.sh` to regenerate the buckets:

- `experiments/manifests/feasible_ungated_a10g.txt` — quantized, ≤~8 B, **no HF token** (OPT ≤6.7b, BLOOM ≤7b1, huggyllama/llama-7b). Run these now.
- `experiments/manifests/feasible_gated_a10g.txt` — quantized, ≤~8 B, **needs `HF_TOKEN` + accepted license** (Llama-2-7b, Mistral-7B, Llama-3.1-8B).
- `experiments/manifests/too_big_for_a10g.txt` — 13 B–70 B / Mixtral / opt-30b+. **Cannot run on this all-A10G cluster** in fp16 fake-quant; they need a ≥40 GB GPU.
- `experiments/manifests/fp16_baselines.txt` — FP16-only configs. The vendored LightCompress build requires a `quant:`/`sparse:` block so these don't run standalone; the FP16 perplexity is captured anyway as the `pretrain` eval line at the top of every quantized run's log.

## First-time setup (each user, ~5 min)

```bash
# 1. Get your own checkout on /shared (NOT /home — quota).
cd /shared/$USER            # or wherever you keep projects on /shared
git clone git@github.com:Medhatt21/llm-quant-lab.git
cd llm-quant-lab

# 2. Build the venv. No sudo, no docker. ~5 min + a torch download.
bash scripts/setup_cuda_arm_venv.sh
```

`setup_cuda_arm_venv.sh` creates `.venv-cuda-arm/` and a **relocatable**
`.cuda-arm.env`. It pins the stack validated on this cluster:
`torch 2.6.0+cu124`, `torchvision 0.21.0+cu124`, `transformers 5.1.0`, plus
`nvidia-cusparselt-cu12`, `pillow`, `einops`, `torchvision`, `human-eval`
(all needed by the vendored LightCompress import chain). The HF cache defaults
to a `hf-cache/` dir next to the repo (on `/shared`), so you won't blow your
`/home` quota.

> Sharing one HF cache across users avoids re-downloading ~60 GB of models.
> Point everyone at a common, group-readable dir:
> `export HF_HOME=/shared/<group-dir>/hf-cache` before submitting.

## Smoke test (login node, ~2 min)

```bash
bash scripts/run_cuda_arm.sh experiments/configs/gptq_opt125m.yml 0
# -> reports/cuda_arm/cuda_results.csv gets an OPT-125M GPTQ-W4 row (~29.4 ppl)
```

## Running the real batch via Slurm

Each array task chews through a **chunk** of the manifest (round-robin), so the
whole set fits inside the 10-job QOS cap. 8 tasks = 8 nodes in parallel:

```bash
# ungated quantized set (no token needed):
sbatch --array=1-8 scripts/run_cuda_arm.slurm

# gated models (after `export HF_TOKEN=hf_...` and accepting licenses on HF):
MANIFEST=experiments/manifests/feasible_gated_a10g.txt \
  HF_TOKEN=hf_xxx sbatch --array=1-4 --export=ALL scripts/run_cuda_arm.slurm

# one explicit config on one node:
sbatch scripts/run_cuda_arm.slurm experiments/configs/2542_rtn_w4.yml
```

Monitor and collect:

```bash
squeue -u $USER
tail -f reports/cuda_arm/slurm/cuda-arm_<jobid>_<task>.out

# After the array finishes, rebuild the master CSV from the race-free per-config
# row files (parallel tasks each write their own reports/cuda_arm/rows/*.csv):
bash scripts/collect_cuda_results.sh
cat reports/cuda_arm/cuda_results.csv
```

Then merge the CUDA numbers into the paired master CSV (see
`NVIDIA_SAME_STACK_RUNBOOK.md` Step 3):

```bash
python scripts/merge_paired_results.py \
    --master reproduction_results.csv \
    --cuda  reports/cuda_arm/cuda_results.csv \
    --out   reproduction_results_paired.csv
```

## Gotchas already handled (so you don't rediscover them)

- **`libcusparseLt.so.0` not found** — torch ≥2.6 cu124 wheels need the bundled
  NVIDIA libs on `LD_LIBRARY_PATH`. `.cuda-arm.env` adds every
  `nvidia/*/lib` dir automatically.
- **`bad interpreter` after moving the repo** — venv console scripts have
  absolute shebangs. The runner now invokes `python -m torch.distributed.run`
  instead of the `torchrun` shim, so a moved/copied venv still works.
- **transformers refuses to load `.bin`** — it requires torch ≥2.6 for
  `torch.load`; that's why we pin torch 2.6.0.
- **FP16 configs crash with `'EasyDict' has no attribute 'quant'`** — expected;
  see `fp16_baselines.txt` note above.
