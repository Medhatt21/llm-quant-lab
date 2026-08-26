"""Model loading and evaluation utilities.

This module provides standardized model loading, size estimation,
and evaluation helpers for quantization experiments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .hardware import require_gpu

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a loaded model."""
    
    name: str
    num_params: int
    size_mb: float
    dtype: torch.dtype
    device: str
    
    @property
    def num_params_billions(self) -> float:
        """Number of parameters in billions."""
        return self.num_params / 1e9
    
    @property
    def num_params_millions(self) -> float:
        """Number of parameters in millions."""
        return self.num_params / 1e6
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "num_params": self.num_params,
            "num_params_millions": self.num_params_millions,
            "num_params_billions": self.num_params_billions,
            "size_mb": self.size_mb,
            "dtype": str(self.dtype),
            "device": self.device,
        }


def load_model_and_tokenizer(
    model_name: str,
    dtype: torch.dtype = torch.float16,
    trust_remote_code: bool = True,
    attn_implementation: str | None = None,
) -> tuple["PreTrainedModel", "PreTrainedTokenizerBase", ModelInfo]:
    """Load a model and tokenizer from HuggingFace.
    
    This function enforces GPU-only execution and does not fall back to CPU.
    
    Args:
        model_name: HuggingFace model name or path
        dtype: Model dtype (default: float16)
        trust_remote_code: Whether to trust remote code
        attn_implementation: Attention implementation ('eager', 'sdpa', 'flash_attention_2').
            If None, automatically selects 'eager' on ROCm (AMD GPUs) to avoid HIP
            memory access violations, and uses the default on other platforms.
        
    Returns:
        Tuple of (model, tokenizer, model_info)
        
    Raises:
        GPUNotAvailableError: If no GPU is available
        
    Example:
        >>> model, tokenizer, info = load_model_and_tokenizer("facebook/opt-125m")
        >>> print(f"Loaded {info.num_params_millions:.1f}M params")
    """
    # Enforce GPU requirement
    device = require_gpu()
    
    logger.info(f"Loading model: {model_name}")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Determine attention implementation
    # On ROCm (AMD GPUs), SDPA/FlashAttention can trigger HIP memory access violations
    # (HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION) with certain models like OPT.
    # Using 'eager' avoids the problematic indexSelect kernel paths.
    if attn_implementation is None:
        is_rocm = hasattr(torch.version, "hip") and torch.version.hip is not None
        if is_rocm:
            attn_implementation = "eager"
            logger.info("ROCm detected: using attn_implementation='eager' to avoid HIP memory issues")
    
    # Build model loading kwargs
    model_kwargs: dict[str, Any] = {
        "torch_dtype": dtype,
        "device_map": "auto",
        "trust_remote_code": trust_remote_code,
    }
    if attn_implementation is not None:
        model_kwargs["attn_implementation"] = attn_implementation
    
    # Load model with automatic device mapping
    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    model.eval()
    
    # Compute model info
    num_params = sum(p.numel() for p in model.parameters())
    size_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / 1e6
    
    info = ModelInfo(
        name=model_name,
        num_params=num_params,
        size_mb=size_mb,
        dtype=dtype,
        device=device,
    )
    
    logger.info(f"  Parameters: {info.num_params_millions:.1f}M")
    logger.info(f"  Size: {info.size_mb:.1f} MB")
    logger.info(f"  Device: {device}")
    
    return model, tokenizer, info


def estimate_quantized_size(
    original_size_mb: float,
    bit_width: int,
    group_size: int = 128,
    original_bits: int = 16,
) -> tuple[float, float]:
    """Estimate quantized model size.
    
    Args:
        original_size_mb: Original model size in MB
        bit_width: Target bit width
        group_size: Quantization group size
        original_bits: Original bit width (default: 16 for FP16)
        
    Returns:
        Tuple of (quantized_size_mb, compression_ratio)
        
    Example:
        >>> size, ratio = estimate_quantized_size(250.0, bit_width=4)
        >>> print(f"Estimated size: {size:.1f} MB ({ratio:.1f}x compression)")
    """
    # Base compression from bit reduction
    base_ratio = bit_width / original_bits
    
    # Overhead for scales and zeros (~1-3% depending on group size)
    # Each group needs: scale (fp16=2 bytes) + zero (bit_width bits)
    if group_size > 0:
        overhead = 1 + (32 / (group_size * bit_width))
    else:
        overhead = 1.01  # Per-channel has minimal overhead
    
    quantized_size = original_size_mb * base_ratio * overhead
    compression_ratio = original_size_mb / quantized_size
    
    return quantized_size, compression_ratio


def get_model_memory_footprint(model: "PreTrainedModel") -> dict[str, float]:
    """Get detailed memory footprint of a model.
    
    Args:
        model: The model to analyze
        
    Returns:
        Dictionary with memory breakdown in MB
    """
    # Parameter memory
    param_bytes = sum(p.numel() * p.element_size() for p in model.parameters())
    
    # Buffer memory (e.g., running stats in BatchNorm)
    buffer_bytes = sum(b.numel() * b.element_size() for b in model.buffers())
    
    # Gradient memory (if training)
    grad_bytes = sum(
        p.grad.numel() * p.grad.element_size() 
        for p in model.parameters() 
        if p.grad is not None
    )
    
    return {
        "parameters_mb": param_bytes / 1e6,
        "buffers_mb": buffer_bytes / 1e6,
        "gradients_mb": grad_bytes / 1e6,
        "total_mb": (param_bytes + buffer_bytes + grad_bytes) / 1e6,
    }
