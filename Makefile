.PHONY: help install sync run test test-quick test-cov test-integration test-k test-all lint format clean clean-docker clean-docker-all clean-uv clean-all docker-build docker-up docker-down db-init db-migrate frontend-dev frontend-build reproduce reproduce-gpu powerlaw configs

# Default target

# IISWC reproduction targets (no GPU required for analysis-only flow).
reproduce:
	bash scripts/reproduce_iiswc.sh

reproduce-gpu:
	bash scripts/reproduce_iiswc.sh --run-gpu

powerlaw:
	docker run --rm -v $(CURDIR):/workspace --workdir /workspace --user $(shell id -u):$(shell id -g) \
		rocm/pytorch:rocm7.1_ubuntu24.04_py3.12_pytorch_release_2.8.0 \
		python /workspace/scripts/powerlaw_refit.py

configs:
	docker run --rm -v $(CURDIR):/workspace --workdir /workspace --user $(shell id -u):$(shell id -g) \
		rocm/pytorch:rocm7.1_ubuntu24.04_py3.12_pytorch_release_2.8.0 \
		python /workspace/scripts/generate_configs.py
help:
	@echo "LLM Quant Lab - Available commands:"
	@echo ""
	@echo "  Setup:"
	@echo "    make install        - Install Python dependencies via uv"
	@echo "    make llmc-clone     - Clone LightCompress (required for quantization)"
	@echo "    make llmc-check     - Check LightCompress installation"
	@echo ""
	@echo "  Experiments:"
	@echo "    make experiment     - Run a quantization experiment"
	@echo "                          MODEL=facebook/opt-125m ALGO=awq BITS=4"
	@echo "    make list-algorithms - List available quantization algorithms"
	@echo "    make run-experiment - Run via CLI with full options"
	@echo "    make report         - Generate analytics report"
	@echo ""
	@echo "  Development:"
	@echo "    make sync           - Sync dependencies with uv"
	@echo "    make run            - Run the CLI (use ARGS='...' for arguments)"
	@echo "    make test           - Run all tests"
	@echo "    make test-quick     - Fast unit tests only (no integration)"
	@echo "    make test-cov       - Tests with HTML coverage report"
	@echo "    make test-integration - Integration tests (may need DB/W&B)"
	@echo "    make test-k K=name  - Run tests matching keyword"
	@echo "    make test-all       - Full suite with coverage (CI)"
	@echo "    make lint           - Run linters"
	@echo "    make format         - Format code with black"
	@echo ""
	@echo "  Frontend:"
	@echo "    make frontend-dev   - Start frontend dev server"
	@echo "    make api-dev        - Start API server for development"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-up      - Start all services"
	@echo "    make docker-down    - Stop all services"
	@echo ""
	@echo "  ROCm Development:"
	@echo "    make rocm-build     - Build ROCm dev container (with Quark)"
	@echo "    make rocm-run       - Run the ROCm dev container"
	@echo ""
	@echo "  Database:"
	@echo "    make db-init        - Initialize database schema"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean          - Remove Python build artifacts"
	@echo "    make clean-docker-all - Prune all Docker containers/volumes/cache"
	@echo "    make clean-uv       - Clear UV package cache"
	@echo "    make clean-all      - Full cleanup (Docker + UV + project)"
	@echo ""
	@echo "  Quick Start:"
	@echo "    1. make install && make llmc-clone"
	@echo "    2. make experiment MODEL=facebook/opt-125m ALGO=awq"

# ============================================================================
# Development
# ============================================================================

# Set UV cache to /u01 to avoid home directory space issues
export UV_CACHE_DIR := /u01/.cache/uv
export HF_HOME := /u01/.cache/huggingface
export TRANSFORMERS_CACHE := /u01/.cache/huggingface
export TORCH_HOME := /u01/.cache/torch

install:
	UV_CACHE_DIR=/u01/.cache/uv uv sync --all-extras

sync:
	UV_CACHE_DIR=/u01/.cache/uv uv sync

run:
	UV_CACHE_DIR=/u01/.cache/uv uv run python -m src.main $(ARGS)

# ── Test Targets ──────────────────────────────────────────────────
# Quick unit tests (no DB, no network, no GPU - always runnable)
test:
	UV_CACHE_DIR=/u01/.cache/uv uv run pytest tests/ -v

test-quick:
	UV_CACHE_DIR=/u01/.cache/uv uv run pytest tests/ -v -x --ignore=tests/test_integration.py

# Unit tests with coverage report
test-cov:
	UV_CACHE_DIR=/u01/.cache/uv uv run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html:htmlcov

# Run only integration tests (some may require DB/W&B)
test-integration:
	UV_CACHE_DIR=/u01/.cache/uv uv run pytest tests/test_integration.py -v

# Run tests matching a keyword  (usage: make test-k K=pareto)
test-k:
	UV_CACHE_DIR=/u01/.cache/uv uv run pytest tests/ -v -k "$(K)"

# Full test suite with coverage (for CI)
test-all:
	UV_CACHE_DIR=/u01/.cache/uv uv run pytest tests/ -v --cov=src --cov-report=term-missing --tb=long

lint:
	UV_CACHE_DIR=/u01/.cache/uv uv run ruff check src/
	UV_CACHE_DIR=/u01/.cache/uv uv run mypy src/

format:
	UV_CACHE_DIR=/u01/.cache/uv uv run black src/ tests/
	UV_CACHE_DIR=/u01/.cache/uv uv run ruff check --fix src/

# ============================================================================
# Frontend
# ============================================================================

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-install:
	cd frontend && npm install

api-dev:
	uv run uvicorn src.api.server:app --reload --port 8080

# ============================================================================
# Docker - Hardware-Agnostic Targets
# ============================================================================
# Usage:
#   ROCm:  make docker-up-rocm
#   CUDA:  make docker-up-cuda
#   Default (auto-detect or ROCm fallback): make docker-up

# Build all images (uses HARDWARE_PROFILE env var, default: rocm)
docker-build:
	docker compose build

# Start all services (default profile from HARDWARE_PROFILE env var)
docker-up:
	docker compose up -d

# Stop all services
docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-shell:
	docker compose exec app /bin/bash

# --- ROCm-specific ---
docker-build-rocm:
	docker compose -f docker-compose.yml -f docker-compose.rocm.yml build

docker-up-rocm:
	docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d

docker-up-rocm-vllm:
	docker compose -f docker-compose.yml -f docker-compose.rocm.yml --profile vllm up -d

# --- CUDA-specific ---
docker-build-cuda:
	docker compose -f docker-compose.yml -f docker-compose.cuda.yml build

docker-up-cuda:
	docker compose -f docker-compose.yml -f docker-compose.cuda.yml up -d

docker-up-cuda-vllm:
	docker compose -f docker-compose.yml -f docker-compose.cuda.yml --profile vllm up -d

# ============================================================================
# ROCm Development Container
# ============================================================================

rocm-build:
	docker build -f docker/Dockerfile.rocm-dev -t llm-quant-dev .

rocm-run:
	docker run -it --name llm-quant-dev \
		--ipc=host --network=host --privileged \
		--cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE \
		--device=/dev/kfd --device=/dev/dri \
		--shm-size 16G --group-add video \
		--security-opt seccomp=unconfined \
		--security-opt apparmor=unconfined \
		-v $(PWD):/workspace \
		-v /data/.cache/huggingface:/root/.cache/huggingface \
		-e HF_HOME=/root/.cache/huggingface \
		llm-quant-dev

# ============================================================================
# Database
# ============================================================================

db-init:
	@echo "Initializing database..."
	docker compose exec db psql -U postgres -d experiments -f /docker-entrypoint-initdb.d/schema.sql

db-migrate:
	UV_CACHE_DIR=/u01/.cache/uv uv run alembic upgrade head

db-shell:
	docker compose exec db psql -U postgres -d experiments

# ============================================================================
# LightCompress Setup
# ============================================================================

# LightCompress (LLMC) is vendored in vendors/lightcompress and tracked in this repo.
# No clone step needed; ensure the tree is present (e.g. after git clone).
llmc-clone:
	@echo "LightCompress is vendored in vendors/lightcompress (tracked in this repo). Nothing to clone."
	@test -d vendors/lightcompress/llmc || (echo "ERROR: vendors/lightcompress is missing. Check your clone."; exit 1)

# Check LightCompress installation
llmc-check:
	@UV_CACHE_DIR=/u01/.cache/uv PYTHONPATH=vendors/lightcompress:$$PYTHONPATH uv run python -c \
		"from src.quant.llmc_wrappers import LLMC_AVAILABLE, LLMC_VERSION; print(f'LightCompress: available={LLMC_AVAILABLE}, version={LLMC_VERSION}')"

# ============================================================================
# Experiments
# ============================================================================

# Environment variables for all experiment commands
LLMC_ENV := UV_CACHE_DIR=/u01/.cache/uv HF_HOME=/u01/.cache/huggingface PYTHONPATH=vendors/lightcompress:$$PYTHONPATH

# Run a quantization experiment using LightCompress
# Usage: make experiment MODEL=facebook/opt-125m ALGO=awq BITS=4
experiment:
	$(LLMC_ENV) uv run python examples/run_experiment.py \
		--model $(or $(MODEL),facebook/opt-125m) \
		--algorithm $(or $(ALGO),awq) \
		--bit-width $(or $(BITS),4) \
		--group-size $(or $(GROUP),128) \
		--calib-dataset $(or $(CALIB),wikitext2) \
		--calib-samples $(or $(SAMPLES),128)

# Run experiment via CLI
# Usage: make run-experiment MODEL=facebook/opt-125m METHODS=awq DATASETS=wikitext2
run-experiment:
	$(LLMC_ENV) uv run python -m src.main run-experiment \
		--model-path $(or $(MODEL),facebook/opt-125m) \
		--quant-techs $(or $(METHODS),awq) \
		--datasets $(or $(DATASETS),wikitext2) \
		--capture-activations

# Generate report for an experiment
# Usage: make report EXP_ID=1
report:
	$(LLMC_ENV) uv run python -m src.main generate-report --experiment-id $(EXP_ID)

# List available quantization algorithms
list-algorithms:
	@$(LLMC_ENV) uv run python examples/run_experiment.py --list-algorithms

# List available quantization methods (via CLI)
list-methods:
	$(LLMC_ENV) uv run python -m src.main list-methods

# Validate a stack of methods
# Usage: make validate-stack METHODS="awq,smoothquant"
validate-stack:
	$(LLMC_ENV) uv run python -m src.main validate-stack --methods $(METHODS)

# ============================================================================
# Papers
# ============================================================================

# Clone/update Awesome-LLM-Quantization
papers-update:
	@if [ -d "papers/awesome_llm_quantization/.git" ]; then \
		cd papers/awesome_llm_quantization && git pull; \
	else \
		rm -rf papers/awesome_llm_quantization; \
		git clone https://github.com/pprp/Awesome-LLM-Quantization.git papers/awesome_llm_quantization; \
	fi

# ============================================================================
# Cleanup
# ============================================================================

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-docker:
	docker compose down -v --rmi local

# Full Docker cleanup - stops containers, removes volumes, prunes system
clean-docker-all:
	@echo "Stopping all containers..."
	-docker stop $$(docker ps -aq) 2>/dev/null
	@echo "Removing all containers..."
	-docker rm $$(docker ps -aq) 2>/dev/null
	@echo "Removing all volumes..."
	-docker volume rm $$(docker volume ls -q) 2>/dev/null
	@echo "Pruning Docker system..."
	docker system prune -af
	@echo "Pruning Docker builder cache..."
	-docker builder prune -af
	@echo "Docker cleanup complete"

# Clear UV cache
clean-uv:
	rm -rf ~/.cache/uv
	rm -rf /u01/.cache/uv
	rm -rf /tmp/uv-*
	@echo "UV cache cleared"

# Clear all caches (Docker + UV + project)
clean-all: clean clean-docker-all clean-uv
	rm -rf .local/cache/*
	@echo "All caches cleared"
	@df -h /
