"""Weight inspection hooks for quantization analysis.

This module provides hooks to collect weight statistics before and after
quantization, including norms, distributions, and sparsity metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import torch
from torch import nn


@dataclass
class WeightStats:
    """Statistics for a single weight tensor."""
    layer_name: str
    layer_type: str
    shape: tuple[int, ...]
    dtype: str
    
    # Basic statistics
    norm_l1: float = 0.0
    norm_l2: float = 0.0
    norm_inf: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    
    # Distribution metrics
    median: float = 0.0
    q25: float = 0.0  # 25th percentile
    q75: float = 0.0  # 75th percentile
    skewness: float = 0.0
    kurtosis: float = 0.0
    
    # Sparsity metrics
    num_zeros: int = 0
    sparsity: float = 0.0  # Fraction of zeros
    near_zero_ratio: float = 0.0  # Fraction of values < threshold
    
    # Histogram data (optional)
    histogram_bins: list[float] = field(default_factory=list)
    histogram_counts: list[int] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "layer_name": self.layer_name,
            "layer_type": self.layer_type,
            "shape": self.shape,
            "dtype": self.dtype,
            "norm_l1": self.norm_l1,
            "norm_l2": self.norm_l2,
            "norm_inf": self.norm_inf,
            "mean": self.mean,
            "std": self.std,
            "min_val": self.min_val,
            "max_val": self.max_val,
            "median": self.median,
            "q25": self.q25,
            "q75": self.q75,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "num_zeros": self.num_zeros,
            "sparsity": self.sparsity,
            "near_zero_ratio": self.near_zero_ratio,
        }


class WeightStatsHook:
    """Hook for collecting weight statistics.
    
    Usage:
        hook = WeightStatsHook()
        hook.collect_stats(model)
        stats = hook.get_all_stats()
    """
    
    def __init__(
        self,
        near_zero_threshold: float = 1e-6,
        compute_histogram: bool = False,
        histogram_bins: int = 100,
        layer_filter: Callable[[str, nn.Module], bool] | None = None,
    ):
        """Initialize the weight stats hook.
        
        Args:
            near_zero_threshold: Threshold for counting near-zero values
            compute_histogram: Whether to compute histograms
            histogram_bins: Number of histogram bins
            layer_filter: Optional filter function (name, module) -> bool
        """
        self.near_zero_threshold = near_zero_threshold
        self.compute_histogram = compute_histogram
        self.histogram_bins = histogram_bins
        self.layer_filter = layer_filter or self._default_filter
        
        self._stats: dict[str, WeightStats] = {}
        self._pre_quant_stats: dict[str, WeightStats] = {}
        self._post_quant_stats: dict[str, WeightStats] = {}
    
    @staticmethod
    def _default_filter(name: str, module: nn.Module) -> bool:
        """Default filter: include Linear and Conv layers."""
        return isinstance(module, (nn.Linear, nn.Conv1d, nn.Conv2d))
    
    def _compute_stats(
        self,
        name: str,
        module: nn.Module,
        weight: torch.Tensor,
    ) -> WeightStats:
        """Compute statistics for a weight tensor."""
        weight_flat = weight.detach().float().flatten()
        
        # Basic statistics
        stats = WeightStats(
            layer_name=name,
            layer_type=type(module).__name__,
            shape=tuple(weight.shape),
            dtype=str(weight.dtype),
            norm_l1=weight_flat.abs().sum().item(),
            norm_l2=weight_flat.norm(p=2).item(),
            norm_inf=weight_flat.abs().max().item(),
            mean=weight_flat.mean().item(),
            std=weight_flat.std().item(),
            min_val=weight_flat.min().item(),
            max_val=weight_flat.max().item(),
        )
        
        # Percentiles
        sorted_weights = weight_flat.sort()[0]
        n = len(sorted_weights)
        stats.median = sorted_weights[n // 2].item()
        stats.q25 = sorted_weights[n // 4].item()
        stats.q75 = sorted_weights[3 * n // 4].item()
        
        # Skewness and kurtosis
        if stats.std > 1e-8:
            centered = weight_flat - stats.mean
            stats.skewness = (centered ** 3).mean().item() / (stats.std ** 3)
            stats.kurtosis = (centered ** 4).mean().item() / (stats.std ** 4) - 3
        
        # Sparsity metrics
        stats.num_zeros = (weight_flat == 0).sum().item()
        stats.sparsity = stats.num_zeros / weight_flat.numel()
        stats.near_zero_ratio = (weight_flat.abs() < self.near_zero_threshold).float().mean().item()
        
        # Histogram
        if self.compute_histogram:
            hist = torch.histogram(weight_flat.cpu(), bins=self.histogram_bins)
            stats.histogram_bins = hist.bin_edges.tolist()
            stats.histogram_counts = hist.hist.int().tolist()
        
        return stats
    
    def collect_stats(
        self,
        model: nn.Module,
        prefix: str = "",
    ) -> dict[str, WeightStats]:
        """Collect weight statistics for all layers in the model.
        
        Args:
            model: PyTorch model
            prefix: Prefix for layer names
            
        Returns:
            Dictionary mapping layer names to WeightStats
        """
        self._stats = {}
        
        for name, module in model.named_modules():
            full_name = f"{prefix}.{name}" if prefix else name
            
            if not self.layer_filter(name, module):
                continue
            
            # Get weight tensor
            if hasattr(module, "weight") and module.weight is not None:
                weight = module.weight.data
                stats = self._compute_stats(full_name, module, weight)
                self._stats[full_name] = stats
        
        return self._stats
    
    def collect_pre_quant_stats(self, model: nn.Module) -> dict[str, WeightStats]:
        """Collect pre-quantization statistics.
        
        Args:
            model: Model before quantization
            
        Returns:
            Pre-quantization statistics
        """
        self._pre_quant_stats = self.collect_stats(model, prefix="pre_quant")
        return self._pre_quant_stats
    
    def collect_post_quant_stats(self, model: nn.Module) -> dict[str, WeightStats]:
        """Collect post-quantization statistics.
        
        Args:
            model: Model after quantization
            
        Returns:
            Post-quantization statistics
        """
        self._post_quant_stats = self.collect_stats(model, prefix="post_quant")
        return self._post_quant_stats
    
    def get_all_stats(self) -> dict[str, WeightStats]:
        """Get all collected statistics."""
        return self._stats
    
    def get_pre_quant_stats(self) -> dict[str, WeightStats]:
        """Get pre-quantization statistics."""
        return self._pre_quant_stats
    
    def get_post_quant_stats(self) -> dict[str, WeightStats]:
        """Get post-quantization statistics."""
        return self._post_quant_stats
    
    def compute_quantization_error(self) -> dict[str, dict[str, float]]:
        """Compute quantization error metrics.
        
        Returns:
            Dictionary mapping layer names to error metrics
        """
        errors = {}
        
        for name in self._pre_quant_stats:
            # Find corresponding post-quant stats
            post_name = name.replace("pre_quant", "post_quant")
            if post_name not in self._post_quant_stats:
                continue
            
            pre = self._pre_quant_stats[name]
            post = self._post_quant_stats[post_name]
            
            # Compute error metrics
            base_name = name.replace("pre_quant.", "")
            errors[base_name] = {
                "norm_l2_change": abs(post.norm_l2 - pre.norm_l2),
                "norm_l2_relative_change": abs(post.norm_l2 - pre.norm_l2) / max(pre.norm_l2, 1e-8),
                "mean_shift": abs(post.mean - pre.mean),
                "std_change": abs(post.std - pre.std),
                "sparsity_change": post.sparsity - pre.sparsity,
                "range_change": (post.max_val - post.min_val) - (pre.max_val - pre.min_val),
            }
        
        return errors
    
    def get_layer_summary(self) -> list[dict[str, Any]]:
        """Get a summary of all layers.
        
        Returns:
            List of layer summaries
        """
        summaries = []
        
        for name, stats in self._stats.items():
            summaries.append({
                "name": stats.layer_name,
                "type": stats.layer_type,
                "shape": stats.shape,
                "params": sum(stats.shape) if stats.shape else 0,
                "norm_l2": stats.norm_l2,
                "mean": stats.mean,
                "std": stats.std,
                "sparsity": stats.sparsity,
            })
        
        return summaries
    
    def to_db_records(
        self,
        experiment_id: int,
        quant_config_id: int | None = None,
        stat_type: str = "weight",
    ) -> list[dict[str, Any]]:
        """Convert statistics to database records.
        
        Args:
            experiment_id: Experiment ID
            quant_config_id: Optional quant config ID
            stat_type: Type of statistics ('weight', 'pre_quant', 'post_quant')
            
        Returns:
            List of records suitable for layer_metrics table
        """
        records = []
        
        stats_dict = self._stats
        if stat_type == "pre_quant":
            stats_dict = self._pre_quant_stats
        elif stat_type == "post_quant":
            stats_dict = self._post_quant_stats
        
        for idx, (name, stats) in enumerate(stats_dict.items()):
            # Create records for each metric
            metrics = [
                ("norm_l1", stats.norm_l1),
                ("norm_l2", stats.norm_l2),
                ("norm_inf", stats.norm_inf),
                ("mean", stats.mean),
                ("std", stats.std),
                ("min", stats.min_val),
                ("max", stats.max_val),
                ("median", stats.median),
                ("sparsity", stats.sparsity),
                ("near_zero_ratio", stats.near_zero_ratio),
                ("skewness", stats.skewness),
                ("kurtosis", stats.kurtosis),
            ]
            
            for metric_name, value in metrics:
                records.append({
                    "experiment_id": experiment_id,
                    "quant_config_id": quant_config_id,
                    "layer_index": idx,
                    "layer_name": stats.layer_name,
                    "layer_type": stats.layer_type,
                    "stat_name": metric_name,
                    "stat_type": stat_type,
                    "value": value,
                    "histogram_bins": stats.histogram_bins if metric_name == "distribution" else None,
                    "histogram_counts": stats.histogram_counts if metric_name == "distribution" else None,
                })
        
        return records


def compute_weight_sensitivity(
    model: nn.Module,
    perturbation_scale: float = 0.01,
) -> dict[str, float]:
    """Compute weight sensitivity for each layer.
    
    Sensitivity is measured by the change in output norm when
    weights are perturbed.
    
    Args:
        model: PyTorch model
        perturbation_scale: Scale of random perturbation
        
    Returns:
        Dictionary mapping layer names to sensitivity scores
    """
    sensitivities = {}
    
    for name, module in model.named_modules():
        if not isinstance(module, (nn.Linear, nn.Conv1d, nn.Conv2d)):
            continue
        
        if not hasattr(module, "weight") or module.weight is None:
            continue
        
        weight = module.weight.data
        
        # Compute sensitivity as ratio of weight norm to perturbation effect
        weight_norm = weight.norm().item()
        perturbation_norm = perturbation_scale * weight_norm
        
        # Simple sensitivity estimate based on weight statistics
        # Higher variance = more sensitive to quantization
        sensitivity = weight.std().item() / max(weight.abs().mean().item(), 1e-8)
        sensitivities[name] = sensitivity
    
    return sensitivities
