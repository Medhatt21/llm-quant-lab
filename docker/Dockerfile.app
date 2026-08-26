# =============================================================================
# LLM Quant Lab - Main Application Dockerfile (ROCm)
# Simplified build using prebuilt ROCm PyTorch with native SDPA support
# =============================================================================

# Use ROCm PyTorch base image - already has efficient attention via SDPA
# PyTorch 2.x includes torch.nn.functional.scaled_dot_product_attention
# which automatically uses optimized backends (including flash attention style)
# BASE_IMAGE must be provided via --build-arg or docker-compose .env
ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS base

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=1

# -----------------------------------------------------------------------------
# System dependencies
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    tmux \
    zip \
    unzip \
    wget \
    git \
    cmake \
    build-essential \
    curl \
    libibverbs-dev \
    ca-certificates \
    iproute2 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libpq-dev \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install build dependencies
RUN pip install packaging ninja opencv-python

# -----------------------------------------------------------------------------
# Install uv package manager
# -----------------------------------------------------------------------------
RUN pip install uv

# -----------------------------------------------------------------------------
# Application dependencies
# -----------------------------------------------------------------------------
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./
COPY uv.lock* ./
COPY README.md ./

# Install dependencies with uv (disable bytecode compilation to avoid file descriptor limits)
RUN uv sync --frozen --no-dev --no-compile-bytecode || uv sync --no-dev --no-compile-bytecode

# Install Jupyter for interactive notebook work
RUN pip install --no-cache-dir jupyterlab ipywidgets

# -----------------------------------------------------------------------------
# Copy application code
# -----------------------------------------------------------------------------
COPY src/ ./src/
COPY papers/ ./papers/
COPY examples/ ./examples/

# Create directories for data
RUN mkdir -p /app/.local/models /app/.local/data /app/.local/cache /app/reports /app/outputs

# -----------------------------------------------------------------------------
# Environment configuration
# -----------------------------------------------------------------------------
ENV PYTHONPATH="/app:$PYTHONPATH"

# ROCm-specific environment variables
ENV PYTORCH_ROCM_ARCH="gfx90a" \
    HSA_FORCE_FINE_GRAIN_PCIE=1 \
    ROCM_PATH=/opt/rocm \
    HIP_PATH=/opt/rocm/hip

# Application environment variables
# DB_URL / DATABASE_URL must be provided at runtime via docker-compose environment
ENV HF_HOME="/app/.local/cache" \
    TRANSFORMERS_CACHE="/app/.local/cache" \
    HF_DATASETS_CACHE="/app/.local/data"

# -----------------------------------------------------------------------------
# Cleanup build artifacts to reduce image size
# -----------------------------------------------------------------------------
RUN rm -rf /root/.cache/pip && \
    rm -rf /tmp/*

# -----------------------------------------------------------------------------
# Health check
# -----------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import torch; print('PyTorch OK')" || exit 1

# No default entrypoint - allows flexible use (CLI, Jupyter, or interactive shell)
# For CLI: docker compose run app uv run python -m src.main --help
# For Jupyter: docker compose up app (with command override in docker-compose.yml)
# For shell: docker compose run app bash
