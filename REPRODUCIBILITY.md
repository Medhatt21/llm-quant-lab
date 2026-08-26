# Reproducibility — Pinned Software Stack

This document pins the exact software stack used to produce the
174-experiment reproduction corpus. Reviewers and re-implementors should
match these versions; deviation is a confound for cross-hardware claims.

## Hardware

| Field | Value |
| --- | --- |
| Primary GPU | AMD Instinct **MI300X** (CDNA 3, gfx942, 192 GB HBM3) |
| Secondary GPU | AMD Instinct **MI210** (CDNA 2, 64 GB HBM2e) |
| Driver / runtime | ROCm **7.1.0** |
| Host CPUs | 256 logical cores |
| Host RAM | 2.2 TiB |

`rocminfo` and `rocm-smi --showproductname` outputs are committed at
`docker/host_rocm_info.txt` and should be re-captured per host.

## Container images (digests pinned)

| Service | Image | Digest |
| --- | --- | --- |
| vLLM stable (eval) | `rocm/vllm:rocm7.0.0_vllm_0.11.2_20251210` | `sha256:e7f02dd2ce3824959658bc0391296f6158638e3ebce164f6c019c4eca8150ec7` |
| vLLM nightly (dev) | `rocm/vllm-dev:nightly` | `sha256:d355bc9fc386b08c84b0935714b7953aee3a8cd6f0f5ee053bb703b0b04c7eee` |
| PyTorch dev | `rocm/pytorch:rocm7.1_ubuntu24.04_py3.12_pytorch_release_2.8.0` | `sha256:3e917342db23b080cc7aa274321b4a7f33eb321e71b9607d69c0cb4deaaa8820` |

Pull by digest, not tag, when reproducing:

```bash
docker pull rocm/vllm@sha256:e7f02dd2ce3824959658bc0391296f6158638e3ebce164f6c019c4eca8150ec7
```

## Python packages (versions in the dev container)

| Package | Version |
| --- | --- |
| `torch` | `2.9.1+rocm7.2.0.git7e1940d4` |
| `torchaudio` | `2.9.0+rocm7.2.0.gite3c6ee2b` |
| `torchvision` | `0.24.0+rocm7.2.0.gitb919bd0c` |
| `transformers` | `5.1.0` |
| `accelerate` | `1.12.0` |
| `vllm` (dev) | `0.11.2.dev673+g839868462` |

Re-export with `pip freeze > docker/pinned-requirements.txt` after any
container rebuild.

## Vendored dependencies

| Vendor | Path | Upstream |
| --- | --- | --- |
| LightCompress (LLMC) | `vendors/lightcompress/` | https://github.com/ModelTC/LightCompress |

`vendors/lightcompress/` is vendored (not a git submodule). The upstream
commit it was synchronised against is **not currently recorded** — this is a
known reproducibility gap; resolve by either (a) replacing the vendor with a
git submodule pinned to a specific upstream commit, or (b) adding
`vendors/lightcompress/UPSTREAM_COMMIT` recording the SHA used at vendor
import.

## Cross-hardware paired runs

Cross-hardware claims require running the AMD column **and** an NVIDIA
column under matched software versions, identical model weights, and
identical calibration RNG seeds.

### Path A — no docker, no sudo (recommended for shared NVIDIA clusters)

For NVIDIA hosts where docker/sudo are unavailable (university clusters,
vendor-loaned boxes), provision a user-level Python virtualenv via `uv`:

```bash
bash scripts/setup_cuda_arm_venv.sh   # installs uv to ~/.local/bin if missing
                                      # creates .venv-cuda-arm/
                                      # writes .cuda-arm.env
bash scripts/run_cuda_arm.sh experiments/configs/gptq_opt125m.yml 0
```

Override `TORCH_CUDA_TAG=cu118|cu121|cu124` and `TORCH_PIN=2.x.y` if the
cluster's CUDA driver requires a different wheel. The bootstrap installs
`torch + transformers 5.1.0 + accelerate + datasets + lm-eval + loguru +
easydict + scipy + pyyaml` and nothing else; **vLLM is intentionally not
installed** because LLMC fake-quant runs through plain
transformers + accelerate, and the CUDA arm we need is the LLMC accuracy
column, not a vLLM throughput cell.

### Path B — docker (use if the NVIDIA host has it)

The CUDA-arm Dockerfile lives at `docker/Dockerfile.cuda-arm`; build it
from the same vLLM commit recorded above (currently
`0.11.2.dev673+g839868462`).

For each paired run, log:

- container digest (this file)
- model HF revision (commit hash, not branch)
- LLMC config hash (sha256 of the YAML in `experiments/configs/`)
- random seeds (base seed in YAML)
- start/end timestamps and host name (for energy-log alignment)

## Weights & Biases logging

All experiments connected to the IISWC 2026 Tools-track submission are logged
to W&B with the tag **`iiswc-2026-tools-track`** so they can be filtered as a
single set. The Python wrapper at `scripts/wandb_run_llmc.py` enforces the
tagging convention; do not invoke `torchrun -m llmc` directly when producing
paper-bound numbers — call it through the wrapper.

Per-run metadata logged:

| Field | Value |
| --- | --- |
| `tags` | `iiswc-2026-tools-track`, `<method>`, `<model_family>`, `<hardware>` |
| `name` | `<method>_<model_short>_w<bit>_seed<seed>_GPU<gpu>` |
| `group` | `<method>_<model_short>_w<bit>` (lets seeds aggregate cleanly) |
| `config` | full YAML attached as an input artifact |
| `summary.wikitext2_ppl` | parsed from LLMC `EVAL: ppl on wikitext2` |
| `summary.llmc_duration_s` | parsed from LLMC `llmc_duration_time` |
| `artifacts` | the raw `.log` is uploaded for traceability |

Set `WANDB_API_KEY`, `WANDB_PROJECT`, and (optionally) `WANDB_ENTITY` in
`.env`; the runners pick them up automatically via the dev container's env.

Filtering example for the W&B UI:

```text
tags ∋ "iiswc-2026-tools-track"
group = "gptq_opt-125m_w4"     # all seeds for one config
```

