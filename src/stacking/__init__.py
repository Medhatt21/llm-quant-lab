"""Quantization method stacking and compatibility."""

from .compatibility import (
    COMPATIBILITY_MATRIX,
    get_stack_summary,
    is_stack_valid,
    normalize_stack_order,
)

__all__ = ["COMPATIBILITY_MATRIX", "get_stack_summary", "is_stack_valid", "normalize_stack_order"]
