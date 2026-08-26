"""Activation inspection hooks for quantization analysis.

This module provides hooks to collect activation statistics during
calibration and evaluation, including outlier detection for methods
like SmoothQuant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import torch
from torch import nn


@dataclass
class ActivationStats:
    """Statistics for activations at a layer."""
    layer_name: str
    layer_type: str
    
    # Shape info
    num_samples: int = 0
    feature_dim: int = 0
    
    # Basic statistics (per-channel)
    mean: list[float] = field(default_factory=list)
    std: list[float] = field(default_factory=list)
    min_val: list[float] = field(default_factory=list)
    max_val: list[float] = field(default_factory=list)
    
    # Aggregated statistics
    global_mean: float = 0.0
    global_std: float = 0.0
    global_min: float = 0.0
    global_max: float = 0.0
    
    # Distribution metrics
    kurtosis: float = 0.0  # Measures "tailedness"
    skewness: float = 0.0
    
    # Outlier metrics
    outlier_ratio_3sigma: float = 0.0  # Fraction > 3*std
    outlier_ratio_6sigma: float = 0.0  # Fraction > 6*std
    max_outlier_magnitude: float = 0.0
    
    # Dynamic range
    dynamic_range: float = 0.0  # max / min (for positive values)
    log_dynamic_range: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "layer_name": self.layer_name,
            "layer_type": self.layer_type,
            "num_samples": self.num_samples,
            "feature_dim": self.feature_dim,
            "global_mean": self.global_mean,
            "global_std": self.global_std,
            "global_min": self.global_min,
            "global_max": self.global_max,
            "kurtosis": self.kurtosis,
            "skewness": self.skewness,
            "outlier_ratio_3sigma": self.outlier_ratio_3sigma,
            "outlier_ratio_6sigma": self.outlier_ratio_6sigma,
            "max_outlier_magnitude": self.max_outlier_magnitude,
            "dynamic_range": self.dynamic_range,
            "log_dynamic_range": self.log_dynamic_range,
        }


class ActivationStatsHook:
    """Hook for collecting activation statistics.
    
    Usage:
        hook = ActivationStatsHook()
        handles = hook.register(model)
        
        # Run inference
        for batch in calibration_data:
            model(batch)
        
        hook.remove_hooks(handles)
        stats = hook.get_all_stats()
    """
    
    def __init__(
        self,
        outlier_sigmas: list[float] | None = None,
        max_samples: int = 1000,
        layer_filter: Callable[[str, nn.Module], bool] | None = None,
    ):
        """Initialize the activation stats hook.
        
        Args:
            outlier_sigmas: Sigma thresholds for outlier detection
            max_samples: Maximum samples to collect per layer
            layer_filter: Optional filter function
        """
        self.outlier_sigmas = outlier_sigmas or [3.0, 6.0]
        self.max_samples = max_samples
        self.layer_filter = layer_filter or self._default_filter
        
        self._running_stats: dict[str, dict[str, Any]] = {}
        self._final_stats: dict[str, ActivationStats] = {}
    
    @staticmethod
    def _default_filter(name: str, module: nn.Module) -> bool:
        """Default filter: include Linear layers."""
        return isinstance(module, nn.Linear)
    
    def _create_hook(self, name: str, module: nn.Module) -> Callable:
        """Create a forward hook for a layer."""
        
        def hook(module: nn.Module, input: tuple, output: torch.Tensor) -> None:
            # Get input tensor
            if isinstance(input, tuple) and len(input) > 0:
                inp = input[0]
            else:
                inp = input
            
            if inp is None or not isinstance(inp, torch.Tensor):
                return
            
            with torch.no_grad():
                # Flatten to (batch * seq, features)
                if inp.dim() > 2:
                    inp_flat = inp.reshape(-1, inp.shape[-1])
                elif inp.dim() == 2:
                    inp_flat = inp
                else:
                    inp_flat = inp.unsqueeze(0)
                
                # Initialize running stats if needed
                if name not in self._running_stats:
                    self._running_stats[name] = {
                        "layer_type": type(module).__name__,
                        "sum": torch.zeros(inp_flat.shape[-1], device=inp_flat.device),
                        "sum_sq": torch.zeros(inp_flat.shape[-1], device=inp_flat.device),
                        "min": torch.full((inp_flat.shape[-1],), float("inf"), device=inp_flat.device),
                        "max": torch.full((inp_flat.shape[-1],), float("-inf"), device=inp_flat.device),
                        "count": 0,
                        "outlier_counts": {sigma: 0 for sigma in self.outlier_sigmas},
                        "total_elements": 0,
                        "max_abs": 0.0,
                        "samples": [],
                    }
                
                stats = self._running_stats[name]
                
                # Update running statistics
                batch_size = inp_flat.shape[0]
                if stats["count"] >= self.max_samples:
                    return
                
                # Welford's online algorithm for mean and variance
                stats["sum"] += inp_flat.sum(dim=0)
                stats["sum_sq"] += (inp_flat ** 2).sum(dim=0)
                stats["min"] = torch.minimum(stats["min"], inp_flat.min(dim=0)[0])
                stats["max"] = torch.maximum(stats["max"], inp_flat.max(dim=0)[0])
                stats["count"] += batch_size
                stats["total_elements"] += inp_flat.numel()
                
                # Track max absolute value
                max_abs = inp_flat.abs().max().item()
                stats["max_abs"] = max(stats["max_abs"], max_abs)
                
                # Store samples for later analysis (limited)
                if len(stats["samples"]) < 10:
                    stats["samples"].append(inp_flat.cpu())
        
        return hook
    
    def register(self, model: nn.Module) -> list[torch.utils.hooks.RemovableHandle]:
        """Register hooks on the model.
        
        Args:
            model: PyTorch model
            
        Returns:
            List of hook handles
        """
        handles = []
        
        for name, module in model.named_modules():
            if self.layer_filter(name, module):
                handle = module.register_forward_hook(self._create_hook(name, module))
                handles.append(handle)
        
        return handles
    
    def remove_hooks(self, handles: list[torch.utils.hooks.RemovableHandle]) -> None:
        """Remove registered hooks.
        
        Args:
            handles: List of hook handles
        """
        for handle in handles:
            handle.remove()
    
    def finalize_stats(self) -> dict[str, ActivationStats]:
        """Finalize and compute all statistics.
        
        Returns:
            Dictionary mapping layer names to ActivationStats
        """
        self._final_stats = {}
        
        for name, running in self._running_stats.items():
            if running["count"] == 0:
                continue
            
            count = running["count"]
            
            # Compute mean and std per channel
            mean = running["sum"] / count
            variance = (running["sum_sq"] / count) - (mean ** 2)
            std = torch.sqrt(torch.clamp(variance, min=1e-8))
            
            # Create stats object
            stats = ActivationStats(
                layer_name=name,
                layer_type=running["layer_type"],
                num_samples=count,
                feature_dim=len(mean),
                mean=mean.cpu().tolist(),
                std=std.cpu().tolist(),
                min_val=running["min"].cpu().tolist(),
                max_val=running["max"].cpu().tolist(),
                global_mean=mean.mean().item(),
                global_std=std.mean().item(),
                global_min=running["min"].min().item(),
                global_max=running["max"].max().item(),
                max_outlier_magnitude=running["max_abs"],
            )
            
            # Compute outlier ratios from samples
            if running["samples"]:
                all_samples = torch.cat(running["samples"], dim=0)
                global_mean = all_samples.mean()
                global_std = all_samples.std()
                
                if global_std > 1e-8:
                    # Outlier ratios
                    for sigma in self.outlier_sigmas:
                        outlier_mask = (all_samples - global_mean).abs() > sigma * global_std
                        ratio = outlier_mask.float().mean().item()
                        if sigma == 3.0:
                            stats.outlier_ratio_3sigma = ratio
                        elif sigma == 6.0:
                            stats.outlier_ratio_6sigma = ratio
                    
                    # Skewness and kurtosis
                    centered = all_samples - global_mean
                    stats.skewness = (centered ** 3).mean().item() / (global_std ** 3)
                    stats.kurtosis = (centered ** 4).mean().item() / (global_std ** 4) - 3
            
            # Dynamic range
            pos_min = running["min"][running["min"] > 0].min().item() if (running["min"] > 0).any() else 1e-8
            pos_max = running["max"].max().item()
            if pos_min > 0:
                stats.dynamic_range = pos_max / pos_min
                stats.log_dynamic_range = torch.log10(torch.tensor(stats.dynamic_range)).item()
            
            self._final_stats[name] = stats
        
        return self._final_stats
    
    def get_all_stats(self) -> dict[str, ActivationStats]:
        """Get all finalized statistics."""
        if not self._final_stats:
            self.finalize_stats()
        return self._final_stats
    
    def get_outlier_layers(
        self,
        sigma_threshold: float = 6.0,
        ratio_threshold: float = 0.001,
    ) -> list[str]:
        """Get layers with significant outliers.
        
        Args:
            sigma_threshold: Sigma threshold for outliers
            ratio_threshold: Minimum outlier ratio to flag
            
        Returns:
            List of layer names with outliers
        """
        if not self._final_stats:
            self.finalize_stats()
        
        outlier_layers = []
        for name, stats in self._final_stats.items():
            if sigma_threshold == 6.0 and stats.outlier_ratio_6sigma > ratio_threshold:
                outlier_layers.append(name)
            elif sigma_threshold == 3.0 and stats.outlier_ratio_3sigma > ratio_threshold:
                outlier_layers.append(name)
        
        return outlier_layers
    
    def get_smoothquant_scales(self, alpha: float = 0.5) -> dict[str, torch.Tensor]:
        """Compute SmoothQuant-style scales.
        
        Args:
            alpha: Smoothing parameter (0 = all on weights, 1 = all on activations)
            
        Returns:
            Dictionary mapping layer names to smoothing scales
        """
        if not self._final_stats:
            self.finalize_stats()
        
        scales = {}
        for name, stats in self._final_stats.items():
            # Scale = max_activation ^ alpha
            max_acts = torch.tensor(stats.max_val)
            max_acts = torch.clamp(max_acts.abs(), min=1e-8)
            scale = max_acts.pow(alpha)
            scales[name] = scale
        
        return scales
    
    def to_db_records(
        self,
        experiment_id: int,
        quant_config_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Convert statistics to database records.
        
        Args:
            experiment_id: Experiment ID
            quant_config_id: Optional quant config ID
            
        Returns:
            List of records suitable for layer_metrics table
        """
        if not self._final_stats:
            self.finalize_stats()
        
        records = []
        
        for idx, (name, stats) in enumerate(self._final_stats.items()):
            metrics = [
                ("activation_mean", stats.global_mean),
                ("activation_std", stats.global_std),
                ("activation_min", stats.global_min),
                ("activation_max", stats.global_max),
                ("activation_kurtosis", stats.kurtosis),
                ("activation_skewness", stats.skewness),
                ("outlier_ratio_3sigma", stats.outlier_ratio_3sigma),
                ("outlier_ratio_6sigma", stats.outlier_ratio_6sigma),
                ("max_outlier_magnitude", stats.max_outlier_magnitude),
                ("dynamic_range", stats.dynamic_range),
            ]
            
            for metric_name, value in metrics:
                records.append({
                    "experiment_id": experiment_id,
                    "quant_config_id": quant_config_id,
                    "layer_index": idx,
                    "layer_name": stats.layer_name,
                    "layer_type": stats.layer_type,
                    "stat_name": metric_name,
                    "stat_type": "activation",
                    "value": value,
                })
        
        return records
    
    def reset(self) -> None:
        """Reset all collected statistics."""
        self._running_stats = {}
        self._final_stats = {}
