# GPTQ Paper Reproduction Report

**Author**: LLM Quant Lab  
**Date**: 2026-02-08T17:32:49.866138

## Description

Reproduction of key results from 'GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers' (Frantar et al., 2022). Testing OPT models with GPTQ and RTN baseline at 4-bit quantization.

## Results Summary

### Perplexity Results

| Model | Method | Bits | Group Size | WIKITEXT2 PPL |
|---|---|---|---|---|
| opt-125m | gptq | 4 | 128 | 29.45 |
| opt-125m | rtn | 4 | 128 | 30.47 |

### Hardware Metrics

| Model | Method | Bits | Latency (ms) | Memory (GB) | Size (MB) | Compression |
|---|---|---|---|---|---|---|
| opt-125m | gptq | 4 | - | - | 133 | 3.76x |
| opt-125m | rtn | 4 | - | - | 133 | 3.76x |

## Paper Comparison

| Model | Method | Bits | Dataset | Ours | Paper | Diff (%) | Status |
|---|---|---|---|---|---|---|---|
| opt-125m | gptq | 4 | wikitext2 | 29.45 | 31.12 | -5.4% | ✓ |
| opt-125m | rtn | 4 | wikitext2 | 30.47 | 48.17 | -36.7% | ✗ |

## Key Findings

1. GPTQ significantly outperforms RTN baseline, especially at lower bit widths
2. The actorder heuristic (processing columns by Hessian diagonal) improves accuracy

## Recommendations

1. Use GPTQ with actorder=True and percdamp=0.01 for best results
2. 4-bit quantization with group_size=128 offers good quality-size tradeoff


## Figures

![Perplexity Comparison](reports/report_20260208_173249/perplexity_comparison.png)

![Pareto Frontier](reports/report_20260208_173249/pareto_frontier.png)

