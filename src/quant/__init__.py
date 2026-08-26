"""Quantization plugin system.

This module provides the quantization interface and production-ready
implementations via LightCompress (LLMC).

Available quantizers (requires LightCompress installation):
- gptq: GPTQ quantization
- awq: AWQ quantization  
- rtn: Round-to-nearest baseline
- smoothquant: SmoothQuant W8A8
- omniquant: OmniQuant learnable quantization
- hqq, spqr, owq, quarot, etc.

Installation: make llmc-clone && export PYTHONPATH=vendors/lightcompress:$PYTHONPATH
"""

from .base import (
    Quantizer,
    QuantizerConfig,
    QuantizationState,
    QuantizationType,
    QuantizationMethod,
    get_quantizer,
    register_quantizer,
    list_quantizers,
    check_quantizer_available,
)

# Import wrappers to register quantizers
from . import llmc_wrappers  # noqa: F401

__all__ = [
    # Base classes
    "Quantizer",
    "QuantizerConfig",
    "QuantizationState",
    "QuantizationType",
    "QuantizationMethod",
    # Registry functions
    "get_quantizer",
    "register_quantizer",
    "list_quantizers",
    "check_quantizer_available",
]
