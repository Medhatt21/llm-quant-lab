"""Quantization method stacking compatibility matrix and validation.

This module defines which quantization methods can be combined (stacked)
and in what order they should be applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MethodCategory(str, Enum):
    """Categories of quantization methods."""
    WEIGHT_ONLY_PTQ = "weight_only_ptq"  # Post-training weight-only (GPTQ, AWQ, RTN)
    WEIGHT_ACTIVATION_PTQ = "weight_activation_ptq"  # W+A quantization (SmoothQuant)
    KV_CACHE = "kv_cache"  # KV cache quantization
    QAT = "qat"  # Quantization-aware training methods
    MIXED_PRECISION = "mixed_precision"  # Mixed precision methods
    SPARSITY = "sparsity"  # Pruning/sparsity methods


@dataclass
class MethodInfo:
    """Information about a quantization method."""
    name: str
    category: MethodCategory
    requires_training: bool = False
    requires_calibration: bool = True
    supported_bit_widths: list[int] | None = None
    default_bit_width: int = 4
    can_stack_after: list[str] | None = None  # Methods this can follow
    cannot_stack_with: list[str] | None = None  # Incompatible methods
    priority: int = 0  # Higher priority = applied first
    description: str = ""


# ============================================================================
# Method definitions
# ============================================================================

METHOD_INFO: dict[str, MethodInfo] = {
    # Weight-only PTQ methods
    "rtn": MethodInfo(
        name="rtn",
        category=MethodCategory.WEIGHT_ONLY_PTQ,
        requires_training=False,
        requires_calibration=False,
        supported_bit_widths=[2, 3, 4, 8],
        default_bit_width=4,
        priority=10,
        description="Round-to-Nearest: Simple baseline quantization",
    ),
    "gptq": MethodInfo(
        name="gptq",
        category=MethodCategory.WEIGHT_ONLY_PTQ,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[2, 3, 4, 8],
        default_bit_width=4,
        cannot_stack_with=["awq", "owq", "spqr"],  # Other weight-only methods
        priority=20,
        description="GPTQ: Uses Hessian information for optimal quantization",
    ),
    "awq": MethodInfo(
        name="awq",
        category=MethodCategory.WEIGHT_ONLY_PTQ,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[4],
        default_bit_width=4,
        cannot_stack_with=["gptq", "owq", "spqr"],
        priority=20,
        description="AWQ: Activation-aware weight quantization",
    ),
    "owq": MethodInfo(
        name="owq",
        category=MethodCategory.WEIGHT_ONLY_PTQ,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[3, 4],
        default_bit_width=4,
        cannot_stack_with=["gptq", "awq", "spqr"],
        priority=20,
        description="OWQ: Outlier-aware weight quantization",
    ),
    "spqr": MethodInfo(
        name="spqr",
        category=MethodCategory.WEIGHT_ONLY_PTQ,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[3, 4],
        default_bit_width=4,
        cannot_stack_with=["gptq", "awq", "owq"],
        priority=20,
        description="SpQR: Sparse-quantized representation",
    ),
    
    # Weight + Activation PTQ methods
    "smoothquant": MethodInfo(
        name="smoothquant",
        category=MethodCategory.WEIGHT_ACTIVATION_PTQ,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[8],
        default_bit_width=8,
        can_stack_after=["gptq", "awq"],  # Can be applied after weight-only
        priority=30,
        description="SmoothQuant: Smooths activation outliers for W8A8",
    ),
    "zeroquant": MethodInfo(
        name="zeroquant",
        category=MethodCategory.WEIGHT_ACTIVATION_PTQ,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[8],
        default_bit_width=8,
        can_stack_after=["gptq", "awq"],
        priority=30,
        description="ZeroQuant: Zero-shot quantization with knowledge distillation",
    ),
    "llm_int8": MethodInfo(
        name="llm_int8",
        category=MethodCategory.WEIGHT_ACTIVATION_PTQ,
        requires_training=False,
        requires_calibration=False,
        supported_bit_widths=[8],
        default_bit_width=8,
        cannot_stack_with=["smoothquant", "zeroquant"],
        priority=30,
        description="LLM.int8(): Mixed-precision with outlier handling",
    ),
    
    # KV Cache methods
    "kvquant": MethodInfo(
        name="kvquant",
        category=MethodCategory.KV_CACHE,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[2, 4, 8],
        default_bit_width=4,
        can_stack_after=["gptq", "awq", "smoothquant"],  # Applied after weight quant
        priority=40,
        description="KVQuant: Key-value cache quantization",
    ),
    "kivi": MethodInfo(
        name="kivi",
        category=MethodCategory.KV_CACHE,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[2, 4],
        default_bit_width=2,
        can_stack_after=["gptq", "awq", "smoothquant"],
        cannot_stack_with=["kvquant"],
        priority=40,
        description="KIVI: Tuning-free KV cache quantization",
    ),
    
    # Advanced methods
    "quarot": MethodInfo(
        name="quarot",
        category=MethodCategory.WEIGHT_ONLY_PTQ,
        requires_training=False,
        requires_calibration=True,
        supported_bit_widths=[4],
        default_bit_width=4,
        cannot_stack_with=["gptq", "awq"],  # Standalone method
        priority=20,
        description="QuaRot: Outlier-free quantization via rotation",
    ),
    "omniquant": MethodInfo(
        name="omniquant",
        category=MethodCategory.WEIGHT_ACTIVATION_PTQ,
        requires_training=False,  # Uses block-wise optimization, not full training
        requires_calibration=True,
        supported_bit_widths=[2, 3, 4],
        default_bit_width=4,
        cannot_stack_with=["smoothquant"],
        priority=25,
        description="OmniQuant: Omnidirectionally calibrated quantization",
    ),
    
    # QAT methods (incompatible with PTQ stacking)
    "bitnet": MethodInfo(
        name="bitnet",
        category=MethodCategory.QAT,
        requires_training=True,
        requires_calibration=False,
        supported_bit_widths=[1],
        default_bit_width=1,
        cannot_stack_with=["gptq", "awq", "smoothquant", "kvquant"],  # Standalone
        priority=0,
        description="BitNet: 1-bit LLM (requires training from scratch)",
    ),
}


# ============================================================================
# Compatibility matrix
# ============================================================================

# Define explicit compatibility rules
# Format: (method1, method2) -> (compatible, reason)
COMPATIBILITY_RULES: dict[tuple[str, str], tuple[bool, str]] = {
    # Weight-only methods are mutually exclusive
    ("gptq", "awq"): (False, "Both are weight-only PTQ methods; use one or the other"),
    ("gptq", "owq"): (False, "Both are weight-only PTQ methods; use one or the other"),
    ("gptq", "spqr"): (False, "Both are weight-only PTQ methods; use one or the other"),
    ("awq", "owq"): (False, "Both are weight-only PTQ methods; use one or the other"),
    ("awq", "spqr"): (False, "Both are weight-only PTQ methods; use one or the other"),
    ("owq", "spqr"): (False, "Both are weight-only PTQ methods; use one or the other"),
    
    # Weight-only + activation quant is OK
    ("gptq", "smoothquant"): (True, "GPTQ (weights) + SmoothQuant (activations) is valid"),
    ("awq", "smoothquant"): (True, "AWQ (weights) + SmoothQuant (activations) is valid"),
    ("gptq", "zeroquant"): (True, "GPTQ + ZeroQuant activation quantization is valid"),
    ("awq", "zeroquant"): (True, "AWQ + ZeroQuant activation quantization is valid"),
    
    # Activation methods are mutually exclusive
    ("smoothquant", "zeroquant"): (False, "Both handle activation quantization; use one"),
    ("smoothquant", "llm_int8"): (False, "Both handle activation quantization; use one"),
    ("zeroquant", "llm_int8"): (False, "Both handle activation quantization; use one"),
    
    # KV cache can stack with weight/activation quant
    ("gptq", "kvquant"): (True, "Weight quant + KV cache quant is valid"),
    ("awq", "kvquant"): (True, "Weight quant + KV cache quant is valid"),
    ("smoothquant", "kvquant"): (True, "W+A quant + KV cache quant is valid"),
    ("gptq", "kivi"): (True, "Weight quant + KIVI is valid"),
    ("awq", "kivi"): (True, "Weight quant + KIVI is valid"),
    
    # KV cache methods are mutually exclusive
    ("kvquant", "kivi"): (False, "Both are KV cache methods; use one or the other"),
    
    # QAT methods are standalone
    ("bitnet", "gptq"): (False, "BitNet requires training from scratch; incompatible with PTQ"),
    ("bitnet", "awq"): (False, "BitNet requires training from scratch; incompatible with PTQ"),
    ("bitnet", "smoothquant"): (False, "BitNet requires training from scratch; incompatible with PTQ"),
}


# Compatibility matrix for quick lookup
# True = compatible, False = incompatible, None = check rules
COMPATIBILITY_MATRIX: dict[str, dict[str, bool | None]] = {}

# Initialize matrix
for method in METHOD_INFO:
    COMPATIBILITY_MATRIX[method] = {}
    for other in METHOD_INFO:
        if method == other:
            COMPATIBILITY_MATRIX[method][other] = False  # Can't stack same method
        else:
            # Check explicit rules
            key = (method, other) if method < other else (other, method)
            if key in COMPATIBILITY_RULES:
                COMPATIBILITY_MATRIX[method][other] = COMPATIBILITY_RULES[key][0]
            else:
                COMPATIBILITY_MATRIX[method][other] = None  # Need to check categories


# ============================================================================
# Validation functions
# ============================================================================


def is_stack_valid(methods: list[str]) -> tuple[bool, str]:
    """Check if a stack of methods is valid.
    
    Args:
        methods: List of method names in desired order
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if not methods:
        return True, "Empty stack is valid"
    
    if len(methods) == 1:
        method = methods[0].lower()
        if method not in METHOD_INFO:
            return False, f"Unknown method: {method}"
        return True, "Single method is always valid"
    
    # Normalize method names
    methods = [m.lower() for m in methods]
    
    # Check all methods exist
    for method in methods:
        if method not in METHOD_INFO:
            return False, f"Unknown method: {method}"
    
    # Check for duplicates
    if len(methods) != len(set(methods)):
        return False, "Duplicate methods in stack"
    
    # Check pairwise compatibility
    for i, method1 in enumerate(methods):
        for method2 in methods[i+1:]:
            # Check explicit rules first
            key = (method1, method2) if method1 < method2 else (method2, method1)
            
            if key in COMPATIBILITY_RULES:
                compatible, reason = COMPATIBILITY_RULES[key]
                if not compatible:
                    return False, reason
            else:
                # Check category-based rules
                info1 = METHOD_INFO[method1]
                info2 = METHOD_INFO[method2]
                
                # QAT methods are standalone
                if info1.category == MethodCategory.QAT or info2.category == MethodCategory.QAT:
                    return False, f"QAT method ({method1 if info1.category == MethodCategory.QAT else method2}) cannot be stacked with PTQ methods"
                
                # Same category weight-only methods are incompatible
                if (info1.category == MethodCategory.WEIGHT_ONLY_PTQ and 
                    info2.category == MethodCategory.WEIGHT_ONLY_PTQ):
                    return False, f"Cannot stack multiple weight-only methods: {method1}, {method2}"
                
                # Check cannot_stack_with lists
                if info1.cannot_stack_with and method2 in info1.cannot_stack_with:
                    return False, f"{method1} cannot be stacked with {method2}"
                if info2.cannot_stack_with and method1 in info2.cannot_stack_with:
                    return False, f"{method2} cannot be stacked with {method1}"
    
    return True, "Stack is valid"


def normalize_stack_order(methods: list[str]) -> list[str]:
    """Normalize the order of methods in a stack.
    
    Methods are ordered by priority (higher priority first):
    1. Weight-only PTQ (GPTQ, AWQ, etc.)
    2. Weight+Activation PTQ (SmoothQuant, etc.)
    3. KV Cache quantization
    
    Args:
        methods: List of method names
        
    Returns:
        List of method names in normalized order
    """
    if not methods:
        return []
    
    # Normalize names
    methods = [m.lower() for m in methods]
    
    # Filter valid methods
    valid_methods = [m for m in methods if m in METHOD_INFO]
    
    # Sort by priority (higher priority first)
    sorted_methods = sorted(
        valid_methods,
        key=lambda m: METHOD_INFO[m].priority,
        reverse=False  # Lower priority number = applied first
    )
    
    return sorted_methods


def get_method_info(method: str) -> MethodInfo | None:
    """Get information about a method.
    
    Args:
        method: Method name
        
    Returns:
        MethodInfo or None if not found
    """
    return METHOD_INFO.get(method.lower())


def list_compatible_methods(method: str) -> list[str]:
    """List methods compatible with the given method.
    
    Args:
        method: Method name
        
    Returns:
        List of compatible method names
    """
    method = method.lower()
    if method not in METHOD_INFO:
        return []
    
    compatible = []
    for other in METHOD_INFO:
        if other == method:
            continue
        
        valid, _ = is_stack_valid([method, other])
        if valid:
            compatible.append(other)
    
    return compatible


def suggest_stack(
    target_bits: int = 4,
    quantize_activations: bool = False,
    quantize_kv: bool = False,
    prefer_accuracy: bool = True,
) -> list[str]:
    """Suggest a quantization stack based on requirements.
    
    Args:
        target_bits: Target bit width for weights
        quantize_activations: Whether to quantize activations
        quantize_kv: Whether to quantize KV cache
        prefer_accuracy: Prefer accuracy over speed
        
    Returns:
        Suggested list of methods
    """
    stack = []
    
    # Choose weight quantization method
    if target_bits <= 4:
        if prefer_accuracy:
            stack.append("gptq")  # GPTQ generally has better accuracy
        else:
            stack.append("awq")  # AWQ is faster
    else:
        stack.append("rtn")  # Simple RTN for higher bit widths
    
    # Add activation quantization if requested
    if quantize_activations:
        stack.append("smoothquant")
    
    # Add KV cache quantization if requested
    if quantize_kv:
        stack.append("kvquant")
    
    return normalize_stack_order(stack)


def validate_config_for_method(method: str, config: dict[str, Any]) -> tuple[bool, str]:
    """Validate a configuration for a specific method.
    
    Args:
        method: Method name
        config: Configuration dictionary
        
    Returns:
        Tuple of (is_valid, reason)
    """
    method = method.lower()
    if method not in METHOD_INFO:
        return False, f"Unknown method: {method}"
    
    info = METHOD_INFO[method]
    
    # Check bit width
    bit_width = config.get("bit_width", info.default_bit_width)
    if info.supported_bit_widths and bit_width not in info.supported_bit_widths:
        return False, f"{method} does not support {bit_width}-bit quantization. Supported: {info.supported_bit_widths}"
    
    # Check if calibration data is needed
    if info.requires_calibration and not config.get("calib_dataset"):
        return False, f"{method} requires calibration data"
    
    # Check if training is needed
    if info.requires_training:
        return False, f"{method} requires training and cannot be used for post-training quantization"
    
    return True, "Configuration is valid"


def get_stack_summary(methods: list[str]) -> dict[str, Any]:
    """Get a summary of a quantization stack.
    
    Args:
        methods: List of method names
        
    Returns:
        Summary dictionary
    """
    valid, reason = is_stack_valid(methods)
    
    if not valid:
        return {
            "valid": False,
            "reason": reason,
            "methods": methods,
        }
    
    normalized = normalize_stack_order(methods)
    
    # Collect info about each method
    method_details = []
    for method in normalized:
        info = METHOD_INFO.get(method.lower())
        if info:
            method_details.append({
                "name": info.name,
                "category": info.category.value,
                "requires_calibration": info.requires_calibration,
                "default_bit_width": info.default_bit_width,
                "description": info.description,
            })
    
    # Determine overall characteristics
    has_weight_quant = any(
        METHOD_INFO[m].category in [MethodCategory.WEIGHT_ONLY_PTQ, MethodCategory.WEIGHT_ACTIVATION_PTQ]
        for m in normalized if m in METHOD_INFO
    )
    has_activation_quant = any(
        METHOD_INFO[m].category == MethodCategory.WEIGHT_ACTIVATION_PTQ
        for m in normalized if m in METHOD_INFO
    )
    has_kv_quant = any(
        METHOD_INFO[m].category == MethodCategory.KV_CACHE
        for m in normalized if m in METHOD_INFO
    )
    
    return {
        "valid": True,
        "reason": reason,
        "methods": methods,
        "normalized_order": normalized,
        "method_details": method_details,
        "has_weight_quant": has_weight_quant,
        "has_activation_quant": has_activation_quant,
        "has_kv_quant": has_kv_quant,
        "requires_calibration": any(
            METHOD_INFO[m].requires_calibration
            for m in normalized if m in METHOD_INFO
        ),
    }
