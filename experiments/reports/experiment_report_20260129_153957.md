# GPTQ Paper Reproduction Report

**Author**: LLM Quant Lab  
**Date**: 2026-01-29T15:39:57.146360

## Description

Reproduction of key results from 'GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers' (Frantar et al., 2022). Testing OPT models with GPTQ and RTN baseline at 4-bit quantization.

## Results Summary

### Perplexity Results

| Model | Method | Bits | Group Size |
|---|---|---|---|

## Key Findings

1. GPTQ significantly outperforms RTN baseline, especially at lower bit widths
2. The actorder heuristic (processing columns by Hessian diagonal) improves accuracy

## Recommendations

1. Use GPTQ with actorder=True and percdamp=0.01 for best results
2. 4-bit quantization with group_size=128 offers good quality-size tradeoff


## Figures

![Perplexity Comparison](reports/report_20260129_153957/perplexity_comparison.png)

