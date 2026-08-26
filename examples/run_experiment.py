#!/usr/bin/env python3
"""Run a quantization experiment using LightCompress.

This script demonstrates the proper usage of the LLM Quant Lab framework
with LightCompress as the quantization backend.

Prerequisites:
    1. Install LightCompress:
       git clone https://github.com/ModelTC/LightCompress.git
       cd LightCompress && pip install -e .
    
    2. Install project dependencies:
       cd /u01/llm-quant-lab && uv sync

Usage:
    # Run AWQ 4-bit quantization on OPT-125M
    python examples/run_experiment.py \\
        --model facebook/opt-125m \\
        --algorithm awq \\
        --bit-width 4

    # Run GPTQ with custom group size
    python examples/run_experiment.py \\
        --model facebook/opt-125m \\
        --algorithm gptq \\
        --bit-width 4 \\
        --group-size 64

    # Run SmoothQuant W8A8
    python examples/run_experiment.py \\
        --model facebook/opt-125m \\
        --algorithm smoothquant \\
        --bit-width 8

    # List available algorithms
    python examples/run_experiment.py --list-algorithms
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run LLM quantization experiment using LightCompress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Mode flags
    parser.add_argument(
        "--list-algorithms",
        action="store_true",
        help="List available quantization algorithms and exit",
    )
    
    # Model configuration
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="HuggingFace model ID or local path (e.g., facebook/opt-125m)",
    )
    
    # Quantization configuration
    parser.add_argument(
        "--algorithm", "-a",
        type=str,
        help="Quantization algorithm (awq, gptq, smoothquant, omniquant, quarot, etc.)",
    )
    parser.add_argument(
        "--bit-width", "-b",
        type=int,
        default=4,
        help="Bit width for weight quantization (default: 4)",
    )
    parser.add_argument(
        "--group-size", "-g",
        type=int,
        default=128,
        help="Group size for quantization (default: 128, use -1 for per-channel)",
    )
    
    # Calibration configuration
    parser.add_argument(
        "--calib-dataset",
        type=str,
        default="wikitext2",
        choices=["wikitext2", "c4", "ptb", "pile", "pileval"],
        help="Calibration dataset (default: wikitext2)",
    )
    parser.add_argument(
        "--calib-samples",
        type=int,
        default=128,
        help="Number of calibration samples (default: 128)",
    )
    parser.add_argument(
        "--calib-seq-len",
        type=int,
        default=2048,
        help="Calibration sequence length (default: 2048)",
    )
    
    # Evaluation configuration
    parser.add_argument(
        "--eval-datasets",
        type=str,
        default="wikitext2",
        help="Evaluation datasets, comma-separated (default: wikitext2)",
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Skip evaluation",
    )
    
    # Output configuration
    parser.add_argument(
        "--save-path",
        type=str,
        help="Path to save quantized model",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["vllm", "sglang", "autoawq", "lightllm"],
        help="Export backend format",
    )
    parser.add_argument(
        "--config-out",
        type=str,
        help="Path to save LLMC YAML config",
    )
    
    # Algorithm-specific options
    parser.add_argument(
        "--alpha",
        type=float,
        help="SmoothQuant alpha parameter (default: 0.5)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        help="OmniQuant training epochs (default: 20)",
    )
    
    return parser.parse_args()


def list_algorithms():
    """Print available algorithms with details."""
    from src.quant.llmc_wrappers import LLMC_ALGORITHMS, LLMC_AVAILABLE
    
    if not LLMC_AVAILABLE:
        print("WARNING: LightCompress not installed. Install from:")
        print("  git clone https://github.com/ModelTC/LightCompress.git")
        print("  cd LightCompress && pip install -e .")
        print()
    
    print("=" * 80)
    print("Available Quantization Algorithms (LightCompress)")
    print("=" * 80)
    print()
    
    # Group by type
    weight_only = []
    weight_act = []
    learnable = []
    
    for name, spec in LLMC_ALGORITHMS.items():
        entry = (name, spec)
        if "omniquant" in name or "adadim" in name or "normtweaking" in name or "tesseraq" in name:
            learnable.append(entry)
        elif spec.supports_activation_quant:
            weight_act.append(entry)
        else:
            weight_only.append(entry)
    
    def print_group(title, entries):
        print(f"  {title}")
        print("  " + "-" * 60)
        for name, spec in entries:
            bits = ", ".join(map(str, spec.supported_bits))
            calib = "Yes" if spec.requires_calibration else "No"
            print(f"    {name:<15} bits=[{bits:<10}] calib={calib:<4} {spec.description[:40]}")
        print()
    
    print_group("Weight-Only Quantization", weight_only)
    print_group("Weight + Activation Quantization", weight_act)
    print_group("Learnable/Adaptive Quantization", learnable)
    
    print("=" * 80)
    print("Usage: python examples/run_experiment.py --model <model> --algorithm <algo>")
    print("=" * 80)


def main():
    args = parse_args()
    
    # Handle list mode
    if args.list_algorithms:
        list_algorithms()
        return 0
    
    # Validate required args
    if not args.model:
        print("ERROR: --model is required")
        print("Use --list-algorithms to see available options")
        return 1
    
    if not args.algorithm:
        print("ERROR: --algorithm is required")
        print("Use --list-algorithms to see available options")
        return 1
    
    # Import after arg validation to speed up --help
    from src.quant.llmc_wrappers import (
        LLMC_AVAILABLE,
        LLMC_ALGORITHMS,
        LLMCRunner,
        create_config_from_experiment,
    )
    
    if not LLMC_AVAILABLE:
        print("ERROR: LightCompress not installed")
        print("Install from: https://github.com/ModelTC/LightCompress")
        return 1
    
    # Validate algorithm
    if args.algorithm.lower() not in LLMC_ALGORITHMS:
        print(f"ERROR: Unknown algorithm '{args.algorithm}'")
        print(f"Available: {', '.join(LLMC_ALGORITHMS.keys())}")
        return 1
    
    spec = LLMC_ALGORITHMS[args.algorithm.lower()]
    
    # Validate bit width
    if args.bit_width not in spec.supported_bits:
        print(f"ERROR: {args.algorithm} does not support {args.bit_width}-bit")
        print(f"Supported: {spec.supported_bits}")
        return 1
    
    # Build extra config from args
    extra_config = {}
    if args.alpha is not None:
        extra_config["alpha"] = args.alpha
    if args.epochs is not None:
        extra_config["epochs"] = args.epochs
    
    # Parse eval datasets
    eval_datasets = None if args.no_eval else args.eval_datasets.split(",")
    
    # Create config
    print("=" * 80)
    print("LLM Quant Lab - Quantization Experiment")
    print("=" * 80)
    print(f"Model:      {args.model}")
    print(f"Algorithm:  {args.algorithm} ({spec.description})")
    print(f"Bit width:  {args.bit_width}")
    print(f"Group size: {args.group_size}")
    print(f"Calib data: {args.calib_dataset} ({args.calib_samples} samples)")
    if eval_datasets:
        print(f"Eval data:  {', '.join(eval_datasets)}")
    if args.save_path:
        print(f"Save path:  {args.save_path}")
    if args.backend:
        print(f"Backend:    {args.backend}")
    print("=" * 80)
    
    config = create_config_from_experiment(
        model_path=args.model,
        algorithm=args.algorithm,
        bit_width=args.bit_width,
        group_size=args.group_size if args.group_size > 0 else 0,
        calib_dataset=args.calib_dataset,
        calib_samples=args.calib_samples,
        calib_seq_len=args.calib_seq_len,
        eval_datasets=eval_datasets,
        save_path=args.save_path,
        backend=args.backend,
        **extra_config,
    )
    
    # Save config if requested
    if args.config_out:
        config_path = config.to_yaml_file(args.config_out)
        print(f"Config saved to: {config_path}")
    
    # Run quantization
    print("\nStarting quantization...")
    runner = LLMCRunner()
    result = runner.run_quantization(config, capture_stats=True)
    
    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    if result.success:
        print(f"Status:           SUCCESS")
        print(f"Total time:       {result.total_time_seconds:.1f}s")
        print(f"Original size:    {result.original_size_mb:.2f} MB")
        print(f"Quantized size:   {result.quantized_size_mb:.2f} MB")
        print(f"Compression:      {result.compression_ratio:.2f}x")
        
        if result.eval_results:
            print("\nEvaluation Results:")
            for dataset, metrics in result.eval_results.items():
                if "perplexity" in metrics:
                    print(f"  {dataset}: perplexity = {metrics['perplexity']:.2f}")
                elif "error" in metrics:
                    print(f"  {dataset}: ERROR - {metrics['error']}")
        
        if result.output_path:
            print(f"\nQuantized model saved to: {result.output_path}")
    else:
        print(f"Status:  FAILED")
        print(f"Error:   {result.error}")
        return 1
    
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
