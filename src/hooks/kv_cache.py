"""KV cache inspection hooks for quantization analysis.

This module provides hooks to analyze key-value cache behavior,
including size estimation, compression ratios, and distribution metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import torch
from torch import nn


@dataclass
class KVCacheStats:
    """Statistics for KV cache at a layer."""
    layer_name: str
    layer_index: int
    
    # Shape info
    num_heads: int = 0
    head_dim: int = 0
    max_seq_length: int = 0
    
    # Key statistics
    key_mean: float = 0.0
    key_std: float = 0.0
    key_min: float = 0.0
    key_max: float = 0.0
    key_sparsity: float = 0.0
    
    # Value statistics
    value_mean: float = 0.0
    value_std: float = 0.0
    value_min: float = 0.0
    value_max: float = 0.0
    value_sparsity: float = 0.0
    
    # Size metrics (in bytes)
    fp16_size: int = 0
    estimated_quantized_size: int = 0
    compression_ratio: float = 1.0
    
    # Distribution metrics
    key_kurtosis: float = 0.0
    value_kurtosis: float = 0.0
    key_outlier_ratio: float = 0.0
    value_outlier_ratio: float = 0.0
    
    # Per-head variance (to identify important heads)
    head_importance: list[float] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "layer_name": self.layer_name,
            "layer_index": self.layer_index,
            "num_heads": self.num_heads,
            "head_dim": self.head_dim,
            "max_seq_length": self.max_seq_length,
            "key_mean": self.key_mean,
            "key_std": self.key_std,
            "key_min": self.key_min,
            "key_max": self.key_max,
            "value_mean": self.value_mean,
            "value_std": self.value_std,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "fp16_size": self.fp16_size,
            "estimated_quantized_size": self.estimated_quantized_size,
            "compression_ratio": self.compression_ratio,
            "key_kurtosis": self.key_kurtosis,
            "value_kurtosis": self.value_kurtosis,
            "key_outlier_ratio": self.key_outlier_ratio,
            "value_outlier_ratio": self.value_outlier_ratio,
        }


class KVCacheStatsHook:
    """Hook for collecting KV cache statistics.
    
    This hook monitors attention layers to capture key and value tensors
    and compute statistics relevant to KV cache quantization.
    
    Usage:
        hook = KVCacheStatsHook()
        handles = hook.register(model)
        
        # Run inference
        for batch in data:
            model(batch)
        
        hook.remove_hooks(handles)
        stats = hook.get_all_stats()
    """
    
    def __init__(
        self,
        target_bit_width: int = 4,
        outlier_sigma: float = 3.0,
        max_samples: int = 100,
    ):
        """Initialize the KV cache stats hook.
        
        Args:
            target_bit_width: Target bit width for compression estimation
            outlier_sigma: Sigma threshold for outlier detection
            max_samples: Maximum samples to collect
        """
        self.target_bit_width = target_bit_width
        self.outlier_sigma = outlier_sigma
        self.max_samples = max_samples
        
        self._running_stats: dict[str, dict[str, Any]] = {}
        self._final_stats: dict[str, KVCacheStats] = {}
        self._layer_counter = 0
    
    def _create_hook(self, name: str, layer_idx: int) -> Callable:
        """Create a forward hook for an attention layer."""
        
        def hook(module: nn.Module, input: tuple, output: Any) -> None:
            # Try to extract key and value tensors
            # This depends on the model architecture
            
            key = None
            value = None
            
            # Check if module has past_key_value or similar attributes
            if hasattr(module, "key") and module.key is not None:
                key = module.key
            if hasattr(module, "value") and module.value is not None:
                value = module.value
            
            # Try to get from output if it's a tuple with KV cache
            if isinstance(output, tuple) and len(output) >= 2:
                # Common pattern: (hidden_states, present_key_value, ...)
                if isinstance(output[1], tuple) and len(output[1]) == 2:
                    key, value = output[1]
            
            # If we couldn't find KV, try input
            if key is None and isinstance(input, tuple):
                for inp in input:
                    if isinstance(inp, tuple) and len(inp) == 2:
                        if isinstance(inp[0], torch.Tensor) and isinstance(inp[1], torch.Tensor):
                            key, value = inp
                            break
            
            if key is None or value is None:
                return
            
            with torch.no_grad():
                # Initialize running stats
                if name not in self._running_stats:
                    self._running_stats[name] = {
                        "layer_idx": layer_idx,
                        "key_samples": [],
                        "value_samples": [],
                        "count": 0,
                    }
                
                stats = self._running_stats[name]
                
                if stats["count"] >= self.max_samples:
                    return
                
                # Store samples (limited)
                if len(stats["key_samples"]) < 10:
                    stats["key_samples"].append(key.detach().cpu())
                    stats["value_samples"].append(value.detach().cpu())
                
                stats["count"] += 1
        
        return hook
    
    def register(self, model: nn.Module) -> list[torch.utils.hooks.RemovableHandle]:
        """Register hooks on attention layers.
        
        Args:
            model: PyTorch model
            
        Returns:
            List of hook handles
        """
        handles = []
        self._layer_counter = 0
        
        for name, module in model.named_modules():
            # Look for attention-related modules
            module_name = type(module).__name__.lower()
            if any(attn in module_name for attn in ["attention", "attn", "selfatt"]):
                handle = module.register_forward_hook(
                    self._create_hook(name, self._layer_counter)
                )
                handles.append(handle)
                self._layer_counter += 1
        
        return handles
    
    def remove_hooks(self, handles: list[torch.utils.hooks.RemovableHandle]) -> None:
        """Remove registered hooks."""
        for handle in handles:
            handle.remove()
    
    def finalize_stats(self) -> dict[str, KVCacheStats]:
        """Finalize and compute all statistics."""
        self._final_stats = {}
        
        for name, running in self._running_stats.items():
            if not running["key_samples"]:
                continue
            
            # Concatenate samples
            keys = torch.cat(running["key_samples"], dim=0)
            values = torch.cat(running["value_samples"], dim=0)
            
            # Determine shape (batch, heads, seq, dim) or similar
            if keys.dim() == 4:
                num_heads = keys.shape[1]
                head_dim = keys.shape[-1]
                max_seq = keys.shape[2]
            elif keys.dim() == 3:
                num_heads = 1
                head_dim = keys.shape[-1]
                max_seq = keys.shape[1]
            else:
                num_heads = 1
                head_dim = keys.shape[-1] if keys.dim() >= 1 else 1
                max_seq = 1
            
            # Flatten for statistics
            keys_flat = keys.flatten().float()
            values_flat = values.flatten().float()
            
            # Basic statistics
            key_mean = keys_flat.mean().item()
            key_std = keys_flat.std().item()
            value_mean = values_flat.mean().item()
            value_std = values_flat.std().item()
            
            # Kurtosis
            if key_std > 1e-8:
                key_centered = keys_flat - key_mean
                key_kurtosis = (key_centered ** 4).mean().item() / (key_std ** 4) - 3
            else:
                key_kurtosis = 0.0
            
            if value_std > 1e-8:
                value_centered = values_flat - value_mean
                value_kurtosis = (value_centered ** 4).mean().item() / (value_std ** 4) - 3
            else:
                value_kurtosis = 0.0
            
            # Outlier ratios
            key_outlier_ratio = ((keys_flat - key_mean).abs() > self.outlier_sigma * key_std).float().mean().item()
            value_outlier_ratio = ((values_flat - value_mean).abs() > self.outlier_sigma * value_std).float().mean().item()
            
            # Sparsity
            key_sparsity = (keys_flat.abs() < 1e-6).float().mean().item()
            value_sparsity = (values_flat.abs() < 1e-6).float().mean().item()
            
            # Size estimation
            total_elements = keys.numel() + values.numel()
            fp16_size = total_elements * 2  # 2 bytes per FP16
            quantized_size = int(total_elements * self.target_bit_width / 8)
            compression_ratio = fp16_size / max(quantized_size, 1)
            
            # Per-head importance (variance)
            head_importance = []
            if keys.dim() >= 3:
                for h in range(num_heads):
                    if keys.dim() == 4:
                        head_keys = keys[:, h, :, :]
                    else:
                        head_keys = keys
                    head_importance.append(head_keys.var().item())
            
            stats = KVCacheStats(
                layer_name=name,
                layer_index=running["layer_idx"],
                num_heads=num_heads,
                head_dim=head_dim,
                max_seq_length=max_seq,
                key_mean=key_mean,
                key_std=key_std,
                key_min=keys_flat.min().item(),
                key_max=keys_flat.max().item(),
                key_sparsity=key_sparsity,
                value_mean=value_mean,
                value_std=value_std,
                value_min=values_flat.min().item(),
                value_max=values_flat.max().item(),
                value_sparsity=value_sparsity,
                fp16_size=fp16_size,
                estimated_quantized_size=quantized_size,
                compression_ratio=compression_ratio,
                key_kurtosis=key_kurtosis,
                value_kurtosis=value_kurtosis,
                key_outlier_ratio=key_outlier_ratio,
                value_outlier_ratio=value_outlier_ratio,
                head_importance=head_importance,
            )
            
            self._final_stats[name] = stats
        
        return self._final_stats
    
    def get_all_stats(self) -> dict[str, KVCacheStats]:
        """Get all finalized statistics."""
        if not self._final_stats:
            self.finalize_stats()
        return self._final_stats
    
    def get_total_cache_size(self) -> dict[str, int]:
        """Get total KV cache size estimates.
        
        Returns:
            Dictionary with fp16_size, quantized_size, and compression_ratio
        """
        if not self._final_stats:
            self.finalize_stats()
        
        total_fp16 = sum(s.fp16_size for s in self._final_stats.values())
        total_quantized = sum(s.estimated_quantized_size for s in self._final_stats.values())
        
        return {
            "fp16_size_bytes": total_fp16,
            "fp16_size_mb": total_fp16 / (1024 * 1024),
            "quantized_size_bytes": total_quantized,
            "quantized_size_mb": total_quantized / (1024 * 1024),
            "compression_ratio": total_fp16 / max(total_quantized, 1),
            "target_bit_width": self.target_bit_width,
        }
    
    def get_quantization_difficulty(self) -> dict[str, float]:
        """Estimate quantization difficulty for each layer.
        
        Higher values indicate more difficult quantization.
        
        Returns:
            Dictionary mapping layer names to difficulty scores
        """
        if not self._final_stats:
            self.finalize_stats()
        
        difficulties = {}
        for name, stats in self._final_stats.items():
            # Difficulty based on:
            # - High kurtosis (heavy tails)
            # - High outlier ratio
            # - Large dynamic range
            difficulty = (
                abs(stats.key_kurtosis) * 0.3 +
                abs(stats.value_kurtosis) * 0.3 +
                stats.key_outlier_ratio * 100 +
                stats.value_outlier_ratio * 100
            )
            difficulties[name] = difficulty
        
        return difficulties
    
    def to_db_records(
        self,
        experiment_id: int,
        quant_config_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Convert statistics to database records."""
        if not self._final_stats:
            self.finalize_stats()
        
        records = []
        
        for name, stats in self._final_stats.items():
            metrics = [
                ("kv_key_mean", stats.key_mean),
                ("kv_key_std", stats.key_std),
                ("kv_key_min", stats.key_min),
                ("kv_key_max", stats.key_max),
                ("kv_key_sparsity", stats.key_sparsity),
                ("kv_value_mean", stats.value_mean),
                ("kv_value_std", stats.value_std),
                ("kv_value_min", stats.value_min),
                ("kv_value_max", stats.value_max),
                ("kv_value_sparsity", stats.value_sparsity),
                ("kv_compression_ratio", stats.compression_ratio),
                ("kv_key_kurtosis", stats.key_kurtosis),
                ("kv_value_kurtosis", stats.value_kurtosis),
                ("kv_key_outlier_ratio", stats.key_outlier_ratio),
                ("kv_value_outlier_ratio", stats.value_outlier_ratio),
            ]
            
            for metric_name, value in metrics:
                records.append({
                    "experiment_id": experiment_id,
                    "quant_config_id": quant_config_id,
                    "layer_index": stats.layer_index,
                    "layer_name": stats.layer_name,
                    "layer_type": "attention",
                    "stat_name": metric_name,
                    "stat_type": "kv_cache",
                    "value": value,
                })
        
        return records
    
    def reset(self) -> None:
        """Reset all collected statistics."""
        self._running_stats = {}
        self._final_stats = {}
        self._layer_counter = 0
