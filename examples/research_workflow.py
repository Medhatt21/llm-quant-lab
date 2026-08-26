#!/usr/bin/env python3
"""Research workflow example: Compare quantization methods on a model.

This script demonstrates a complete research workflow:
1. Load a model from HuggingFace
2. Run multiple quantization algorithms
3. Evaluate each on perplexity
4. Compare results and generate analysis

This is the recommended way to run quantization experiments for research.

Prerequisites:
    1. Install LightCompress:
       make llmc-install
    
    2. Install project:
       uv sync

Usage:
    # Compare AWQ vs GPTQ on OPT-125M
    python examples/research_workflow.py \\
        --model facebook/opt-125m \\
        --algorithms awq,gptq

    # Full comparison with multiple bit widths
    python examples/research_workflow.py \\
        --model facebook/opt-125m \\
        --algorithms awq,gptq,rtn,hqq \\
        --bit-widths 4

    # Generate YAML configs only (for manual LLMC runs)
    python examples/research_workflow.py \\
        --model facebook/opt-125m \\
        --algorithms awq,gptq \\
        --config-only \\
        --output-dir configs/generated
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Result from a single quantization experiment."""
    algorithm: str
    bit_width: int
    group_size: int
    success: bool
    
    # Metrics
    original_size_mb: float = 0.0
    quantized_size_mb: float = 0.0
    compression_ratio: float = 0.0
    perplexity: float | None = None
    
    # Timing
    total_time_seconds: float = 0.0
    
    # Error (if failed)
    error: str | None = None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run comparative quantization experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        required=True,
        help="HuggingFace model ID (e.g., facebook/opt-125m)",
    )
    parser.add_argument(
        "--algorithms", "-a",
        type=str,
        default="awq,gptq",
        help="Comma-separated list of algorithms to compare",
    )
    parser.add_argument(
        "--bit-widths", "-b",
        type=str,
        default="4",
        help="Comma-separated list of bit widths to test",
    )
    parser.add_argument(
        "--group-size", "-g",
        type=int,
        default=128,
        help="Group size for quantization",
    )
    parser.add_argument(
        "--calib-dataset",
        type=str,
        default="wikitext2",
        help="Calibration dataset",
    )
    parser.add_argument(
        "--calib-samples",
        type=int,
        default=128,
        help="Number of calibration samples",
    )
    parser.add_argument(
        "--eval-datasets",
        type=str,
        default="wikitext2",
        help="Evaluation datasets (comma-separated)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Directory for output files",
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Only generate YAML configs, don't run quantization",
    )
    parser.add_argument(
        "--save-models",
        action="store_true",
        help="Save quantized models",
    )
    
    return parser.parse_args()


def validate_algorithms(algorithms: list[str]) -> list[str]:
    """Validate and return supported algorithms."""
    from src.quant.llmc_wrappers import LLMC_ALGORITHMS
    
    valid = []
    for algo in algorithms:
        algo = algo.strip().lower()
        if algo in LLMC_ALGORITHMS:
            valid.append(algo)
        else:
            logger.warning(f"Unknown algorithm '{algo}', skipping")
    
    return valid


def run_single_experiment(
    model_path: str,
    algorithm: str,
    bit_width: int,
    group_size: int,
    calib_dataset: str,
    calib_samples: int,
    eval_datasets: list[str],
    save_path: str | None = None,
) -> ExperimentResult:
    """Run a single quantization experiment."""
    from src.quant.llmc_wrappers import (
        LLMCRunner,
        create_config_from_experiment,
        LLMC_ALGORITHMS,
    )
    
    spec = LLMC_ALGORITHMS[algorithm]
    
    # Check if bit width is supported
    if bit_width not in spec.supported_bits:
        return ExperimentResult(
            algorithm=algorithm,
            bit_width=bit_width,
            group_size=group_size,
            success=False,
            error=f"{algorithm} does not support {bit_width}-bit (supported: {spec.supported_bits})",
        )
    
    logger.info(f"Running {algorithm} @ {bit_width}-bit...")
    
    try:
        config = create_config_from_experiment(
            model_path=model_path,
            algorithm=algorithm,
            bit_width=bit_width,
            group_size=group_size,
            calib_dataset=calib_dataset,
            calib_samples=calib_samples,
            eval_datasets=eval_datasets,
            save_path=save_path,
        )
        
        runner = LLMCRunner()
        result = runner.run_quantization(config, capture_stats=True)
        
        if result.success:
            perplexity = None
            if result.eval_results:
                # Get perplexity from first eval dataset
                for dataset, metrics in result.eval_results.items():
                    if "perplexity" in metrics:
                        perplexity = metrics["perplexity"]
                        break
            
            return ExperimentResult(
                algorithm=algorithm,
                bit_width=bit_width,
                group_size=group_size,
                success=True,
                original_size_mb=result.original_size_mb,
                quantized_size_mb=result.quantized_size_mb,
                compression_ratio=result.compression_ratio,
                perplexity=perplexity,
                total_time_seconds=result.total_time_seconds,
            )
        else:
            return ExperimentResult(
                algorithm=algorithm,
                bit_width=bit_width,
                group_size=group_size,
                success=False,
                error=result.error,
            )
    
    except Exception as e:
        logger.error(f"Experiment failed: {e}")
        return ExperimentResult(
            algorithm=algorithm,
            bit_width=bit_width,
            group_size=group_size,
            success=False,
            error=str(e),
        )


def generate_configs_only(
    model_path: str,
    algorithms: list[str],
    bit_widths: list[int],
    group_size: int,
    calib_dataset: str,
    calib_samples: int,
    eval_datasets: list[str],
    output_dir: Path,
) -> list[Path]:
    """Generate YAML configs without running quantization."""
    from src.quant.llmc_wrappers import create_config_from_experiment, LLMC_ALGORITHMS
    
    output_dir.mkdir(parents=True, exist_ok=True)
    config_paths = []
    
    for algo in algorithms:
        spec = LLMC_ALGORITHMS[algo]
        
        for bits in bit_widths:
            if bits not in spec.supported_bits:
                logger.warning(f"Skipping {algo}@{bits}bit (not supported)")
                continue
            
            config = create_config_from_experiment(
                model_path=model_path,
                algorithm=algo,
                bit_width=bits,
                group_size=group_size,
                calib_dataset=calib_dataset,
                calib_samples=calib_samples,
                eval_datasets=eval_datasets,
            )
            
            config_name = f"{algo}_w{bits}_g{group_size}.yaml"
            config_path = config.to_yaml_file(output_dir / config_name)
            config_paths.append(config_path)
            
            logger.info(f"Generated: {config_path}")
    
    return config_paths


def print_results_table(results: list[ExperimentResult]):
    """Print results as a formatted table."""
    print("\n" + "=" * 90)
    print("COMPARISON RESULTS")
    print("=" * 90)
    
    # Header
    print(f"{'Algorithm':<15} {'Bits':>5} {'Group':>6} {'Size (MB)':>12} {'Compress':>10} {'PPL':>10} {'Time':>8} {'Status':<8}")
    print("-" * 90)
    
    for r in results:
        if r.success:
            ppl_str = f"{r.perplexity:.2f}" if r.perplexity else "N/A"
            print(
                f"{r.algorithm:<15} {r.bit_width:>5} {r.group_size:>6} "
                f"{r.quantized_size_mb:>12.2f} {r.compression_ratio:>10.2f}x "
                f"{ppl_str:>10} {r.total_time_seconds:>7.1f}s {'OK':<8}"
            )
        else:
            print(f"{r.algorithm:<15} {r.bit_width:>5} {r.group_size:>6} {'':>12} {'':>10} {'':>10} {'':>8} {'FAIL':<8}")
            if r.error:
                print(f"    Error: {r.error[:60]}...")
    
    print("=" * 90)


def save_results(results: list[ExperimentResult], output_path: Path):
    """Save results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": [asdict(r) for r in results],
    }
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Results saved to: {output_path}")


def main():
    args = parse_args()
    
    # Parse inputs
    algorithms = [a.strip() for a in args.algorithms.split(",")]
    bit_widths = [int(b.strip()) for b in args.bit_widths.split(",")]
    eval_datasets = [d.strip() for d in args.eval_datasets.split(",")]
    output_dir = Path(args.output_dir)
    
    # Check LLMC availability
    from src.quant.llmc_wrappers import LLMC_AVAILABLE
    if not LLMC_AVAILABLE:
        print("ERROR: LightCompress not installed")
        print("Run: make llmc-install")
        return 1
    
    # Validate algorithms
    algorithms = validate_algorithms(algorithms)
    if not algorithms:
        print("ERROR: No valid algorithms specified")
        return 1
    
    print("=" * 80)
    print("LLM Quant Lab - Research Workflow")
    print("=" * 80)
    print(f"Model:       {args.model}")
    print(f"Algorithms:  {', '.join(algorithms)}")
    print(f"Bit widths:  {bit_widths}")
    print(f"Group size:  {args.group_size}")
    print(f"Calib data:  {args.calib_dataset} ({args.calib_samples} samples)")
    print(f"Eval data:   {', '.join(eval_datasets)}")
    print(f"Output:      {output_dir}")
    print("=" * 80)
    
    # Config-only mode
    if args.config_only:
        print("\nGenerating YAML configs only...")
        config_paths = generate_configs_only(
            model_path=args.model,
            algorithms=algorithms,
            bit_widths=bit_widths,
            group_size=args.group_size,
            calib_dataset=args.calib_dataset,
            calib_samples=args.calib_samples,
            eval_datasets=eval_datasets,
            output_dir=output_dir / "configs",
        )
        print(f"\nGenerated {len(config_paths)} configs")
        print("Run with LLMC directly:")
        for p in config_paths:
            print(f"  python -m llmc --config {p}")
        return 0
    
    # Run experiments
    results: list[ExperimentResult] = []
    total_experiments = len(algorithms) * len(bit_widths)
    current = 0
    
    for algo in algorithms:
        for bits in bit_widths:
            current += 1
            print(f"\n[{current}/{total_experiments}] Running {algo} @ {bits}-bit...")
            
            save_path = None
            if args.save_models:
                save_path = str(output_dir / "models" / f"{algo}_w{bits}_g{args.group_size}")
            
            result = run_single_experiment(
                model_path=args.model,
                algorithm=algo,
                bit_width=bits,
                group_size=args.group_size,
                calib_dataset=args.calib_dataset,
                calib_samples=args.calib_samples,
                eval_datasets=eval_datasets,
                save_path=save_path,
            )
            results.append(result)
    
    # Print and save results
    print_results_table(results)
    
    results_path = output_dir / "comparison_results.json"
    save_results(results, results_path)
    
    # Summary
    successful = sum(1 for r in results if r.success)
    print(f"\nCompleted: {successful}/{len(results)} experiments successful")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
