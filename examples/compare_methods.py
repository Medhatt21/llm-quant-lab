#!/usr/bin/env python3
"""Example: Compare AWQ vs GPTQ quantization methods.

This script demonstrates how to programmatically run experiments
comparing different quantization methods on the same model.

Prerequisites:
    - pip install autoawq auto-gptq
    - Database must be running: make docker-up
    - DB schema initialized: make db-init
"""

import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_dependencies() -> dict[str, bool]:
    """Check which quantization backends are available."""
    available = {}
    
    try:
        import awq
        available["awq"] = True
    except ImportError:
        available["awq"] = False
        logger.warning("AutoAWQ not installed. AWQ experiments will be skipped.")
    
    try:
        import auto_gptq
        available["gptq"] = True
    except ImportError:
        available["gptq"] = False
        logger.warning("AutoGPTQ not installed. GPTQ experiments will be skipped.")
    
    try:
        import bitsandbytes
        available["llm_int8"] = True
    except ImportError:
        available["llm_int8"] = False
        logger.warning("bitsandbytes not installed. LLM.int8() experiments will be skipped.")
    
    return available


def main():
    """Run comparison experiments."""
    from src.quant.base import QuantizerConfig, get_quantizer, check_quantizer_available
    from src.quant.llmc_wrappers import load_model_for_quantization
    from src.eval.datasets import load_calibration_data, compute_perplexity
    from src.eval.hardware import profile_model
    from src.db import get_session
    from src.db.logging import (
        create_experiment,
        create_quant_config,
        log_metric,
        log_hardware_stats,
    )
    from src.analytics.reports import generate_comparison_report
    
    # Configuration
    model_path = "facebook/opt-125m"  # Small model for testing
    methods_to_test = ["awq", "gptq"]  # Methods to compare
    bit_width = 4
    
    # Check available backends
    available = check_dependencies()
    methods_to_run = [m for m in methods_to_test if available.get(m, False)]
    
    if not methods_to_run:
        logger.error("No quantization backends available. Install autoawq or auto-gptq.")
        sys.exit(1)
    
    logger.info(f"Comparing methods: {methods_to_run}")
    logger.info(f"Model: {model_path}")
    logger.info(f"Bit width: {bit_width}")
    
    # Load model and tokenizer
    logger.info("Loading model...")
    model, tokenizer = load_model_for_quantization(model_path)
    
    # Load calibration and evaluation data
    logger.info("Loading calibration data...")
    calib_data = load_calibration_data(
        dataset_name="wikitext2",
        tokenizer=tokenizer,
        num_samples=128,
        seq_length=2048,
    )
    
    # Get database session
    session = get_session()
    experiment_ids = []
    
    try:
        for method in methods_to_run:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running experiment: {method.upper()} {bit_width}-bit")
            logger.info(f"{'='*60}")
            
            # Check if method is available
            is_available, msg = check_quantizer_available(method)
            if not is_available:
                logger.warning(f"Skipping {method}: {msg}")
                continue
            
            # Create experiment record
            experiment = create_experiment(
                session,
                model_name=model_path,
                name=f"compare_{method}_{bit_width}bit",
                base_precision="fp16",
                tags=["comparison", method, f"{bit_width}bit"],
            )
            experiment_ids.append(experiment.id)
            
            # Create quantizer config
            config = QuantizerConfig(
                method=method,
                bit_width=bit_width,
                group_size=128,
                calib_dataset="wikitext2",
                calib_size=128,
            )
            
            quant_config = create_quant_config(
                session,
                experiment_id=experiment.id,
                method_name=method,
                bit_width=bit_width,
                group_size=128,
            )
            
            # Get quantizer and run quantization
            quantizer = get_quantizer(method, config)
            
            logger.info("Preparing quantization...")
            state = quantizer.prepare(model, calib_data)
            
            logger.info("Applying quantization...")
            quantized_model = quantizer.apply(model, state)
            
            # Evaluate perplexity using LightCompress
            logger.info("Evaluating perplexity...")
            ppl_results = compute_perplexity(
                model=quantized_model,
                tokenizer=tokenizer,
                dataset_name="wikitext2",
                seq_len=2048,
                batch_size=1,
            )
            
            log_metric(
                session,
                experiment_id=experiment.id,
                quant_config_id=quant_config.id,
                dataset="wikitext2",
                metric_name="perplexity",
                value=ppl_results["perplexity"],
                split="test",
            )
            
            # Profile hardware
            logger.info("Profiling hardware performance...")
            
            def input_fn():
                return {"input_ids": calib_data[0].cuda()}
            
            hw_stats = profile_model(
                quantized_model,
                input_fn=input_fn,
                warmup_iterations=3,
                benchmark_iterations=10,
            )
            
            log_hardware_stats(
                session,
                experiment_id=experiment.id,
                quant_config_id=quant_config.id,
                **hw_stats.to_dict(),
            )
            
            # Get metadata
            metadata = quantizer.metadata(state)
            
            logger.info(f"Experiment {experiment.id} completed:")
            logger.info(f"  Perplexity: {ppl_results['perplexity']:.2f}")
            logger.info(f"  Latency P50: {hw_stats.latency.p50:.2f} ms")
            logger.info(f"  Throughput: {hw_stats.latency.tokens_per_second:.1f} tok/s")
            logger.info(f"  Compression: {metadata.get('compression_ratio', 0):.2f}x")
            
            # Reload original model for next method
            if method != methods_to_run[-1]:
                logger.info("Reloading original model for next method...")
                model, tokenizer = load_model_for_quantization(model_path)
        
        # Generate comparison report
        if len(experiment_ids) > 1:
            logger.info(f"\n{'='*60}")
            logger.info("Generating comparison report...")
            logger.info(f"{'='*60}")
            
            from src.db.queries import get_experiment_with_details
            
            experiments = []
            for exp_id in experiment_ids:
                exp_data = get_experiment_with_details(session, exp_id)
                if exp_data:
                    experiments.append(exp_data)
            
            if experiments:
                report_path = Path("reports") / "method_comparison.md"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                
                report = generate_comparison_report(experiments, str(report_path))
                logger.info(f"Report saved to: {report_path}")
                
                # Print summary
                print("\n" + "=" * 60)
                print("COMPARISON SUMMARY")
                print("=" * 60)
                print(report[:2000])
        
        logger.info("\nDone!")
        return experiment_ids
    
    finally:
        session.close()


if __name__ == "__main__":
    main()
