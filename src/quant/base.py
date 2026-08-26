"""Base quantizer interface and common utilities.

This module defines the abstract Quantizer interface that all quantization
methods must implement. It provides no default implementations - all methods
must be explicitly implemented by concrete quantizer classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

import torch
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from transformers import PreTrainedModel


class QuantizationType(str, Enum):
    """Types of quantization."""
    WEIGHT_ONLY = "weight_only"
    WEIGHT_ACTIVATION = "weight_activation"
    KV_CACHE = "kv_cache"
    MIXED = "mixed"


class QuantizationMethod(str, Enum):
    """Supported quantization methods."""
    # Weight-only methods
    GPTQ = "gptq"
    AWQ = "awq"
    SPQR = "spqr"
    OWQ = "owq"
    
    # Weight + Activation methods
    SMOOTHQUANT = "smoothquant"
    LLMINT8 = "llm_int8"
    
    # KV Cache methods
    KVQUANT = "kvquant"
    KIVI = "kivi"
    
    # Advanced methods
    QUAROT = "quarot"
    OMNIQUANT = "omniquant"
    ATOM = "atom"


@dataclass
class QuantizationState:
    """State object holding quantization information.
    
    This is passed between prepare() and apply() to carry
    calibration data, scales, and other intermediate results.
    """
    # Original model info
    model_name: str
    original_dtype: torch.dtype
    original_size_mb: float
    
    # Quantization parameters
    method: str
    bit_width: int
    per_channel: bool = True
    symmetric: bool = True
    group_size: int | None = None
    
    # Calibration info
    calibration_samples: int = 0
    calibration_tokens: int = 0
    
    # Computed scales and zeros (layer_name -> tensor)
    scales: dict[str, torch.Tensor] = field(default_factory=dict)
    zeros: dict[str, torch.Tensor] = field(default_factory=dict)
    
    # Quantized weights storage (for packed formats)
    qweights: dict[str, torch.Tensor] = field(default_factory=dict)
    
    # Layer-wise statistics
    layer_stats: dict[str, dict[str, float]] = field(default_factory=dict)
    
    # Error metrics
    quantization_error: dict[str, float] = field(default_factory=dict)
    
    # Timing
    prepare_time_seconds: float = 0.0
    apply_time_seconds: float = 0.0
    
    # Backend-specific state (e.g., AutoGPTQ model, AutoAWQ model)
    backend_model: Any = None
    backend_config: dict[str, Any] = field(default_factory=dict)
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)


class QuantizerConfig(BaseModel):
    """Configuration for a quantizer."""
    
    method: str = Field(..., description="Quantization method name")
    bit_width: int = Field(4, ge=1, le=16, description="Bit width for quantization")
    per_channel: bool = Field(True, description="Use per-channel quantization")
    symmetric: bool = Field(True, description="Use symmetric quantization")
    group_size: int | None = Field(128, description="Group size for quantization")
    
    # Activation quantization
    activation_quant: bool = Field(False, description="Quantize activations")
    activation_bits: int | None = Field(None, description="Bit width for activations")
    
    # KV cache quantization
    kv_quant: bool = Field(False, description="Quantize KV cache")
    kv_bits: int | None = Field(None, description="Bit width for KV cache")
    
    # Calibration settings
    calib_dataset: str = Field("wikitext2", description="Calibration dataset")
    calib_size: int = Field(128, description="Number of calibration samples")
    calib_seq_length: int = Field(2048, description="Sequence length for calibration")
    
    # Multi-GPU
    num_gpus: int = Field(1, ge=1, description="Number of GPUs for distributed quantization via torchrun")
    
    # Method-specific settings
    method_config: dict[str, Any] = Field(default_factory=dict, description="Method-specific configuration")
    
    # Output settings
    save_path: str | None = Field(None, description="Path to save quantized model")
    
    class Config:
        extra = "allow"


class Quantizer(ABC):
    """Abstract base class for quantizers.
    
    All quantization methods must inherit from this class and implement
    ALL abstract methods. No default implementations are provided.
    
    Concrete implementations should use production-ready backends:
    - AWQ: AutoAWQ library
    - GPTQ: AutoGPTQ library
    - SmoothQuant: LLMC or custom implementation
    - etc.
    
    Example usage:
        quantizer = AWQQuantizer(config)
        state = quantizer.prepare(model, calib_data)
        quantized_model = quantizer.apply(model, state)
        meta = quantizer.metadata(state)
    """
    
    def __init__(self, config: QuantizerConfig):
        """Initialize the quantizer.
        
        Args:
            config: Quantizer configuration
        """
        self.config = config
        self._hooks: list[Callable] = []
        self._validate_dependencies()
    
    @abstractmethod
    def _validate_dependencies(self) -> None:
        """Validate that required dependencies are installed.
        
        Raises:
            ImportError: If required dependencies are not available
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this quantizer."""
        pass
    
    @property
    @abstractmethod
    def quantization_type(self) -> QuantizationType:
        """Return the type of quantization this quantizer performs."""
        pass
    
    @property
    @abstractmethod
    def supported_bit_widths(self) -> list[int]:
        """Return list of supported bit widths."""
        pass
    
    @property
    @abstractmethod
    def requires_calibration(self) -> bool:
        """Whether this method requires calibration data."""
        pass
    
    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the name of the backend library used."""
        pass
    
    @abstractmethod
    def prepare(
        self,
        model: "PreTrainedModel",
        calibration_data: torch.Tensor | list[torch.Tensor] | None = None,
    ) -> QuantizationState:
        """Prepare the model for quantization.
        
        This step typically involves:
        - Collecting activation statistics
        - Computing scales and zero points
        - Any method-specific preparation
        
        Args:
            model: The model to quantize
            calibration_data: Calibration data (input_ids tensors)
            
        Returns:
            QuantizationState containing preparation results
        """
        pass
    
    @abstractmethod
    def apply(
        self,
        model: "PreTrainedModel",
        state: QuantizationState,
    ) -> "PreTrainedModel":
        """Apply quantization to the model.
        
        Args:
            model: The model to quantize
            state: State from prepare()
            
        Returns:
            Quantized model
        """
        pass
    
    @abstractmethod
    def metadata(self, state: QuantizationState) -> dict[str, Any]:
        """Return metadata about the quantization.
        
        Args:
            state: State from prepare()/apply()
            
        Returns:
            Dictionary with quantization metadata
        """
        pass
    
    @abstractmethod
    def save(self, model: "PreTrainedModel", state: QuantizationState, path: str) -> None:
        """Save the quantized model.
        
        Args:
            model: Quantized model
            state: Quantization state
            path: Output path
        """
        pass
    
    @abstractmethod
    def load(self, path: str) -> "PreTrainedModel":
        """Load a quantized model.
        
        Args:
            path: Path to quantized model
            
        Returns:
            Loaded quantized model
        """
        pass
    
    def validate_config(self) -> tuple[bool, str]:
        """Validate the configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.config.bit_width not in self.supported_bit_widths:
            return False, f"Bit width {self.config.bit_width} not supported by {self.name}. Supported: {self.supported_bit_widths}"
        return True, ""
    
    def register_hook(self, hook: Callable) -> None:
        """Register a hook to be called during quantization.
        
        Args:
            hook: Callable that takes (layer_name, tensor) arguments
        """
        self._hooks.append(hook)
    
    def _call_hooks(self, layer_name: str, tensor: torch.Tensor) -> None:
        """Call all registered hooks.
        
        Args:
            layer_name: Name of the layer
            tensor: Tensor being processed
        """
        for hook in self._hooks:
            hook(layer_name, tensor)
    
    @staticmethod
    def estimate_model_size(model: "PreTrainedModel") -> float:
        """Estimate the model size in MB.
        
        Args:
            model: The model
            
        Returns:
            Estimated size in MB
        """
        total_bytes = sum(
            p.numel() * p.element_size() for p in model.parameters()
        )
        return total_bytes / (1024 * 1024)
    
    def estimate_quantized_size(self, model: "PreTrainedModel") -> float:
        """Estimate the quantized model size in MB.
        
        Args:
            model: The model
            
        Returns:
            Estimated quantized size in MB
        """
        total_params = sum(p.numel() for p in model.parameters())
        bits_per_param = self.config.bit_width
        
        # Add overhead for scales and zeros
        # For group_size=128, overhead is ~0.5% for scales + zeros
        if self.config.group_size:
            num_groups = total_params / self.config.group_size
            # Each group has a scale (fp16) and zero (int)
            overhead_bytes = num_groups * (2 + self.config.bit_width / 8)
        else:
            overhead_bytes = 0
        
        quantized_bytes = (total_params * bits_per_param / 8) + overhead_bytes
        return quantized_bytes / (1024 * 1024)


# Registry of available quantizers
QUANTIZER_REGISTRY: dict[str, type[Quantizer]] = {}


def get_quantizer(method: str, config: QuantizerConfig) -> Quantizer:
    """Get a quantizer instance by method name.

    Args:
        method: Quantization method name
        config: Quantizer configuration

    Returns:
        Quantizer instance

    Raises:
        ValueError: If method is not found or no quantizers registered (LightCompress not installed)
    """
    method_lower = method.lower()
    if method_lower not in QUANTIZER_REGISTRY:
        available = list(QUANTIZER_REGISTRY.keys())
        if not available:
            raise ValueError(
                f"No quantizers registered. Quantization requires LightCompress. "
                "Run: make llmc-clone. Then set PYTHONPATH=vendors/lightcompress when running. "
                "See https://github.com/ModelTC/LightCompress"
            )
        raise ValueError(
            f"Unknown quantization method: {method}. Available: {available}"
        )
    return QUANTIZER_REGISTRY[method_lower](config)


def register_quantizer(name: str, quantizer_class: type[Quantizer]) -> None:
    """Register a new quantizer.
    
    Args:
        name: Name to register under
        quantizer_class: Quantizer class
    """
    QUANTIZER_REGISTRY[name.lower()] = quantizer_class


def list_quantizers() -> list[str]:
    """List available quantizers.
    
    Returns:
        List of quantizer names
    """
    return list(QUANTIZER_REGISTRY.keys())


def check_quantizer_available(name: str) -> tuple[bool, str]:
    """Check if a quantizer is available and its dependencies are installed.

    Args:
        name: Quantizer name

    Returns:
        Tuple of (available, message)
    """
    if name.lower() not in QUANTIZER_REGISTRY:
        if not QUANTIZER_REGISTRY:
            return False, (
                f"Quantizer '{name}' is not registered. Quantization requires LightCompress. "
                "Run: make llmc-clone, set PYTHONPATH=vendors/lightcompress. "
                "See https://github.com/ModelTC/LightCompress"
            )
        return False, f"Quantizer '{name}' is not registered. Available: {list(QUANTIZER_REGISTRY.keys())}"
    
    try:
        # Try to instantiate with minimal config to check dependencies
        config = QuantizerConfig(method=name, bit_width=4)
        quantizer = QUANTIZER_REGISTRY[name.lower()](config)
        return True, f"Quantizer '{name}' is available (backend: {quantizer.backend_name})"
    except ImportError as e:
        return False, f"Quantizer '{name}' dependencies not installed: {e}"
    except Exception as e:
        return False, f"Quantizer '{name}' initialization failed: {e}"
