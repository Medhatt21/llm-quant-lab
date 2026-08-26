"""Evaluation system for quantized models.

This module provides thin wrappers around LightCompress (LLMC) for:
- Perplexity evaluation (compute_perplexity)
- Calibration data loading (load_calibration_data)
- Hardware profiling (measure_latency, measure_memory, etc.)

All evaluation delegates to LLMC's production-tested implementations.
LightCompress is REQUIRED - there are no fallback implementations.

NOTE: This module uses lazy imports to avoid import errors when
dependencies like transformers are not yet available. Functions
are loaded on first access.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

# Hardware utilities are lightweight - import eagerly
from .hardware import (
    GPUNotAvailableError,
    HardwareProfile,
    detect_hardware,
    get_accelerator_device,
    get_gpu_info,
    measure_latency,
    measure_memory,
    measure_power,
    require_gpu,
)

if TYPE_CHECKING:
    # Type hints only, not actual imports
    from .datasets import (
        compute_perplexity as _compute_perplexity,
        evaluate_with_llmc as _evaluate_with_llmc,
        list_supported_datasets as _list_supported_datasets,
        load_calibration_data as _load_calibration_data,
    )
    from .models import (
        ModelInfo as _ModelInfo,
        estimate_quantized_size as _estimate_quantized_size,
        get_model_memory_footprint as _get_model_memory_footprint,
        load_model_and_tokenizer as _load_model_and_tokenizer,
    )
    from .runner import (
        ExperimentConfig as _ExperimentConfig,
        run_experiment as _run_experiment,
    )


# ============================================================================
# Lazy Loading Helpers
# ============================================================================

_datasets_module = None
_models_module = None
_runner_module = None


def _get_datasets_module():
    """Lazily import datasets module."""
    global _datasets_module
    if _datasets_module is None:
        _datasets_module = importlib.import_module(".datasets", __package__)
    return _datasets_module


def _get_models_module():
    """Lazily import models module."""
    global _models_module
    if _models_module is None:
        _models_module = importlib.import_module(".models", __package__)
    return _models_module


def _get_runner_module():
    """Lazily import runner module."""
    global _runner_module
    if _runner_module is None:
        _runner_module = importlib.import_module(".runner", __package__)
    return _runner_module


# ============================================================================
# Lazy-loaded Functions (Datasets)
# ============================================================================


def load_calibration_data(*args, **kwargs):
    """Load calibration data using LightCompress's dataset utilities.
    
    See datasets.load_calibration_data for full documentation.
    """
    return _get_datasets_module().load_calibration_data(*args, **kwargs)


def compute_perplexity(*args, **kwargs):
    """Compute perplexity using LightCompress's PerplexityEval.
    
    See datasets.compute_perplexity for full documentation.
    """
    return _get_datasets_module().compute_perplexity(*args, **kwargs)


def evaluate_with_llmc(*args, **kwargs):
    """Run evaluation using LightCompress directly on LLMC model objects.
    
    See datasets.evaluate_with_llmc for full documentation.
    """
    return _get_datasets_module().evaluate_with_llmc(*args, **kwargs)


def list_supported_datasets():
    """List datasets supported by LightCompress evaluation."""
    return _get_datasets_module().list_supported_datasets()


# ============================================================================
# Lazy-loaded Functions (Models)
# ============================================================================


def load_model_and_tokenizer(*args, **kwargs):
    """Load a model and tokenizer from HuggingFace.
    
    See models.load_model_and_tokenizer for full documentation.
    """
    return _get_models_module().load_model_and_tokenizer(*args, **kwargs)


def estimate_quantized_size(*args, **kwargs):
    """Estimate quantized model size.
    
    See models.estimate_quantized_size for full documentation.
    """
    return _get_models_module().estimate_quantized_size(*args, **kwargs)


def get_model_memory_footprint(*args, **kwargs):
    """Get detailed memory footprint of a model.
    
    See models.get_model_memory_footprint for full documentation.
    """
    return _get_models_module().get_model_memory_footprint(*args, **kwargs)


# Lazy class accessor for ModelInfo
class _LazyModelInfo:
    """Lazy accessor for ModelInfo class."""
    _cls = None
    
    def __new__(cls):
        if cls._cls is None:
            cls._cls = _get_models_module().ModelInfo
        return cls._cls


# Create a module-level accessor that works like a class
def __getattr__(name: str) -> Any:
    """Module-level __getattr__ for lazy loading of classes."""
    if name == "ModelInfo":
        return _get_models_module().ModelInfo
    elif name == "ExperimentConfig":
        return _get_runner_module().ExperimentConfig
    elif name == "run_experiment":
        return _get_runner_module().run_experiment
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Hardware (eagerly loaded)
    "HardwareProfile",
    "measure_latency",
    "measure_memory",
    "measure_power",
    "detect_hardware",
    "require_gpu",
    "get_accelerator_device",
    "get_gpu_info",
    "GPUNotAvailableError",
    # Datasets & Evaluation (lazily loaded)
    "load_calibration_data",
    "compute_perplexity",
    "evaluate_with_llmc",
    "list_supported_datasets",
    # Models (lazily loaded)
    "load_model_and_tokenizer",
    "estimate_quantized_size",
    "get_model_memory_footprint",
    "ModelInfo",
    # Runner (lazily loaded)
    "run_experiment",
    "ExperimentConfig",
    # New modules (lazily loaded via submodule import)
    # from .lm_eval_runner import run_lm_eval, run_multi_seed_eval
    # from .matrix_runner import MatrixConfig, run_matrix
]
