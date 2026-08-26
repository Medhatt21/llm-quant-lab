# LLM Quant Lab — Installation & Deployment Guide

This document provides detailed, hardware-specific instructions for installing,
configuring, and running the LLM Quant Lab on **CUDA (NVIDIA)**, **ROCm (AMD)**,
and **MPS (Apple Silicon)** backends. It also covers local development without
Docker.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (all backends)](#quick-start)
3. [CUDA (NVIDIA) Setup](#cuda-nvidia-setup)
4. [ROCm (AMD) Setup](#rocm-amd-setup)
5. [MPS (Apple Silicon) Setup](#mps-apple-silicon-setup)
6. [Local Development (no Docker)](#local-development-no-docker)
7. [Database Setup & Migrations](#database-setup--migrations)
8. [Weights & Biases Integration](#weights--biases-integration)
9. [Running Tests](#running-tests)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version |
|---|---|
| Docker | 24.0+ |
| Docker Compose | v2.20+ (plugin, not standalone) |
| Python | 3.10+ (for local dev only) |
| uv | latest (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) |
| Git | 2.30+ |
| Node.js | 18+ (for frontend dev) |

### Additional per-backend

| Backend | Host requirement |
|---|---|
| CUDA | NVIDIA driver ≥ 535, `nvidia-container-toolkit` |
| ROCm | ROCm ≥ 6.0 kernel driver, `/dev/kfd` and `/dev/dri` accessible |
| MPS | macOS 13+ with M1/M2/M3/M4, no Docker GPU passthrough (run natively) |

---

## Quick Start

These steps are common to all backends.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/llm-quant-lab.git
cd llm-quant-lab

# 2. Copy and configure environment
cp config/env.template .env
# Edit .env — fill in at minimum:
#   POSTGRES_PASSWORD, HF_TOKEN, WANDB_API_KEY,
#   SCIENTIST_LLM_API_KEY, SCIENTIST_LLM_MODEL

# 3. Choose your backend and start (see sections below)
```

---

## CUDA (NVIDIA) Setup

### Host requirements

```bash
# Verify NVIDIA driver
nvidia-smi
# Expected: Driver ≥ 535.x, CUDA ≥ 12.0

# Install nvidia-container-toolkit if not present
# (Ubuntu/Debian)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Docker images used

| Service | Base image | Notes |
|---|---|---|
| `app` | `nvcr.io/nvidia/pytorch:25.12-py3` | NGC monthly release, CUDA 12.x, PyTorch pre-installed |
| `vllm` | `vllm/vllm-openai:latest` | Official vLLM OpenAI-compatible server |

### Start the stack

```bash
# Build and start (CUDA)
make docker-build-cuda
make docker-up-cuda

# With vLLM inference server
make docker-up-cuda-vllm

# Or using docker compose directly
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up -d
```

### Environment variables (CUDA-specific)

Add to your `.env`:

```bash
HARDWARE_PROFILE=cuda
NVIDIA_VISIBLE_DEVICES=all          # or specific GPU indices: 0,1
CUDA_VISIBLE_DEVICES=               # optional, further restrict within container
```

### Caveats

- NGC images are large (~15 GB). First pull takes time.
- For multi-GPU, ensure `NVIDIA_VISIBLE_DEVICES` is set correctly.
- If you encounter NCCL errors, set `NCCL_P2P_DISABLE=1` in `.env`.

---

## ROCm (AMD) Setup

### Host requirements

```bash
# Verify ROCm installation
rocm-smi
# Expected: ROCm ≥ 6.0, GPU(s) listed

# Ensure /dev/kfd and /dev/dri are accessible
ls -la /dev/kfd /dev/dri/render*

# Current user should be in 'video' and 'render' groups
groups
# If not: sudo usermod -aG video,render $USER && newgrp video
```

### Docker images used

| Service | Base image | Notes |
|---|---|---|
| `app` | `rocm/pytorch:rocm7.2_ubuntu22.04_py3.10_pytorch_release_2.9.1` | Official ROCm PyTorch, stable release |
| `vllm` | Custom build from `Dockerfile.vllm-rocm` | ROCm-compatible vLLM |

### Start the stack

```bash
# Build and start (ROCm)
make docker-build-rocm
make docker-up-rocm

# With vLLM inference server
make docker-up-rocm-vllm

# Or using docker compose directly
docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d
```

### Environment variables (ROCm-specific)

Add to your `.env`:

```bash
HARDWARE_PROFILE=rocm
HIP_VISIBLE_DEVICES=0               # GPU indices from rocm-smi
```

### Caveats

- **GPU architecture**: The default `PYTORCH_ROCM_ARCH=gfx90a` targets MI200/MI300 series.
  For other GPUs, override in the Dockerfile or set `HSA_OVERRIDE_GFX_VERSION`.
  - MI300X: `gfx942` (auto-detected by ROCm 6.0+)
  - MI250: `gfx90a`
  - RX 7900 XT (RDNA3): `gfx1100`
- **Memory**: ROCm containers require `--security-opt seccomp:unconfined` and
  access to `/dev/kfd`. The compose overlay handles this automatically.
- **vLLM on ROCm**: Community support. Some features (e.g., FlashAttention-2)
  may not be available. Check vLLM ROCm compatibility notes.

---

## MPS (Apple Silicon) Setup

> **Note**: Docker cannot pass through the Apple GPU. MPS workloads must run
> natively on macOS. You can still use Docker for Postgres and the frontend.

### Host requirements

- macOS 13.0 (Ventura) or later
- Apple M1, M2, M3, or M4 chip
- Python 3.10+ via Homebrew or pyenv
- [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) (for Postgres/frontend)

### Install

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install Python dependencies
make install

# 3. Start Postgres and frontend via Docker (no GPU needed)
docker compose up -d db frontend api

# 4. Initialize database
make db-init

# 5. Run experiments natively (PyTorch uses MPS automatically)
uv run python -m src.main run-experiment \
    --model-path facebook/opt-125m \
    --quant-techs rtn \
    --datasets wikitext2 \
    --bit-width 4
```

### Environment variables (MPS-specific)

```bash
# In .env or exported
PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0   # Prevents OOM on unified memory
```

### Caveats

- **Not all quantization methods work on MPS.** GPTQ and AWQ require CUDA
  kernels. RTN and SmoothQuant (pure-PyTorch) are supported.
- **vLLM does not support MPS.** For inference benchmarking, use the standard
  PyTorch inference path instead.
- **Performance**: MPS is significantly slower than datacenter GPUs. Use it for
  development and small-scale validation only.

---

## Local Development (no Docker)

For development without Docker (GPU containers are optional; Postgres is still recommended via Docker).

### 1. Python environment

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (including dev)
make install

# Verify
uv run python -c "import torch; print(torch.__version__)"
```

### 2. Start Postgres

```bash
# Option A: Docker (recommended)
docker compose up -d db
make db-init

# Option B: Local Postgres
sudo -u postgres createdb experiments
psql -U postgres -d experiments -f src/db/schema.sql
```

### 3. Run migrations

```bash
# Set DATABASE_URL
export DATABASE_URL=postgresql://postgres:password@localhost:5432/experiments

# Run Alembic migrations
make db-migrate
```

### 4. Start the API server

```bash
make api-dev
# API available at http://localhost:8080
```

### 5. Start the frontend

```bash
make frontend-install
make frontend-dev
# Frontend available at http://localhost:5173
```

### 6. Run experiments

```bash
# Ensure LightCompress is available
make llmc-check

# Run an experiment
make experiment MODEL=facebook/opt-125m ALGO=gptq BITS=4
```

---

## Database Setup & Migrations

The project uses **Alembic** for schema migrations, with the base schema in
`src/db/schema.sql`.

### Initial setup

```bash
# Docker: schema auto-applies on first db start
docker compose up -d db

# Manual: apply base schema
psql -U postgres -d experiments -f src/db/schema.sql
```

### Running migrations

```bash
# Apply all pending migrations
make db-migrate

# Or directly:
uv run alembic upgrade head
```

### Creating new migrations

```bash
# Auto-generate from model changes
uv run alembic revision --autogenerate -m "describe your change"

# Review the generated file in alembic/versions/
# Then apply:
make db-migrate
```

### Key tables

| Table | Purpose |
|---|---|
| `experiments` | Experiment metadata, W&B links, config hashes |
| `quant_configs` | Quantization configurations |
| `metrics` | Evaluation metrics (perplexity, accuracy, latency) |
| `hardware_stats` | Hardware profiling results |
| `environment_snapshots` | Reproducible environment fingerprints |
| `experiment_groups` | Grouping experiments for ablation studies |
| `calibration_records` | Calibration dataset metadata |
| `wandb_sync_log` | Postgres ↔ W&B sync audit trail |
| `knowledge_nodes` / `knowledge_edges` | Quantization knowledge graph |

---

## Weights & Biases Integration

The system uses a **unified ownership model** between Postgres and W&B:

| Data | Owner | Reason |
|---|---|---|
| Structured summaries, configs, environment | **Postgres** | Queryable, relational |
| Time-series metrics, training curves | **W&B** | Streaming, visualization |
| Artifacts (model weights, plots) | **W&B** | Storage, versioning |
| Cross-references (run IDs, URLs) | **Both** | Linking |

### Setup

```bash
# 1. Get your API key from https://wandb.ai/authorize
# 2. Add to .env:
WANDB_API_KEY=your_key_here
WANDB_PROJECT=llm-quant-lab

# 3. The SyncManager handles all coordination automatically
```

### Using the SyncManager

```python
from src.tracking.sync_manager import SyncManager

mgr = SyncManager(
    db_url="postgresql://postgres:password@localhost:5432/experiments",
    wandb_project="llm-quant-lab",
)

# Start a run (creates entries in both Postgres and W&B)
run = mgr.start_run(
    experiment_name="gptq-opt125m-4bit",
    config={"method": "gptq", "bit_width": 4, "model": "facebook/opt-125m"},
    seed=42,
)

# Log time-series to W&B only
mgr.log_step({"loss": 0.5, "step": 1})

# Log summary to Postgres
mgr.log_summary({"final_perplexity": 15.3, "accuracy": 0.82})

# Finish (writes summaries to Postgres, finalizes W&B)
mgr.finish_run(status="completed")
```

---

## Running Tests

### Unit tests (no external services needed)

```bash
make test
# Runs: pytest tests/ -v
```

### Integration tests (require Postgres and/or W&B)

```bash
# Start Postgres
docker compose up -d db

# Run all tests including integration
DATABASE_URL=postgresql://postgres:password@localhost:5432/experiments \
WANDB_API_KEY=your_key \
uv run pytest tests/ -v

# Tests requiring Postgres or W&B are auto-skipped if env vars are missing
```

### Test coverage

```bash
uv run pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html
```

### What the tests cover

| Test file | Scope |
|---|---|
| `test_config_hash.py` | Config hashing determinism and run ID generation |
| `test_model_registry.py` | Architecture mapping and model info serialisation |
| `test_seeds.py` | Deterministic seed enforcement |
| `test_environment.py` | Environment snapshot capture |
| `test_pareto.py` | Pareto frontier computation |
| `test_knowledge_graph.py` | Knowledge graph seed data integrity |
| `test_integration.py` | Cross-subsystem integration (offline + live) |

---

## Troubleshooting

### Docker build fails with "no space left on device"

```bash
# Clean up Docker
make clean-docker-all

# Or selectively prune
docker system prune -af
docker builder prune -af
```

### "Permission denied" on `/dev/kfd` (ROCm)

```bash
sudo usermod -aG video,render $USER
newgrp video
# Log out and back in, then retry
```

### NVIDIA runtime not found

```bash
# Ensure nvidia-container-toolkit is installed and configured
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Database connection refused

```bash
# Check if Postgres is running
docker compose ps db

# Check health
docker compose exec db pg_isready -U postgres

# View logs
docker compose logs db
```

### Alembic "Target database is not up to date"

```bash
# Stamp current state and then upgrade
uv run alembic stamp head
uv run alembic upgrade head
```

### W&B authentication error

```bash
# Verify your key
wandb login --verify

# Or set directly
export WANDB_API_KEY=your_key
```

### ROCm GPU not detected inside container

```bash
# Verify on host
rocm-smi

# Check permissions
ls -la /dev/kfd /dev/dri/render*

# Override GFX version if needed (consumer GPUs)
# In .env:
HSA_OVERRIDE_GFX_VERSION=10.3.0
```

### MPS out of memory

```bash
# Set memory watermark
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0

# Use smaller models for local testing
make experiment MODEL=facebook/opt-125m ALGO=rtn BITS=8
```

### Frontend can't reach the API

```bash
# Verify the API is running
curl http://localhost:8080/api/environment/current

# Check CORS settings if running frontend separately
# The API allows all origins in development mode
```

---

## Docker Image Reference

| Dockerfile | Backend | Base Image | Size (approx) |
|---|---|---|---|
| `Dockerfile.app-cuda` | CUDA | `nvcr.io/nvidia/pytorch:25.12-py3` | ~15 GB |
| `Dockerfile.app-rocm` | ROCm | `rocm/pytorch:rocm7.2_ubuntu22.04_py3.10_pytorch_release_2.9.1` | ~18 GB |
| `Dockerfile.vllm-cuda` | CUDA | `vllm/vllm-openai:latest` | ~10 GB |
| `Dockerfile.vllm-rocm` | ROCm | Custom ROCm vLLM build | ~20 GB |
| `Dockerfile.api` | CPU | Python slim | ~500 MB |
| `frontend/Dockerfile` | N/A | Node + Nginx | ~200 MB |

---

## Directory Structure (after install)

```
llm-quant-lab/
├── .env                    # Your configuration (from env.template)
├── .local/
│   ├── models/             # Downloaded/quantised model weights
│   ├── data/               # Datasets and calibration data
│   └── cache/              # HuggingFace cache
├── alembic/                # Database migrations
├── config/
│   └── env.template        # Environment variable template
├── docker/
│   ├── Dockerfile.app-cuda
│   ├── Dockerfile.app-rocm
│   ├── Dockerfile.vllm-cuda
│   ├── Dockerfile.vllm-rocm
│   └── Dockerfile.api
├── docker-compose.yml      # Base compose (hardware-agnostic)
├── docker-compose.cuda.yml # CUDA GPU overlay
├── docker-compose.rocm.yml # ROCm GPU overlay
├── frontend/               # React web dashboard
├── src/
│   ├── analytics/          # Pareto, plots, LaTeX, cross-hardware
│   ├── api/                # FastAPI backend
│   ├── db/                 # ORM models, schema, migrations
│   ├── eval/               # Evaluation runners (lm-eval, matrix)
│   ├── knowledge/          # Quantization knowledge graph
│   ├── llm_reports/        # Agentic scientist LLM
│   ├── models/             # Dynamic HF model registry
│   ├── serving/            # vLLM benchmark pipeline
│   ├── tracking/           # SyncManager (Postgres ↔ W&B)
│   └── utils/              # Environment, seeds, helpers
├── tests/                  # Unit and integration tests
├── papers/                 # Reference literature
├── reports/                # Generated analysis reports
└── outputs/                # Quantised model outputs
```
