# LLM-Quant-Lab

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22116400.svg)](https://doi.org/10.5281/zenodo.22116400)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A cross-hardware quantization validation framework for large language models. LLM-Quant-Lab automates post-training quantization experiments with deterministic reproducibility, structured knowledge graph navigation, and full-stack experiment management.

> **Paper:** M. Abouzeid, I. Amer, F. Pasha, "Tools-LLM-Quant-Lab: An Open Tool for
> Cross-Hardware Reproducibility Characterization of LLM Post-Training Quantization
> on AMD ROCm," in *IEEE International Symposium on Workload Characterization
> (IISWC)*, 2026.
>
> This repository is the evaluated artifact. Start at
> **[AE_QUICKSTART.md](AE_QUICKSTART.md)** — steps 1-4 validate the published
> 174-experiment corpus in a few minutes with no GPU and no model downloads.

## Features

- **12+ Quantization Methods**: GPTQ, AWQ, SmoothQuant, RTN, HQQ, OmniQuant, QuaRot, SPQR, OWQ, LLM.int8(), ZeroQuant, ParetoQ, and more via LightCompress
- **Method Stacking**: Combine compatible quantization methods with automatic compatibility validation
- **Comprehensive Hooks**: Inspect weights, activations, and KV cache at every layer
- **Unified Experiment Tracking**: PostgreSQL + Weights & Biases via SyncManager
- **Agentic Scientist**: LLM-powered analysis with 13 tools (SQL queries, code execution, W&B data, plotting, literature search, knowledge graph, Pareto frontiers, model weight inspection, web search, and more)
- **Hardware Profiling**: Latency, throughput, memory, and power measurement
- **Analytics**: Pareto frontiers, ablation heatmaps, LaTeX export, cross-hardware comparison
- **Dynamic Model Registry**: Discover and evaluate any HuggingFace model with LightCompress compatibility detection
- **Quantization Knowledge Graph**: Interactive force-directed graph linking data types, hardware, schemes, and algorithms — auto-enriched from papers and algorithm tables
- **Multi-Hardware Support**: CUDA (NVIDIA), ROCm (AMD), MPS (Apple Silicon) via parameterised Docker setup
- **Reproducibility**: Environment fingerprinting, deterministic seeds, config hashing (SHA-256), Alembic migrations
- **Web Dashboard**: React/TypeScript frontend with experiment management, model browser, knowledge graph visualizer, and AI report viewer

---

## Table of Contents

- [Reproducing Published Results](#reproducing-published-results)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running Experiments](#running-experiments)
- [Testing](#testing)
- [Web Dashboard](#web-dashboard)
- [CLI Reference](#cli-reference)
- [Scientist LLM Reports](#scientist-llm-reports)
- [Knowledge Graph](#knowledge-graph)
- [Docker Services](#docker-services)
- [Frontend Development](#frontend-development)
- [Project Structure](#project-structure)
- [Extending the Framework](#extending-the-framework)
- [Troubleshooting](#troubleshooting)

---

## Reproducing Published Results

This repository is the artifact for the IISWC 2026 Tools-track paper. The
fastest way to reproduce the headline analyses without GPU access is:

```bash
# Pulls the pinned ROCm 7.1 image, refits the per-method power law with
# 1,000-sample bootstrap CIs, and auto-generates all 174 experiment configs
# from reproduction_results.csv. No GPU required.
make reproduce
```

Outputs:

| Path | Content |
| --- | --- |
| `reports/powerlaw/per_method_fit.csv` | Per-method `α`, `β`, 95% CI, `R²` |
| `reports/powerlaw/per_method_fit.tex` | Booktabs LaTeX table (Table~\ref{tab:powerlaw_perfit} in the paper) |
| `reports/powerlaw/per_method_curves.pdf` | Per-method scaling figure |
| `experiments/configs/<exp_id>_<method>_w<bit>.yml` | One LLMC YAML per cell of the 174-row corpus |

To rerun the headline GPU experiments on a visible MI300X / MI210:

```bash
make reproduce-gpu
```

The exact software stack (Docker image digests, ROCm version, vLLM commit,
PyTorch version, transformers version) is recorded in
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

The paired NVIDIA arm of any cross-hardware claim must be produced under the
same software stack. `scripts/reproduce_iiswc.sh` is hardware-agnostic and can
be invoked on a CUDA host that has the same image pulled; the resulting CSV
column slots directly into `reproduction_results.csv` under `nvidia_value`.

---

## Prerequisites

- **Python** 3.10+
- **Docker** 24.0+ and **Docker Compose** v2.20+
- **GPU**: NVIDIA (CUDA 12+), AMD (ROCm 6.0+), or Apple Silicon (MPS)
- **uv** package manager (recommended) or pip

> **Detailed installation instructions for each hardware backend** are in [`docs/INSTALL.md`](docs/INSTALL.md).

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/Medhatt21/llm-quant-lab.git
cd llm-quant-lab
```

### 2. Set up environment variables

```bash
# Copy the template and fill in your credentials
cp config/env.template .env
# Edit .env — at minimum set:
#   POSTGRES_PASSWORD, HF_TOKEN, WANDB_API_KEY,
#   SCIENTIST_LLM_BASE_URL, SCIENTIST_LLM_API_KEY
```

See [Configuration](#configuration) for a full variable reference.

### 3. Start the stack

```bash
# For AMD GPUs (ROCm)
make docker-up-rocm

# For NVIDIA GPUs (CUDA)
make docker-up-cuda

# Initialize the database schema
make db-init
make db-migrate
```

### 4. Run your first experiment

```bash
# AWQ 4-bit quantization on OPT-125M
make experiment MODEL=facebook/opt-125m ALGO=awq BITS=4
```

### 5. Open the dashboard

Visit `http://localhost:<FRONTEND_PORT>` (the port from your `.env`, default `18392`).

---

## Configuration

All configuration lives in the `.env` file at the project root. Copy from `config/env.template` or `.env.example`.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `HARDWARE_PROFILE` | `cuda` or `rocm` — selects Docker images | `rocm` |
| `HIP_VISIBLE_DEVICES` | GPU indices (ROCm) | `0` or `0,1` |
| `POSTGRES_HOST` | Database hostname | `db` (Docker) or `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_USER` | Database username | `llmquant` |
| `POSTGRES_PASSWORD` | Database password | *(set a strong password)* |
| `POSTGRES_DB` | Database name | `experiments` |
| `DATABASE_URL` | Full connection string (or auto-built from above) | `postgresql://llmquant:pass@db:5432/experiments` |
| `HF_TOKEN` | HuggingFace API token | `hf_xxxx` |
| `SCIENTIST_LLM_PROVIDER` | `openai`, `anthropic`, `local`, or `openrouter` | `openai` |
| `SCIENTIST_LLM_BASE_URL` | LLM API endpoint | `http://localhost:8000/v1` |
| `SCIENTIST_LLM_API_KEY` | LLM API key | `sk-xxxx` |
| `SCIENTIST_LLM_MODEL` | Model name | `gpt-4-turbo` |
| `SCIENTIST_LLM_TIMEOUT` | Request timeout in seconds | `300` |
| `WANDB_API_KEY` | Weights & Biases API key | `wandb_v1_xxxx` |
| `WANDB_PROJECT` | W&B project name | `llm-quant-lab` |
| `API_PORT` | FastAPI backend port | `18247` |
| `FRONTEND_PORT` | Frontend web UI port | `18392` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WANDB_ENTITY` | W&B team/entity name | *(your username)* |
| `VLLM_PORT` | vLLM inference port | `18456` |
| `VLLM_MODEL` | Model path for vLLM serving | *(empty)* |
| `PGADMIN_PORT` | pgAdmin web UI port | `18519` |
| `PGADMIN_EMAIL` | pgAdmin login email | `admin@llmquant.lab` |
| `PGADMIN_PASSWORD` | pgAdmin login password | *(set one)* |
| `BASE_IMAGE` | Docker base image | `rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `LOG_FORMAT` | `text` or `json` | `text` |

### Local Directories

All cache, model, and data files are stored inside the project directory (excluded from git):

```
llm-quant-lab/
├── .local/
│   ├── models/    # Model weights and checkpoints
│   ├── data/      # Datasets and calibration data
│   └── cache/     # HuggingFace cache
├── reports/       # Generated scientist reports
└── outputs/       # Quantized model outputs
```

---

## Running Experiments

### Using Make targets (recommended)

```bash
# Run AWQ 4-bit on OPT-125M (simplest)
make experiment MODEL=facebook/opt-125m ALGO=awq BITS=4

# Customize group size and calibration
make experiment MODEL=facebook/opt-125m ALGO=gptq BITS=4 GROUP=64 CALIB=wikitext2 SAMPLES=256

# Run via the full CLI
make run-experiment MODEL=facebook/opt-125m METHODS=awq DATASETS=wikitext2

# List available quantization algorithms
make list-algorithms

# Generate a scientist report for a completed experiment
make report EXP_ID=1
```

### Using the CLI directly

```bash
# Run an experiment
uv run python -m src.main run-experiment \
    --model-path facebook/opt-125m \
    --quant-techs awq \
    --datasets wikitext2 \
    --bit-width 4 \
    --capture-activations

# List available quantization methods
uv run python -m src.main list-methods

# List experiments in the database
uv run python -m src.main list-experiments

# Show experiment details
uv run python -m src.main show-experiment --experiment-id 1

# Generate a scientist LLM report
uv run python -m src.main generate-report --experiment-id 1

# Validate a method stack
uv run python -m src.main validate-stack --methods "awq,smoothquant"

# Get a quantization profile suggestion
uv run python -m src.main suggest-mode --rps 200 --sla-ms 100

# Export results for a paper
uv run python -m src.main paper-export --experiment-id 1
```

### Using the example scripts

```bash
# Compare AWQ vs GPTQ on OPT-125M
python examples/research_workflow.py \
    --model facebook/opt-125m \
    --algorithms awq,gptq

# Run a single experiment with detailed output
python examples/run_experiment.py \
    --model facebook/opt-125m \
    --algorithm awq \
    --bit-width 4

# Compare multiple methods head-to-head
python examples/compare_methods.py

# Analyze layer-wise quantization effects
python examples/analyze_layers.py
```

### Method Stacking

Some quantization methods can be combined. The framework validates compatibility automatically:

```bash
# Valid: Weight quantization + KV cache quantization
uv run python -m src.main validate-stack --methods "awq,kvquant"

# Invalid: Two weight-only methods (will be rejected)
uv run python -m src.main validate-stack --methods "awq,gptq"
```

### Launching via the Web Dashboard

1. Open the dashboard at `http://localhost:<FRONTEND_PORT>`
2. Navigate to **Experiments > New Experiment**
3. Select a model, algorithm, bit width, and calibration dataset
4. Click **Create & Launch** — the experiment runs in the background
5. Monitor progress on the experiment detail page (auto-refreshes every 5s)

---

## Testing

The project includes a comprehensive test suite covering unit tests, integration tests, and subsystem tests.

### Make targets

```bash
# Run all tests
make test

# Fast unit tests only (skip integration tests)
make test-quick

# Tests with HTML coverage report (output in htmlcov/)
make test-cov

# Run only integration tests (some require DB/W&B)
make test-integration

# Run tests matching a keyword
make test-k K=pareto
make test-k K=knowledge
make test-k K=seed

# Full suite with coverage for CI
make test-all
```

### Running directly with pytest

```bash
# All tests with verbose output
pytest tests/ -v

# Stop on first failure
pytest tests/ -v -x

# Run a specific test file
pytest tests/test_knowledge_graph.py -v

# Run a specific test class or function
pytest tests/test_integration.py::TestParetoIntegration -v
pytest tests/test_seeds.py::test_set_seeds -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Test structure

| Test file | What it covers |
|-----------|---------------|
| `test_config_hash.py` | Config hashing determinism, run ID generation |
| `test_environment.py` | Environment snapshotting and hash stability |
| `test_seeds.py` | Deterministic seed enforcement |
| `test_pareto.py` | Pareto frontier computation |
| `test_model_registry.py` | HuggingFace model registry and architecture mapping |
| `test_knowledge_graph.py` | Knowledge graph node/edge integrity |
| `test_integration.py` | End-to-end: config round-trips, DB models, API routes, calibration fingerprinting, Pareto, KG, seeds, sync manager, paper export CLI |

Tests that require external services (PostgreSQL, W&B) are automatically skipped when those services are not available.

---

## Web Dashboard

The web dashboard provides a full UI for managing experiments, browsing models, exploring the knowledge graph, and reading AI-generated reports.

### Starting the dashboard

**With Docker (recommended):**

```bash
make docker-up-rocm   # or docker-up-cuda
# Dashboard available at http://localhost:<FRONTEND_PORT>
# API available at http://localhost:<API_PORT>
```

**For local development:**

```bash
# Terminal 1: Start the API server
make api-dev

# Terminal 2: Start the frontend dev server
make frontend-install   # first time only
make frontend-dev
```

### Dashboard features

- **Dashboard home**: Overview statistics, recent experiments, quick actions
- **Experiments list**: Filter, search, and browse all experiments
- **Experiment detail**: Metrics, charts, hardware stats, W&B links, with live status polling for running experiments
- **New Experiment**: Configure and launch experiments from the browser
- **Model Browser**: Search HuggingFace models, check LightCompress compatibility
- **Knowledge Graph**: Interactive force-directed graph of quantization algorithms, data types, hardware, and schemes
- **Scientist Reports**: Read AI-generated analysis reports with findings, plots, and recommendations

---

## CLI Reference

All CLI commands are available via `uv run python -m src.main` or the `llm-quant` entry point:

| Command | Description |
|---------|-------------|
| `run-experiment` | Run a quantization experiment |
| `list-methods` | List available quantization methods |
| `list-experiments` | List experiments in the database |
| `show-experiment` | Show details for a specific experiment |
| `generate-report` | Generate a scientist LLM report |
| `validate-stack` | Validate method compatibility |
| `suggest-mode` | Suggest quantization profile for target latency/throughput |
| `paper-export` | Export experiment results for publication |

---

## Scientist LLM Reports

The Agentic Scientist is an LLM-powered analysis pipeline that generates research reports for your experiments. It uses a multi-turn reasoning loop with 13 tools.

### Available tools

| Tool | Description |
|------|-------------|
| `query_database` | Run SQL queries against the experiment database |
| `execute_code` | Run Python code (pandas, numpy, scipy, sklearn) |
| `compute_statistics` | Statistical tests: t-test, paired t-test, ANOVA, Cohen's d, confidence intervals |
| `generate_plot` | Create matplotlib visualizations |
| `search_arxiv` | Search ArXiv for related quantization papers |
| `query_wandb` | Fetch time-series data and artifacts from W&B |
| `read_file` | Read project files (configs, paper notes, results) |
| `generate_latex_table` | Produce publication-ready LaTeX tables |
| `inspect_model_weights` | Examine quantized model weight distributions |
| `query_knowledge_graph` | Explore the quantization knowledge graph |
| `compare_experiments` | Side-by-side experiment comparison |
| `compute_pareto_frontier` | Find Pareto-optimal configurations |
| `web_search` | Search the web for relevant information |

### Configuration

Set these in your `.env`:

```bash
SCIENTIST_LLM_PROVIDER=openai          # or anthropic, local, openrouter
SCIENTIST_LLM_BASE_URL=http://your-llm-endpoint/v1
SCIENTIST_LLM_API_KEY=your-api-key
SCIENTIST_LLM_MODEL=Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8
SCIENTIST_LLM_TIMEOUT=300
```

### Generating a report

```bash
# Via Make
make report EXP_ID=1

# Via CLI
uv run python -m src.main generate-report --experiment-id 1

# Via API
curl -X POST http://localhost:<API_PORT>/api/scientist/analyze \
  -H "Content-Type: application/json" \
  -d '{"question": "Analyze the perplexity results for experiment 1"}'

# Full analysis (runs all 10 analysis questions)
curl -X POST http://localhost:<API_PORT>/api/scientist/full-analysis
```

---

## Knowledge Graph

The knowledge graph connects quantization algorithms, data types, hardware platforms, and quantization schemes in a visual, explorable graph.

### Data sources

- **Hardcoded base**: Core nodes and edges for data types (INT4, FP16, MXFP4, etc.), hardware (NVIDIA, AMD, Intel), and schemes (PTQ, QAT)
- **Dynamic enrichment**: Automatically parses `papers/quantization_algorithms_table.md` and `papers/notes/*.yaml` to add algorithm details, bit-width relationships, and paper metadata

### Exploring the graph

- **Web UI**: Navigate to the Knowledge Graph page in the dashboard
- **API**: `GET /api/knowledge/graph` with optional filters
- **Scientist tool**: The LLM can query the graph via the `query_knowledge_graph` tool during analysis

### Adding to the graph

1. Add a row to `papers/quantization_algorithms_table.md`
2. Optionally add a `papers/notes/<algorithm>.yaml` with detailed notes
3. Restart the API — the graph auto-enriches on seed

---

## Docker Services

The stack runs 4 core services (+ 2 optional) via Docker Compose:

| Service | Container | Description |
|---------|-----------|-------------|
| `app` | `llm-quant-app` | Main GPU-enabled quantization workload + JupyterLab |
| `db` | `llm-quant-db` | PostgreSQL 16 for experiment data |
| `api` | `llm-quant-api` | FastAPI backend on port `API_PORT` |
| `frontend` | `llm-quant-frontend` | React dashboard on port `FRONTEND_PORT` |
| `vllm` | `llm-quant-vllm` | *(optional)* vLLM inference server |
| `pgadmin` | `llm-quant-pgadmin` | *(optional)* pgAdmin web UI |

### Common commands

```bash
# Start (choose your hardware backend)
make docker-up-rocm
make docker-up-cuda

# Start with vLLM inference server
make docker-up-rocm-vllm
make docker-up-cuda-vllm

# View logs
make docker-logs

# Open a shell in the app container
make docker-shell

# Open a psql shell to the database
make db-shell

# Stop all services
make docker-down

# Full cleanup (containers, volumes, images)
make clean-docker-all
```

---

## Frontend Development

```bash
# Install frontend dependencies
make frontend-install

# Start frontend dev server (hot reload, port 5173)
make frontend-dev

# Start API server for development (port 8080)
make api-dev

# Build production frontend
make frontend-build
```

The frontend uses React 18, TypeScript, TanStack Query, Tailwind CSS, and `react-force-graph-2d` for the knowledge graph visualization.

---

## Project Structure

```
llm-quant-lab/
├── .env                          # Your environment configuration (from template)
├── .env.example                  # Example .env with placeholder values
├── config/
│   └── env.template              # Canonical env template with documentation
├── docker/
│   ├── Dockerfile.app-cuda       # App container (CUDA/NVIDIA)
│   ├── Dockerfile.app-rocm       # App container (ROCm/AMD)
│   ├── Dockerfile.api            # API server container
│   ├── Dockerfile.vllm-cuda      # vLLM for CUDA
│   └── Dockerfile.vllm-rocm      # vLLM for ROCm
├── docker-compose.yml            # Base docker compose (hardware-agnostic)
├── docker-compose.cuda.yml       # CUDA GPU overlay
├── docker-compose.rocm.yml       # ROCm GPU overlay
├── frontend/                     # React/TypeScript dashboard
├── papers/                       # ASPLOS 2027 paper, references, figures
├── pyproject.toml                # Python dependencies and project config
├── Makefile                      # All available commands (run `make help`)
├── src/
│   ├── main.py                   # CLI entrypoint (Typer)
│   ├── config/                   # Configuration management
│   ├── api/                      # FastAPI backend (server.py)
│   ├── quant/                    # Quantization plugins
│   │   ├── base.py               # Quantizer interface
│   │   ├── llmc_wrappers.py      # LightCompress algorithm wrappers
│   │   └── custom/               # Custom quantizers
│   ├── stacking/                 # Method compatibility validation
│   ├── hooks/                    # Weight/activation/KV cache hooks
│   ├── db/                       # Database models, schema, Alembic migrations
│   ├── eval/                     # Evaluation runners (lm-eval-harness, matrix)
│   ├── analytics/                # Pareto, plots, LaTeX, cross-hardware
│   ├── knowledge/                # Knowledge graph data and seeding
│   ├── models/                   # Dynamic HuggingFace model registry
│   ├── serving/                  # vLLM benchmark pipeline
│   ├── tracking/                 # SyncManager (PostgreSQL <-> W&B)
│   ├── utils/                    # Environment, seeds, helpers
│   └── llm_reports/              # Agentic scientist LLM pipeline + tools
├── examples/
│   ├── run_experiment.py         # Single experiment runner
│   ├── research_workflow.py      # Multi-algorithm comparison
│   ├── compare_methods.py        # Method comparison
│   └── analyze_layers.py         # Layer-wise analysis
├── tests/                        # Test suite (pytest)
├── alembic/                      # Database migrations
└── vendors/
    └── lightcompress/            # Vendored LightCompress/LLMC
```

---

## Extending the Framework

### Adding a new quantizer

1. Create a new class in `src/quant/custom/`:

```python
from ..base import Quantizer, QuantizerConfig, QuantizationState

class MyQuantizer(Quantizer):
    @property
    def name(self) -> str:
        return "my_method"

    def prepare(self, model, calibration_data):
        # Compute scales, collect statistics
        ...

    def apply(self, model, state):
        # Apply quantization
        ...
```

2. Register in `src/quant/__init__.py`:

```python
from .custom.my_quantizer import MyQuantizer
register_quantizer("my_method", MyQuantizer)
```

3. Add compatibility rules in `src/stacking/compatibility.py`

### Adding paper notes

Create a YAML file in `papers/notes/`:

```yaml
# papers/notes/my_algorithm.yaml
id: my_algorithm
title: "My Algorithm: A Novel Approach to Quantization"
core_idea: |
  Description of the core algorithmic idea...
expected_behavior: |
  - Achieves <1% accuracy degradation at 4-bit
  - Requires calibration data
method_names:
  - my_algorithm
tags:
  - weight_only
  - ptq
  - 4bit
```

This will automatically enrich the knowledge graph on next seed.

### Adding to the algorithm table

Add a row to `papers/quantization_algorithms_table.md` — the knowledge graph seeder parses this file automatically.

---

## Troubleshooting

### Configuration errors

If the application fails to start:

1. Ensure `.env` exists — copy from `config/env.template` or `.env.example`
2. Fill in **ALL** required variables (especially `POSTGRES_PASSWORD`, `HF_TOKEN`)
3. Verify the `DATABASE_URL` matches your Postgres credentials
4. Check that Docker services are running: `docker compose ps`

### Database connection issues

```bash
# Check if Postgres is healthy
docker compose ps db

# Open a direct psql shell
make db-shell

# Re-initialize schema
make db-init
make db-migrate
```

### ROCm GPU issues

```bash
# Check GPU visibility
rocm-smi

# Set specific GPUs
export HIP_VISIBLE_DEVICES=0,1

# For unsupported GPUs, override the architecture
export HSA_OVERRIDE_GFX_VERSION=10.3.0  # Example for RDNA2
```

### Tests failing

```bash
# Run with verbose output to see exact failures
make test

# Run only the failing test for more detail
pytest tests/test_integration.py::TestAPIRoutes -v --tb=long

# Integration tests that require DB/W&B skip automatically when services
# are unavailable — this is expected behavior, not a failure.
```

### Disk space

```bash
# Check disk usage
df -h /

# Clear all caches (Docker, uv, project)
make clean-all
```

---

## Supported Quantization Methods

| Method | Type | Bit Widths | Description |
|--------|------|------------|-------------|
| RTN | Weight-only | 2-8 | Round-to-nearest baseline |
| GPTQ | Weight-only | 2-8 | Hessian-based optimization |
| AWQ | Weight-only | 4 | Activation-aware scaling |
| SmoothQuant | W+A | 8 | Activation outlier smoothing |
| HQQ | Weight-only | 2-8 | Half-Quadratic Quantization |
| OmniQuant | Weight-only | 2-8 | Omnidirectional calibration |
| QuaRot | W+A | 4 | Rotation-based quantization |
| SPQR | Weight-only | 3-4 | Sparse-Quantized Representation |
| OWQ | Weight-only | 3-4 | Outlier-aware weight quantization |
| LLM.int8() | W+A | 8 | Mixed-precision decomposition |
| ZeroQuant | W+A | 8 | Zero-cost quantization |
| ParetoQ | Weight-only | 2-4 | Pareto-optimal bit allocation |

---

## Database Schema

| Table | Description |
|-------|-------------|
| `experiments` | Experiment metadata, W&B links, config hashes, seeds |
| `quant_configs` | Quantization configurations |
| `metrics` | Evaluation metrics (perplexity, accuracy, latency) |
| `hardware_stats` | Latency, throughput, memory usage |
| `layer_metrics` | Layer-wise quantization statistics |
| `scientist_reports` | LLM-generated analysis reports |
| `environment_snapshots` | Reproducible environment fingerprints |
| `experiment_groups` | Ablation study groupings |
| `calibration_records` | Calibration dataset metadata |
| `wandb_sync_log` | PostgreSQL ↔ W&B sync audit trail |
| `knowledge_nodes` | Knowledge graph nodes |
| `knowledge_edges` | Knowledge graph edges |

---

## License

MIT License — see LICENSE file for details.

## Citation

If you use LLM-Quant-Lab in your research, please cite:

```bibtex
@inproceedings{abouzeid2026llmquantlab,
  title     = {Tools-{LLM-Quant-Lab}: An Open Tool for Cross-Hardware
               Reproducibility Characterization of {LLM} Post-Training
               Quantization on {AMD} {ROCm}},
  author    = {Abouzeid, Medhat and Amer, Ihab and Pasha, Fadil},
  booktitle = {IEEE International Symposium on Workload Characterization
               (IISWC)},
  year      = {2026},
  url       = {https://github.com/Medhatt21/llm-quant-lab}
}
```

## Acknowledgments

- [LightCompress/LLMC](https://github.com/ModelTC/llmc) — Core compression toolkit
- [Awesome-LLM-Quantization](https://github.com/pprp/Awesome-LLM-Quantization) — Paper curation
- American University of Sharjah — Hardware and institutional support
