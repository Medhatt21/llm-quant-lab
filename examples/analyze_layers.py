#!/usr/bin/env python3
"""Example: Analyze layer-wise statistics for quantization.

This script demonstrates how to use the activation and weight hooks
to analyze model characteristics relevant to quantization, including:
- Weight distribution statistics
- Activation outlier detection (important for SmoothQuant)
- Dynamic range analysis

Prerequisites:
    - pip install transformers torch
    - No quantization libraries required for analysis
"""

import logging
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Analyze layer statistics for a model."""
    from src.hooks.activations import ActivationStatsHook
    from src.hooks.weights import WeightStatsHook
    from src.eval.datasets import load_calibration_data
    
    # Configuration
    model_name = "facebook/opt-125m"
    num_calib_samples = 32
    seq_length = 512
    
    # Load model
    logger.info(f"Loading model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    
    device = next(model.parameters()).device
    
    # =========================================================================
    # Weight Analysis
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("WEIGHT ANALYSIS")
    logger.info("=" * 60)
    
    weight_hook = WeightStatsHook()
    weight_stats = weight_hook.collect_stats(model)
    
    print(f"\nFound {len(weight_stats)} layers with weights\n")
    print(f"{'Layer':<50} {'Norm':<12} {'Mean':<12} {'Std':<12} {'Sparsity':<12}")
    print("-" * 98)
    
    # Show first 20 layers
    for name, stats in list(weight_stats.items())[:20]:
        short_name = name[-50:] if len(name) > 50 else name
        print(
            f"{short_name:<50} {stats.norm_l2:<12.4f} {stats.mean:<12.6f} "
            f"{stats.std:<12.6f} {stats.sparsity:<12.6f}"
        )
    
    # Identify layers with potential quantization issues
    print("\n⚠️  Layers with high weight variance (potential quantization issues):")
    high_variance_layers = [
        (name, stats) for name, stats in weight_stats.items()
        if stats.std > 0.1
    ]
    for name, stats in high_variance_layers[:5]:
        print(f"  - {name}: std={stats.std:.4f}")
    
    # =========================================================================
    # Activation Analysis
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("ACTIVATION ANALYSIS")
    logger.info("=" * 60)
    
    # Load calibration data
    logger.info("Loading calibration data...")
    calib_data = load_calibration_data(
        dataset_name="wikitext2",
        tokenizer=tokenizer,
        num_samples=num_calib_samples,
        seq_length=seq_length,
    )
    
    # Collect activation statistics
    activation_hook = ActivationStatsHook(
        outlier_sigmas=[3.0, 6.0],
        max_samples=num_calib_samples * 10,
    )
    handles = activation_hook.register(model)
    
    logger.info("Running calibration forward passes...")
    model.eval()
    
    with torch.no_grad():
        for i, batch in enumerate(calib_data[:num_calib_samples]):
            batch = batch.to(device)
            try:
                model(batch)
            except Exception as e:
                logger.warning(f"Forward pass {i} failed: {e}")
    
    activation_hook.remove_hooks(handles)
    activation_stats = activation_hook.get_all_stats()
    
    print(f"\nCollected activation stats for {len(activation_stats)} layers\n")
    print(f"{'Layer':<50} {'Mean':<12} {'Std':<12} {'6σ Outliers':<12} {'Kurtosis':<12}")
    print("-" * 98)
    
    for name, stats in list(activation_stats.items())[:20]:
        short_name = name[-50:] if len(name) > 50 else name
        outlier_pct = stats.outlier_ratio_6sigma * 100
        print(
            f"{short_name:<50} {stats.global_mean:<12.4f} {stats.global_std:<12.4f} "
            f"{outlier_pct:<12.4f}% {stats.kurtosis:<12.2f}"
        )
    
    # =========================================================================
    # Outlier Analysis (Important for SmoothQuant)
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("OUTLIER ANALYSIS (for SmoothQuant)")
    logger.info("=" * 60)
    
    outlier_layers = activation_hook.get_outlier_layers(
        sigma_threshold=6.0,
        ratio_threshold=0.0001,  # 0.01% outliers
    )
    
    if outlier_layers:
        print(f"\n⚠️  {len(outlier_layers)} layers with significant outliers (>6σ):")
        for layer in outlier_layers[:10]:
            stats = activation_stats[layer]
            print(
                f"  - {layer}: {stats.outlier_ratio_6sigma*100:.4f}% outliers, "
                f"max magnitude: {stats.max_outlier_magnitude:.2f}"
            )
        
        print("\n💡 Recommendation: Consider using SmoothQuant for this model")
        print("   SmoothQuant can migrate these outliers from activations to weights")
    else:
        print("\n✓ No layers with significant outliers detected")
        print("💡 Standard weight-only quantization (AWQ, GPTQ) should work well")
    
    # =========================================================================
    # SmoothQuant Scale Computation
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SMOOTHQUANT SCALE ANALYSIS")
    logger.info("=" * 60)
    
    # Compute SmoothQuant-style scales
    smoothquant_scales = activation_hook.get_smoothquant_scales(alpha=0.5)
    
    print(f"\nComputed smoothing scales for {len(smoothquant_scales)} layers")
    print("\nTop 10 layers by scale magnitude:")
    
    scale_magnitudes = [
        (name, scale.max().item(), scale.mean().item())
        for name, scale in smoothquant_scales.items()
    ]
    scale_magnitudes.sort(key=lambda x: x[1], reverse=True)
    
    print(f"{'Layer':<50} {'Max Scale':<15} {'Mean Scale':<15}")
    print("-" * 80)
    for name, max_scale, mean_scale in scale_magnitudes[:10]:
        short_name = name[-50:] if len(name) > 50 else name
        print(f"{short_name:<50} {max_scale:<15.4f} {mean_scale:<15.4f}")
    
    # =========================================================================
    # Summary and Recommendations
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY AND RECOMMENDATIONS")
    logger.info("=" * 60)
    
    # Calculate overall metrics
    total_outlier_layers = len(outlier_layers)
    avg_kurtosis = sum(s.kurtosis for s in activation_stats.values()) / len(activation_stats)
    max_dynamic_range = max(s.dynamic_range for s in activation_stats.values())
    
    print(f"""
Model: {model_name}
Total layers analyzed: {len(weight_stats)} (weights), {len(activation_stats)} (activations)

Weight Statistics:
  - Layers with high variance: {len(high_variance_layers)}
  
Activation Statistics:
  - Layers with 6σ outliers: {total_outlier_layers}
  - Average kurtosis: {avg_kurtosis:.2f} (>3 indicates heavy tails)
  - Max dynamic range: {max_dynamic_range:.2f}

Quantization Recommendations:
""")
    
    if total_outlier_layers > len(activation_stats) * 0.1:
        print("  ⚠️  HIGH OUTLIER RATIO - SmoothQuant recommended")
        print("     Many layers have activation outliers that could hurt quantization")
    elif avg_kurtosis > 5:
        print("  ⚠️  HIGH KURTOSIS - Consider SmoothQuant or careful calibration")
        print("     Activations have heavy tails")
    else:
        print("  ✓ Standard quantization should work well")
        print("     AWQ or GPTQ recommended for 4-bit weight quantization")
    
    if max_dynamic_range > 1e6:
        print("  ⚠️  HIGH DYNAMIC RANGE - Consider mixed-precision quantization")
    
    logger.info("\nAnalysis complete!")


if __name__ == "__main__":
    main()
