"""Paper reproduction tracking and validation.

This module provides tools for reproducing and validating results
from quantization papers (GPTQ, SmoothQuant, AWQ, etc.).

All reference numbers are extracted directly from the original paper PDFs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Paper Results Database
# ============================================================================

@dataclass
class PaperResult:
    """A single result from a paper."""
    
    model: str
    method: str
    bit_width: int
    dataset: str
    metric_name: str
    value: float
    table_ref: str | None = None  # e.g., "Table 3"
    notes: str | None = None


@dataclass
class PaperReproductionSpec:
    """Specification for reproducing a paper's results."""
    
    paper_id: str
    title: str
    arxiv_id: str
    
    models: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    bit_widths: list[int] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    results: list[PaperResult] = field(default_factory=list)
    
    default_calib_dataset: str = "wikitext2"
    default_calib_samples: int = 128
    default_calib_seq_len: int = 2048
    default_group_size: int | None = 128
    default_symmetric: bool = True
    
    notes: str | None = None


# ============================================================================
# GPTQ Paper Specification (ICLR 2023)
# All numbers from Tables 3-5 of arXiv:2210.17323
# Calibration: C4, 128 samples, seq 2048
# No actorder, no grouping in default config (per-row quantization)
# ============================================================================

GPTQ_PAPER = PaperReproductionSpec(
    paper_id="gptq",
    title="GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers",
    arxiv_id="2210.17323",
    
    models=[
        "facebook/opt-125m",
        "facebook/opt-350m",
        "facebook/opt-1.3b",
        "facebook/opt-2.7b",
        "facebook/opt-6.7b",
        "facebook/opt-13b",
        "facebook/opt-30b",
        "facebook/opt-66b",
        "facebook/opt-175b",
        "bigscience/bloom-560m",
        "bigscience/bloom-1b1",
        "bigscience/bloom-1b7",
        "bigscience/bloom-3b",
        "bigscience/bloom-7b1",
        "bigscience/bloom",
    ],
    
    methods=["gptq", "rtn"],
    bit_widths=[2, 3, 4],
    datasets=["wikitext2", "ptb", "c4", "lambada"],
    
    results=[
        # === Table 3: OPT WikiText-2 Perplexity ===
        # FP16 baselines
        PaperResult("facebook/opt-125m", "fp16", 16, "wikitext2", "perplexity", 27.65, "Table 3"),
        PaperResult("facebook/opt-350m", "fp16", 16, "wikitext2", "perplexity", 22.00, "Table 3"),
        PaperResult("facebook/opt-1.3b", "fp16", 16, "wikitext2", "perplexity", 14.63, "Table 3"),
        PaperResult("facebook/opt-2.7b", "fp16", 16, "wikitext2", "perplexity", 12.47, "Table 3"),
        PaperResult("facebook/opt-6.7b", "fp16", 16, "wikitext2", "perplexity", 10.86, "Table 3"),
        PaperResult("facebook/opt-13b", "fp16", 16, "wikitext2", "perplexity", 10.13, "Table 3"),
        PaperResult("facebook/opt-30b", "fp16", 16, "wikitext2", "perplexity", 9.56, "Table 3"),
        PaperResult("facebook/opt-66b", "fp16", 16, "wikitext2", "perplexity", 9.34, "Table 3"),
        PaperResult("facebook/opt-175b", "fp16", 16, "wikitext2", "perplexity", 8.34, "Table 3"),
        # GPTQ 4-bit (no grouping, per-row)
        PaperResult("facebook/opt-125m", "gptq", 4, "wikitext2", "perplexity", 31.12, "Table 3"),
        PaperResult("facebook/opt-350m", "gptq", 4, "wikitext2", "perplexity", 24.24, "Table 3"),
        PaperResult("facebook/opt-1.3b", "gptq", 4, "wikitext2", "perplexity", 15.47, "Table 3"),
        PaperResult("facebook/opt-2.7b", "gptq", 4, "wikitext2", "perplexity", 12.87, "Table 3"),
        PaperResult("facebook/opt-6.7b", "gptq", 4, "wikitext2", "perplexity", 11.39, "Table 3"),
        PaperResult("facebook/opt-13b", "gptq", 4, "wikitext2", "perplexity", 10.31, "Table 3"),
        PaperResult("facebook/opt-30b", "gptq", 4, "wikitext2", "perplexity", 9.63, "Table 3"),
        PaperResult("facebook/opt-66b", "gptq", 4, "wikitext2", "perplexity", 9.55, "Table 3"),
        PaperResult("facebook/opt-175b", "gptq", 4, "wikitext2", "perplexity", 8.37, "Table 3"),
        # GPTQ 3-bit (no grouping)
        PaperResult("facebook/opt-125m", "gptq", 3, "wikitext2", "perplexity", 53.85, "Table 3"),
        PaperResult("facebook/opt-350m", "gptq", 3, "wikitext2", "perplexity", 33.79, "Table 3"),
        PaperResult("facebook/opt-1.3b", "gptq", 3, "wikitext2", "perplexity", 20.97, "Table 3"),
        PaperResult("facebook/opt-2.7b", "gptq", 3, "wikitext2", "perplexity", 16.88, "Table 3"),
        PaperResult("facebook/opt-6.7b", "gptq", 3, "wikitext2", "perplexity", 14.86, "Table 3"),
        PaperResult("facebook/opt-13b", "gptq", 3, "wikitext2", "perplexity", 11.61, "Table 3"),
        PaperResult("facebook/opt-30b", "gptq", 3, "wikitext2", "perplexity", 10.27, "Table 3"),
        PaperResult("facebook/opt-175b", "gptq", 3, "wikitext2", "perplexity", 8.68, "Table 3"),
        # RTN 4-bit baselines
        PaperResult("facebook/opt-125m", "rtn", 4, "wikitext2", "perplexity", 37.28, "Table 3"),
        PaperResult("facebook/opt-350m", "rtn", 4, "wikitext2", "perplexity", 25.94, "Table 3"),
        PaperResult("facebook/opt-1.3b", "rtn", 4, "wikitext2", "perplexity", 48.17, "Table 3"),
        PaperResult("facebook/opt-2.7b", "rtn", 4, "wikitext2", "perplexity", 16.92, "Table 3"),
        PaperResult("facebook/opt-6.7b", "rtn", 4, "wikitext2", "perplexity", 12.10, "Table 3"),
        PaperResult("facebook/opt-13b", "rtn", 4, "wikitext2", "perplexity", 11.32, "Table 3"),
        PaperResult("facebook/opt-30b", "rtn", 4, "wikitext2", "perplexity", 10.98, "Table 3"),
        PaperResult("facebook/opt-175b", "rtn", 4, "wikitext2", "perplexity", 10.54, "Table 3"),

        # === Table 4: BLOOM WikiText-2 Perplexity ===
        PaperResult("bigscience/bloom-560m", "fp16", 16, "wikitext2", "perplexity", 22.42, "Table 4"),
        PaperResult("bigscience/bloom-1b1", "fp16", 16, "wikitext2", "perplexity", 17.69, "Table 4"),
        PaperResult("bigscience/bloom-1b7", "fp16", 16, "wikitext2", "perplexity", 15.39, "Table 4"),
        PaperResult("bigscience/bloom-3b", "fp16", 16, "wikitext2", "perplexity", 13.48, "Table 4"),
        PaperResult("bigscience/bloom-7b1", "fp16", 16, "wikitext2", "perplexity", 11.37, "Table 4"),
        PaperResult("bigscience/bloom", "fp16", 16, "wikitext2", "perplexity", 8.11, "Table 4"),
        PaperResult("bigscience/bloom-560m", "gptq", 4, "wikitext2", "perplexity", 24.03, "Table 4"),
        PaperResult("bigscience/bloom-1b1", "gptq", 4, "wikitext2", "perplexity", 19.05, "Table 4"),
        PaperResult("bigscience/bloom-1b7", "gptq", 4, "wikitext2", "perplexity", 16.48, "Table 4"),
        PaperResult("bigscience/bloom-3b", "gptq", 4, "wikitext2", "perplexity", 14.20, "Table 4"),
        PaperResult("bigscience/bloom-7b1", "gptq", 4, "wikitext2", "perplexity", 11.73, "Table 4"),
        PaperResult("bigscience/bloom", "gptq", 4, "wikitext2", "perplexity", 8.21, "Table 4"),

        # === Table 5: OPT-175B & BLOOM-176B multi-dataset (selected) ===
        PaperResult("facebook/opt-175b", "fp16", 16, "ptb", "perplexity", 12.01, "Table 5"),
        PaperResult("facebook/opt-175b", "gptq", 4, "ptb", "perplexity", 12.26, "Table 5"),
        PaperResult("facebook/opt-175b", "fp16", 16, "c4", "perplexity", 10.13, "Table 5"),
        PaperResult("facebook/opt-175b", "gptq", 4, "c4", "perplexity", 10.28, "Table 5"),
        PaperResult("facebook/opt-175b", "fp16", 16, "lambada", "accuracy", 75.59, "Table 5"),
        PaperResult("facebook/opt-175b", "gptq", 4, "lambada", "accuracy", 76.80, "Table 5"),
        PaperResult("facebook/opt-175b", "gptq", 3, "lambada", "accuracy", 76.19, "Table 5"),
        PaperResult("facebook/opt-175b", "rtn", 4, "lambada", "accuracy", 71.34, "Table 5"),

        # === Table 13: OPT LAMBADA Accuracy ===
        PaperResult("facebook/opt-125m", "fp16", 16, "lambada", "accuracy", 39.16, "Table 13"),
        PaperResult("facebook/opt-125m", "rtn", 4, "lambada", "accuracy", 18.34, "Table 13"),
        PaperResult("facebook/opt-125m", "gptq", 4, "lambada", "accuracy", 34.74, "Table 13"),
        PaperResult("facebook/opt-125m", "gptq", 3, "lambada", "accuracy", 13.93, "Table 13"),
        PaperResult("facebook/opt-6.7b", "fp16", 16, "lambada", "accuracy", 68.72, "Table 13"),
        PaperResult("facebook/opt-6.7b", "rtn", 4, "lambada", "accuracy", 64.66, "Table 13"),
        PaperResult("facebook/opt-6.7b", "gptq", 4, "lambada", "accuracy", 66.37, "Table 13"),
        PaperResult("facebook/opt-6.7b", "gptq", 3, "lambada", "accuracy", 54.98, "Table 13"),
        PaperResult("facebook/opt-13b", "fp16", 16, "lambada", "accuracy", 70.23, "Table 13"),
        PaperResult("facebook/opt-13b", "rtn", 4, "lambada", "accuracy", 67.38, "Table 13"),
        PaperResult("facebook/opt-13b", "gptq", 4, "lambada", "accuracy", 69.12, "Table 13"),
        PaperResult("facebook/opt-13b", "gptq", 3, "lambada", "accuracy", 64.18, "Table 13"),
        PaperResult("facebook/opt-30b", "fp16", 16, "lambada", "accuracy", 72.39, "Table 13"),
        PaperResult("facebook/opt-30b", "rtn", 4, "lambada", "accuracy", 70.48, "Table 13"),
        PaperResult("facebook/opt-30b", "gptq", 4, "lambada", "accuracy", 72.40, "Table 13"),
        PaperResult("facebook/opt-30b", "gptq", 3, "lambada", "accuracy", 69.69, "Table 13"),
    ],
    
    default_calib_dataset="c4",
    default_calib_samples=128,
    default_calib_seq_len=2048,
    default_group_size=None,
    default_symmetric=False,
    notes="""\
    GPTQ paper settings:
    - Calibration: C4 (NOT WikiText-2), 128 samples, seq 2048
    - percdamp=0.01, blocksize=128
    - No actorder (fixed left-to-right column order in original paper)
    - No grouping (per-row quantization) in default experiments
    - actorder and group_size=128 were added later by AutoGPTQ community
    - OPT-66B has anomalous RTN results due to dead units in early layers
    """,
)


# ============================================================================
# SmoothQuant Paper Specification (ICML 2023)
# All numbers from Tables 3, 5, 6, 7 of arXiv:2211.10438
# Calibration: The Pile, 512 samples
# Alpha varies by model family
# ============================================================================

SMOOTHQUANT_PAPER = PaperReproductionSpec(
    paper_id="smoothquant",
    title="SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models",
    arxiv_id="2211.10438",
    
    models=[
        "facebook/opt-175b",
        "facebook/opt-iml-30b",
        "meta-llama/Llama-2-7b-hf",
        "meta-llama/Llama-2-13b-hf",
        "meta-llama/Llama-2-70b-hf",
        "tiiuae/falcon-7b",
        "tiiuae/falcon-40b",
        "mistralai/Mistral-7B-v0.1",
        "mistralai/Mixtral-8x7B-v0.1",
    ],
    
    methods=["smoothquant", "fp16", "w8a8_naive", "llmint8"],
    bit_widths=[8],
    datasets=["wikitext2", "lambada", "hellaswag", "piqa", "winogrande"],
    
    results=[
        # === Table 3: OPT-175B full benchmark (7 zero-shot tasks + WikiText PPL) ===
        PaperResult("facebook/opt-175b", "fp16", 16, "wikitext2", "perplexity", 10.99, "Table 3"),
        PaperResult("facebook/opt-175b", "fp16", 16, "lambada", "accuracy", 74.7, "Table 3"),
        PaperResult("facebook/opt-175b", "fp16", 16, "hellaswag", "accuracy", 59.3, "Table 3"),
        PaperResult("facebook/opt-175b", "fp16", 16, "piqa", "accuracy", 79.7, "Table 3"),
        PaperResult("facebook/opt-175b", "fp16", 16, "winogrande", "accuracy", 72.6, "Table 3"),
        PaperResult("facebook/opt-175b", "smoothquant_o1", 8, "wikitext2", "perplexity", 11.11, "Table 3"),
        PaperResult("facebook/opt-175b", "smoothquant_o2", 8, "wikitext2", "perplexity", 11.14, "Table 3"),
        PaperResult("facebook/opt-175b", "smoothquant_o3", 8, "wikitext2", "perplexity", 11.17, "Table 3"),
        PaperResult("facebook/opt-175b", "smoothquant_o3", 8, "lambada", "accuracy", 74.6, "Table 3"),
        PaperResult("facebook/opt-175b", "smoothquant_o3", 8, "hellaswag", "accuracy", 58.9, "Table 3"),
        PaperResult("facebook/opt-175b", "smoothquant_o3", 8, "piqa", "accuracy", 79.7, "Table 3"),
        PaperResult("facebook/opt-175b", "smoothquant_o3", 8, "winogrande", "accuracy", 71.2, "Table 3"),
        PaperResult("facebook/opt-175b", "llmint8", 8, "wikitext2", "perplexity", 11.10, "Table 3"),
        PaperResult("facebook/opt-175b", "w8a8_naive", 8, "wikitext2", "perplexity", 93080.0, "Table 3"),

        # === Table 5: OPT-IML-30B (instruction-tuned) ===
        PaperResult("facebook/opt-iml-30b", "fp16", 16, "lambada", "accuracy", 69.12, "Table 5"),
        PaperResult("facebook/opt-iml-30b", "fp16", 16, "wikitext2", "perplexity", 14.26, "Table 5"),
        PaperResult("facebook/opt-iml-30b", "smoothquant_o3", 8, "lambada", "accuracy", 69.77, "Table 5"),
        PaperResult("facebook/opt-iml-30b", "smoothquant_o3", 8, "wikitext2", "perplexity", 14.37, "Table 5"),
        PaperResult("facebook/opt-iml-30b", "llmint8", 8, "lambada", "accuracy", 69.14, "Table 5"),
        PaperResult("facebook/opt-iml-30b", "llmint8", 8, "wikitext2", "perplexity", 14.27, "Table 5"),

        # === Table 6: LLaMA-1 WikiText-2 PPL (alpha=0.8, seq 512) ===
        PaperResult("huggyllama/llama-7b", "fp16", 16, "wikitext2", "perplexity", 11.51, "Table 6"),
        PaperResult("huggyllama/llama-7b", "smoothquant", 8, "wikitext2", "perplexity", 11.56, "Table 6"),
        PaperResult("huggyllama/llama-13b", "fp16", 16, "wikitext2", "perplexity", 10.05, "Table 6"),
        PaperResult("huggyllama/llama-13b", "smoothquant", 8, "wikitext2", "perplexity", 10.08, "Table 6"),

        # === Table 7: Llama-2, Falcon, Mistral, Mixtral WikiText-2 PPL (seq 2048) ===
        PaperResult("meta-llama/Llama-2-7b-hf", "fp16", 16, "wikitext2", "perplexity", 5.474, "Table 7"),
        PaperResult("meta-llama/Llama-2-7b-hf", "smoothquant", 8, "wikitext2", "perplexity", 5.515, "Table 7", "alpha=0.85"),
        PaperResult("meta-llama/Llama-2-13b-hf", "fp16", 16, "wikitext2", "perplexity", 4.950, "Table 7"),
        PaperResult("meta-llama/Llama-2-13b-hf", "smoothquant", 8, "wikitext2", "perplexity", 4.929, "Table 7", "alpha=0.85"),
        PaperResult("meta-llama/Llama-2-70b-hf", "fp16", 16, "wikitext2", "perplexity", 3.320, "Table 7"),
        PaperResult("meta-llama/Llama-2-70b-hf", "smoothquant", 8, "wikitext2", "perplexity", 3.359, "Table 7", "alpha=0.9"),
        PaperResult("tiiuae/falcon-7b", "fp16", 16, "wikitext2", "perplexity", 6.590, "Table 7"),
        PaperResult("tiiuae/falcon-7b", "smoothquant", 8, "wikitext2", "perplexity", 6.629, "Table 7", "alpha=0.6"),
        PaperResult("tiiuae/falcon-40b", "fp16", 16, "wikitext2", "perplexity", 5.228, "Table 7"),
        PaperResult("tiiuae/falcon-40b", "smoothquant", 8, "wikitext2", "perplexity", 5.255, "Table 7", "alpha=0.7"),
        PaperResult("mistralai/Mistral-7B-v0.1", "fp16", 16, "wikitext2", "perplexity", 5.253, "Table 7"),
        PaperResult("mistralai/Mistral-7B-v0.1", "smoothquant", 8, "wikitext2", "perplexity", 5.277, "Table 7", "alpha=0.8"),
        PaperResult("mistralai/Mixtral-8x7B-v0.1", "fp16", 16, "wikitext2", "perplexity", 3.842, "Table 7"),
        PaperResult("mistralai/Mixtral-8x7B-v0.1", "smoothquant", 8, "wikitext2", "perplexity", 3.893, "Table 7", "alpha=0.8"),
    ],
    
    default_calib_dataset="pile",
    default_calib_samples=512,
    default_calib_seq_len=2048,
    default_group_size=None,
    default_symmetric=True,
    notes="""\
    SmoothQuant paper settings:
    - Calibration: The Pile (NOT WikiText-2), 512 samples
    - Alpha varies by model: 0.5 (OPT/BLOOM), 0.6 (Falcon-7B), 0.7 (Falcon-40B),
      0.75 (GLM-130B), 0.8 (LLaMA-1, Mistral, Mixtral), 0.85 (Llama-2-7B/13B),
      0.9 (Llama-2-70B)
    - O1: per-tensor weight, per-token dynamic activation
    - O2: per-tensor weight, per-tensor dynamic activation
    - O3: per-tensor weight, per-tensor static activation (most efficient)
    - All linear layers + BMM quantized to INT8; elementwise ops stay FP16
    """,
)


# ============================================================================
# AWQ Paper Specification (MLSys 2024)
# All numbers from Tables 3-5, 8 of arXiv:2306.00978
# Calibration: The Pile, ~16 sequences of 2048 tokens, group_size=128
# ============================================================================

AWQ_PAPER = PaperReproductionSpec(
    paper_id="awq",
    title="AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration",
    arxiv_id="2306.00978",
    
    models=[
        "meta-llama/Llama-2-7b-hf",
        "meta-llama/Llama-2-13b-hf",
        "meta-llama/Llama-2-70b-hf",
        "huggyllama/llama-7b",
        "huggyllama/llama-13b",
        "huggyllama/llama-30b",
        "huggyllama/llama-65b",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "mistralai/Mistral-7B-Instruct-v0.2",
    ],
    
    methods=["awq", "gptq", "gptq_r", "rtn"],
    bit_widths=[3, 4],
    datasets=["wikitext2", "gsm8k"],
    
    results=[
        # === Table 4: INT4-g128 WikiText-2 PPL ===
        PaperResult("meta-llama/Llama-2-7b-hf", "fp16", 16, "wikitext2", "perplexity", 5.47, "Table 4"),
        PaperResult("meta-llama/Llama-2-7b-hf", "awq", 4, "wikitext2", "perplexity", 5.60, "Table 4"),
        PaperResult("meta-llama/Llama-2-7b-hf", "gptq", 4, "wikitext2", "perplexity", 5.69, "Table 4"),
        PaperResult("meta-llama/Llama-2-7b-hf", "rtn", 4, "wikitext2", "perplexity", 5.73, "Table 4"),
        PaperResult("meta-llama/Llama-2-13b-hf", "fp16", 16, "wikitext2", "perplexity", 4.88, "Table 4"),
        PaperResult("meta-llama/Llama-2-13b-hf", "awq", 4, "wikitext2", "perplexity", 4.97, "Table 4"),
        PaperResult("meta-llama/Llama-2-70b-hf", "fp16", 16, "wikitext2", "perplexity", 3.32, "Table 4"),
        PaperResult("meta-llama/Llama-2-70b-hf", "awq", 4, "wikitext2", "perplexity", 3.41, "Table 4"),
        PaperResult("huggyllama/llama-7b", "fp16", 16, "wikitext2", "perplexity", 5.68, "Table 4"),
        PaperResult("huggyllama/llama-7b", "awq", 4, "wikitext2", "perplexity", 5.78, "Table 4"),
        PaperResult("huggyllama/llama-13b", "fp16", 16, "wikitext2", "perplexity", 5.09, "Table 4"),
        PaperResult("huggyllama/llama-13b", "awq", 4, "wikitext2", "perplexity", 5.19, "Table 4"),
        PaperResult("huggyllama/llama-30b", "fp16", 16, "wikitext2", "perplexity", 4.10, "Table 4"),
        PaperResult("huggyllama/llama-30b", "awq", 4, "wikitext2", "perplexity", 4.21, "Table 4"),
        PaperResult("huggyllama/llama-65b", "fp16", 16, "wikitext2", "perplexity", 3.53, "Table 4"),
        PaperResult("huggyllama/llama-65b", "awq", 4, "wikitext2", "perplexity", 3.62, "Table 4"),
        # INT3-g128
        PaperResult("meta-llama/Llama-2-7b-hf", "awq", 3, "wikitext2", "perplexity", 6.24, "Table 4"),
        PaperResult("meta-llama/Llama-2-13b-hf", "awq", 3, "wikitext2", "perplexity", 5.32, "Table 4"),
        PaperResult("meta-llama/Llama-2-70b-hf", "awq", 3, "wikitext2", "perplexity", 3.74, "Table 4"),
        # Table 5: Mistral/Mixtral
        PaperResult("mistralai/Mixtral-8x7B-Instruct-v0.1", "fp16", 16, "wikitext2", "perplexity", 5.94, "Table 5"),
        PaperResult("mistralai/Mixtral-8x7B-Instruct-v0.1", "awq", 4, "wikitext2", "perplexity", 6.05, "Table 5"),
        PaperResult("mistralai/Mistral-7B-Instruct-v0.2", "fp16", 16, "wikitext2", "perplexity", 4.14, "Table 5"),
        PaperResult("mistralai/Mistral-7B-Instruct-v0.2", "awq", 4, "wikitext2", "perplexity", 4.30, "Table 5"),
        # Table 8: GSM8K INT4-g128
        PaperResult("meta-llama/Llama-2-7b-hf", "fp16", 16, "gsm8k", "accuracy", 13.87, "Table 8"),
        PaperResult("meta-llama/Llama-2-7b-hf", "awq", 4, "gsm8k", "accuracy", 13.57, "Table 8"),
        PaperResult("meta-llama/Llama-2-13b-hf", "fp16", 16, "gsm8k", "accuracy", 26.16, "Table 8"),
        PaperResult("meta-llama/Llama-2-13b-hf", "awq", 4, "gsm8k", "accuracy", 25.25, "Table 8"),
        PaperResult("meta-llama/Llama-2-70b-hf", "fp16", 16, "gsm8k", "accuracy", 56.41, "Table 8"),
        PaperResult("meta-llama/Llama-2-70b-hf", "awq", 4, "gsm8k", "accuracy", 56.40, "Table 8"),
    ],
    
    default_calib_dataset="pile",
    default_calib_samples=16,
    default_calib_seq_len=2048,
    default_group_size=128,
    default_symmetric=False,
    notes="""\
    AWQ paper settings:
    - Calibration: The Pile (NOT WikiText-2/C4), ~16 sequences of 2048 tokens
    - group_size=128, weight-only (W4A16 / W3A16)
    - Alpha grid search: 20 values in [0,1], MSE-based weight clipping
    - No backpropagation required
    - Paper does NOT report C4/PTB PPL or standard zero-shot accuracy tables
    """,
)


# ============================================================================
# LLM.int8() Paper Specification (NeurIPS 2022)
# Numbers from Table 1 of the paper
# No calibration required (zero-shot method)
# ============================================================================

LLMINT8_PAPER = PaperReproductionSpec(
    paper_id="llmint8",
    title="LLM.int8(): 8-bit Matrix Multiplication for Transformers at Scale",
    arxiv_id="2208.07339",
    
    models=[
        "facebook/opt-125m",
        "facebook/opt-1.3b",
        "facebook/opt-2.7b",
        "facebook/opt-6.7b",
        "facebook/opt-13b",
    ],
    
    methods=["llmint8", "fp16", "fp32", "int8_absmax"],
    bit_widths=[8],
    datasets=["c4"],
    
    results=[
        # === Table 1: C4 Validation Perplexity (fairseq dense transformers) ===
        # Paper reports baselines as FP32; listed as fp16 since our baselines run fp16
        # (OPT FP16 ≈ FP32 perplexity — negligible difference)
        PaperResult("facebook/opt-125m", "fp16", 16, "c4", "perplexity", 25.65, "Table 1"),
        PaperResult("facebook/opt-1.3b", "fp16", 16, "c4", "perplexity", 15.91, "Table 1"),
        PaperResult("facebook/opt-2.7b", "fp16", 16, "c4", "perplexity", 14.43, "Table 1"),
        PaperResult("facebook/opt-6.7b", "fp16", 16, "c4", "perplexity", 13.30, "Table 1"),
        PaperResult("facebook/opt-13b", "fp16", 16, "c4", "perplexity", 12.45, "Table 1"),
        PaperResult("facebook/opt-125m", "llmint8", 8, "c4", "perplexity", 25.83, "Table 1", "absmax variant"),
        PaperResult("facebook/opt-1.3b", "llmint8", 8, "c4", "perplexity", 15.93, "Table 1", "absmax variant"),
        PaperResult("facebook/opt-2.7b", "llmint8", 8, "c4", "perplexity", 14.44, "Table 1", "absmax variant"),
        PaperResult("facebook/opt-6.7b", "llmint8", 8, "c4", "perplexity", 13.24, "Table 1", "absmax variant"),
        PaperResult("facebook/opt-13b", "llmint8", 8, "c4", "perplexity", 12.45, "Table 1", "absmax variant"),
        PaperResult("facebook/opt-125m", "int8_absmax", 8, "c4", "perplexity", 87.76, "Table 1"),
        PaperResult("facebook/opt-13b", "int8_absmax", 8, "c4", "perplexity", 19.08, "Table 1"),
    ],
    
    default_calib_dataset="c4",
    default_calib_samples=0,
    default_calib_seq_len=2048,
    default_group_size=None,
    default_symmetric=True,
    notes="""\
    LLM.int8() settings:
    - No calibration data required (zero-shot method)
    - Outlier threshold: 6.0 (features with magnitude >= 6.0)
    - ~0.1% outlier features multiplied in FP16, rest in INT8
    - Vector-wise absmax quantization for non-outlier dimensions
    - Net speedup only at >= 13B parameters due to decomposition overhead
    - Perplexity models are fairseq dense transformers (not OPT) evaluated on C4
    """,
)


# ============================================================================
# ZeroQuant Paper Specification (NeurIPS 2022)
# Numbers from Tables 4, 5, 7 of the paper
# Uses internal GPT-3 style models (not public OPT/BLOOM)
# ============================================================================

ZEROQUANT_PAPER = PaperReproductionSpec(
    paper_id="zeroquant",
    title="ZeroQuant: Efficient and Affordable Post-Training Quantization for Large-Scale Transformers",
    arxiv_id="2206.01861",
    
    models=[
        "EleutherAI/gpt-j-6b",
        "EleutherAI/gpt-neox-20b",
    ],
    
    methods=["zeroquant", "fp16"],
    bit_widths=[8],
    datasets=["wikitext2", "ptb"],
    
    results=[
        # === Table 7: GPT-J 6B ===
        PaperResult("EleutherAI/gpt-j-6b", "fp16", 16, "wikitext2", "perplexity", 10.35, "Table 7"),
        PaperResult("EleutherAI/gpt-j-6b", "zeroquant", 8, "wikitext2", "perplexity", 10.51, "Table 7"),
        PaperResult("EleutherAI/gpt-j-6b", "fp16", 16, "ptb", "perplexity", 20.47, "Table 7"),
        PaperResult("EleutherAI/gpt-j-6b", "zeroquant", 8, "ptb", "perplexity", 20.97, "Table 7"),
        # === Table 8: GPT-NeoX 20B ===
        PaperResult("EleutherAI/gpt-neox-20b", "fp16", 16, "lambada", "accuracy", 71.7, "Table 8"),
        PaperResult("EleutherAI/gpt-neox-20b", "zeroquant", 8, "lambada", "accuracy", 71.9, "Table 8"),
    ],
    
    default_calib_dataset="c4",
    default_calib_samples=8,
    default_calib_seq_len=2048,
    default_group_size=128,
    default_symmetric=True,
    notes="""\
    ZeroQuant settings:
    - Weight: group-wise quantization (48-128 groups)
    - Activation: token-wise dynamic quantization (no calibration cost)
    - Optional LKD (Layer-by-layer Knowledge Distillation): LR=5e-6, 1600 iters
    - GPT-3 350M/1.3B results use internal models not publicly available
    - GPT-J 6B and GPT-NeoX 20B are the reproducible targets
    """,
)


# ============================================================================
# ParetoQ Paper Specification (2025)
# Numbers from Table 1 of arXiv:2502.02631
# QAT method (not PTQ) -- requires finetuning
# ============================================================================

PARETOQ_PAPER = PaperReproductionSpec(
    paper_id="paretoq",
    title="ParetoQ: Improving Scaling Laws in Extremely Low-bit LLM Quantization",
    arxiv_id="2502.02631",
    
    models=[
        "meta-llama/Llama-3.1-8B",
        "meta-llama/Llama-3.2-3B",
        "meta-llama/Llama-3.2-1B",
    ],
    
    methods=["paretoq", "fp16", "gptq", "llm_qat"],
    bit_widths=[1, 2, 3, 4],
    datasets=["wikitext2", "arc_easy", "arc_challenge", "piqa", "hellaswag", "winogrande"],
    
    results=[
        # === Table 1: LLaMA-3 8B at extreme low-bit ===
        PaperResult("meta-llama/Llama-3.1-8B", "fp16", 16, "wikitext2", "perplexity", 6.15, "Table 1"),
        PaperResult("meta-llama/Llama-3.1-8B", "paretoq", 2, "wikitext2", "perplexity", 8.0, "Table 1"),
        PaperResult("meta-llama/Llama-3.1-8B", "paretoq", 3, "wikitext2", "perplexity", 7.0, "Table 1"),
        PaperResult("meta-llama/Llama-3.1-8B", "paretoq", 4, "wikitext2", "perplexity", 6.8, "Table 1"),
        PaperResult("meta-llama/Llama-3.1-8B", "gptq", 2, "wikitext2", "perplexity", 160.0, "Table 1"),
    ],
    
    default_calib_dataset="c4",
    default_calib_samples=128,
    default_calib_seq_len=2048,
    default_group_size=None,
    default_symmetric=True,
    notes="""\
    ParetoQ is a QAT method (NOT PTQ). Requires finetuning from pre-trained weights.
    - Binary/Ternary/2-bit: 120K iterations, LR 2e-5, AdamW
    - 3-bit/4-bit: 40K iterations, LR 1e-5
    - Cosine LR decay, all weights except embedding and output layers
    - Cannot be run through standard PTQ pipeline
    """,
)


# ============================================================================
# BitNet Paper Specifications (QAT from scratch)
# Numbers from Table 3 of BitNet paper, Tables 1-2 of BitNet b1.58 paper
# ============================================================================

BITNET_PAPER = PaperReproductionSpec(
    paper_id="bitnet",
    title="BitNet / BitNet b1.58: 1-bit and 1.58-bit LLMs",
    arxiv_id="2310.11453",
    
    models=[],
    methods=["bitnet", "bitnet_b158"],
    bit_widths=[1, 2],
    datasets=["wikitext2", "arc_easy", "arc_challenge", "hellaswag", "piqa", "winogrande"],
    
    results=[
        # === BitNet b1.58 Table 1: Perplexity ===
        PaperResult("bitnet-b158-700m", "bitnet_b158", 2, "wikitext2", "perplexity", 12.87, "b1.58 Table 1"),
        PaperResult("bitnet-b158-1.3b", "bitnet_b158", 2, "wikitext2", "perplexity", 11.29, "b1.58 Table 1"),
        PaperResult("bitnet-b158-3b", "bitnet_b158", 2, "wikitext2", "perplexity", 9.91, "b1.58 Table 1"),
        # FP16 LLaMA baselines from same paper
        PaperResult("llama-700m", "fp16", 16, "wikitext2", "perplexity", 12.33, "b1.58 Table 1"),
        PaperResult("llama-1.3b", "fp16", 16, "wikitext2", "perplexity", 11.25, "b1.58 Table 1"),
        PaperResult("llama-3b", "fp16", 16, "wikitext2", "perplexity", 10.04, "b1.58 Table 1"),
    ],
    
    default_calib_dataset="c4",
    default_calib_samples=0,
    default_calib_seq_len=2048,
    default_group_size=None,
    default_symmetric=True,
    notes="""\
    BitNet family is QAT from scratch -- NOT post-training quantization.
    - BitNet: binary weights {-1, +1}, 8-bit activations
    - BitNet b1.58: ternary weights {-1, 0, +1}, 8-bit activations
    - Cannot be reproduced through standard PTQ pipeline
    - Reference numbers are for models trained from scratch by Microsoft
    """,
)


# ============================================================================
# All Paper Specs Registry
# ============================================================================

ALL_PAPER_SPECS: dict[str, PaperReproductionSpec] = {
    "gptq": GPTQ_PAPER,
    "smoothquant": SMOOTHQUANT_PAPER,
    "awq": AWQ_PAPER,
    "llmint8": LLMINT8_PAPER,
    "zeroquant": ZEROQUANT_PAPER,
    "paretoq": PARETOQ_PAPER,
    "bitnet": BITNET_PAPER,
}


# ============================================================================
# Paper Reproduction Tracker
# ============================================================================

class PaperReproductionTracker:
    """Tracks progress and validates paper reproduction."""
    
    def __init__(self, paper_spec: PaperReproductionSpec):
        self.spec = paper_spec
        self.results: dict[str, dict[str, Any]] = {}
        self.comparisons: list[dict[str, Any]] = []
    
    def get_expected_result(
        self,
        model: str,
        method: str,
        bit_width: int,
        dataset: str,
        metric_name: str = "perplexity",
    ) -> PaperResult | None:
        for result in self.spec.results:
            if (result.model == model and
                result.method == method and
                result.bit_width == bit_width and
                result.dataset == dataset and
                result.metric_name == metric_name):
                return result
        return None
    
    def record_result(
        self,
        model: str,
        method: str,
        bit_width: int,
        dataset: str,
        metric_name: str,
        value: float,
        extra_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = f"{model}:{method}:{bit_width}:{dataset}:{metric_name}"
        
        result_entry = {
            "model": model,
            "method": method,
            "bit_width": bit_width,
            "dataset": dataset,
            "metric_name": metric_name,
            "our_value": value,
            "extra_info": extra_info or {},
        }
        
        expected = self.get_expected_result(model, method, bit_width, dataset, metric_name)
        
        if expected:
            diff = value - expected.value
            if metric_name == "perplexity":
                rel_diff = diff / expected.value
                improvement = diff < 0
            else:
                rel_diff = (value - expected.value) / expected.value
                improvement = value > expected.value
            
            result_entry["paper_value"] = expected.value
            result_entry["absolute_diff"] = diff
            result_entry["relative_diff_pct"] = rel_diff * 100
            result_entry["table_ref"] = expected.table_ref
            result_entry["within_5pct"] = abs(rel_diff) <= 0.05
            result_entry["within_10pct"] = abs(rel_diff) <= 0.10
            result_entry["improvement"] = improvement
            
            status = "✓" if result_entry["within_10pct"] else "✗"
            logger.info(
                f"{status} {model} {method} {bit_width}-bit {dataset} {metric_name}: "
                f"{value:.2f} vs paper {expected.value:.2f} "
                f"(diff: {rel_diff*100:+.1f}%)"
            )
        else:
            logger.info(
                f"? {model} {method} {bit_width}-bit {dataset} {metric_name}: "
                f"{value:.2f} (no paper reference)"
            )
        
        self.results[key] = result_entry
        self.comparisons.append(result_entry)
        
        return result_entry
    
    def get_summary(self) -> dict[str, Any]:
        total = len(self.comparisons)
        with_reference = [c for c in self.comparisons if "paper_value" in c]
        within_5pct = sum(1 for c in with_reference if c.get("within_5pct", False))
        within_10pct = sum(1 for c in with_reference if c.get("within_10pct", False))
        
        return {
            "paper_id": self.spec.paper_id,
            "paper_title": self.spec.title,
            "total_experiments": total,
            "with_paper_reference": len(with_reference),
            "within_5pct": within_5pct,
            "within_10pct": within_10pct,
            "reproduction_rate_5pct": within_5pct / len(with_reference) if with_reference else 0,
            "reproduction_rate_10pct": within_10pct / len(with_reference) if with_reference else 0,
            "results": self.comparisons,
        }
    
    def generate_report(self) -> str:
        summary = self.get_summary()
        
        report = f"""# Paper Reproduction Report

## Paper Information
- **Title**: {self.spec.title}
- **ArXiv ID**: {self.spec.arxiv_id}
- **Paper ID**: {self.spec.paper_id}

## Summary
- Total experiments: {summary['total_experiments']}
- With paper reference: {summary['with_paper_reference']}
- Within 5% of paper: {summary['within_5pct']} ({summary['reproduction_rate_5pct']*100:.1f}%)
- Within 10% of paper: {summary['within_10pct']} ({summary['reproduction_rate_10pct']*100:.1f}%)

## Results

| Model | Method | Bits | Dataset | Metric | Ours | Paper | Diff (%) | Status |
|-------|--------|------|---------|--------|------|-------|----------|--------|
"""
        
        for r in sorted(self.comparisons, key=lambda x: (x["model"], x["method"], x["bit_width"])):
            model_short = r["model"].split("/")[-1]
            paper_val = r.get("paper_value", "-")
            diff_pct = r.get("relative_diff_pct", "-")
            
            if isinstance(paper_val, float):
                paper_str = f"{paper_val:.2f}"
            else:
                paper_str = str(paper_val)
            
            if isinstance(diff_pct, float):
                diff_str = f"{diff_pct:+.1f}%"
                status = "✓" if r.get("within_10pct", False) else "✗"
            else:
                diff_str = "-"
                status = "?"
            
            report += f"| {model_short} | {r['method']} | {r['bit_width']} | {r['dataset']} | {r['metric_name']} | {r['our_value']:.2f} | {paper_str} | {diff_str} | {status} |\n"
        
        if self.spec.notes:
            report += f"\n## Notes\n{self.spec.notes}\n"
        
        return report


# ============================================================================
# Convenience Classes
# ============================================================================

class GPTQReproduction(PaperReproductionTracker):
    def __init__(self):
        super().__init__(GPTQ_PAPER)
    
    @property
    def recommended_models(self) -> list[str]:
        return [
            "facebook/opt-125m",
            "facebook/opt-350m",
            "facebook/opt-1.3b",
            "facebook/opt-2.7b",
        ]
    
    @property
    def gptq_config(self) -> dict[str, Any]:
        """Config matching the original paper (no actorder, no grouping)."""
        return {
            "percdamp": 0.01,
            "blocksize": 128,
        }


class SmoothQuantReproduction(PaperReproductionTracker):
    def __init__(self):
        super().__init__(SMOOTHQUANT_PAPER)
    
    @property
    def recommended_models(self) -> list[str]:
        return [
            "meta-llama/Llama-2-7b-hf",
            "meta-llama/Llama-2-13b-hf",
            "tiiuae/falcon-7b",
            "mistralai/Mistral-7B-v0.1",
        ]
    
    @property
    def smoothquant_config(self) -> dict[str, Any]:
        return {
            "alpha": 0.5,
            "migrate_scale": True,
        }


class AWQReproduction(PaperReproductionTracker):
    def __init__(self):
        super().__init__(AWQ_PAPER)
    
    @property
    def recommended_models(self) -> list[str]:
        return [
            "meta-llama/Llama-2-7b-hf",
            "meta-llama/Llama-2-13b-hf",
            "huggyllama/llama-7b",
        ]
    
    @property
    def awq_config(self) -> dict[str, Any]:
        return {
            "group_size": 128,
            "trans": True,
            "trans_version": "v2",
            "weight_clip": True,
        }


# ============================================================================
# API / Frontend Helpers
# ============================================================================

_TRACKER_REGISTRY: dict[str, tuple[type[PaperReproductionTracker], str]] = {
    "gptq": (GPTQReproduction, "gptq_config"),
    "smoothquant": (SmoothQuantReproduction, "smoothquant_config"),
    "awq": (AWQReproduction, "awq_config"),
}


def get_reproduction_specs_for_api() -> list[dict[str, Any]]:
    """Return all paper specs as JSON-serializable dicts for the API/frontend."""
    specs = []
    for paper_id, spec in ALL_PAPER_SPECS.items():
        tracker_info = _TRACKER_REGISTRY.get(paper_id)
        if tracker_info:
            tracker_class, config_attr = tracker_info
            tracker = tracker_class()
            config = getattr(tracker, config_attr, None) or {}
        else:
            config = {}

        results = [
            {
                "model": r.model,
                "method": r.method,
                "bit_width": r.bit_width,
                "dataset": r.dataset,
                "metric_name": r.metric_name,
                "value": r.value,
                "table_ref": r.table_ref,
                "notes": r.notes,
            }
            for r in spec.results
        ]
        specs.append({
            "paper_id": spec.paper_id,
            "title": spec.title,
            "arxiv_id": spec.arxiv_id,
            "models": spec.models,
            "methods": spec.methods,
            "bit_widths": spec.bit_widths,
            "datasets": spec.datasets,
            "default_calib_dataset": spec.default_calib_dataset,
            "default_calib_samples": spec.default_calib_samples,
            "default_calib_seq_len": spec.default_calib_seq_len,
            "default_group_size": spec.default_group_size,
            "default_symmetric": spec.default_symmetric,
            "notes": (spec.notes or "").strip(),
            "config": config,
            "results": results,
        })
    return specs


def compare_with_paper_results(
    paper_id: str,
    our_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare results with paper's reported values."""
    if paper_id not in ALL_PAPER_SPECS:
        raise ValueError(f"Unknown paper: {paper_id}. Available: {list(ALL_PAPER_SPECS.keys())}")

    tracker_info = _TRACKER_REGISTRY.get(paper_id)
    if tracker_info:
        tracker = tracker_info[0]()
    else:
        tracker = PaperReproductionTracker(ALL_PAPER_SPECS[paper_id])

    for r in our_results:
        tracker.record_result(
            model=r["model"],
            method=r["method"],
            bit_width=r["bit_width"],
            dataset=r["dataset"],
            metric_name=r.get("metric_name", "perplexity"),
            value=r["value"],
        )
    
    return tracker.get_summary()
