#!/usr/bin/env python3
"""
Scientist Agent Analysis Runner — Opus 4.6 via Anthropic API.

Loads reproduction results, feeds full context to Claude Opus 4.6,
and iterates through deep analysis passes until insights are non-trivial.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]  # set in the environment; never hardcode
MODEL = "claude-sonnet-4-20250514"
API_URL = "https://api.anthropic.com/v1/messages"
MAX_TOKENS = 16000

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "reproduction_results.csv"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "scientist_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Anthropic API helper
# ---------------------------------------------------------------------------

def call_anthropic(
    system: str,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = MAX_TOKENS,
) -> str:
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": messages,
    }
    with httpx.Client(timeout=600) as client:
        resp = client.post(API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    blocks = data.get("content", [])
    return "\n".join(b["text"] for b in blocks if b["type"] == "text")


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def load_and_summarise_data() -> tuple[pd.DataFrame, str]:
    df = pd.read_csv(CSV_PATH)

    summary_parts = []
    summary_parts.append("=" * 80)
    summary_parts.append("FULL REPRODUCTION RESULTS DATASET")
    summary_parts.append("=" * 80)
    summary_parts.append(f"Total rows: {len(df)}")
    summary_parts.append(f"Unique models: {df['model'].nunique()} — {sorted(df['model'].unique())}")
    summary_parts.append(f"Methods: {sorted(df['method'].unique())}")
    summary_parts.append(f"Bit widths: {sorted(df['bit_width'].unique())}")
    summary_parts.append(f"Papers reproduced: {sorted(df['paper_id'].unique())}")
    summary_parts.append(f"Datasets: {sorted(df['dataset'].unique())}")
    summary_parts.append(f"Metrics: {sorted(df['metric'].unique())}")

    verdict_counts = df['amd_verdict'].value_counts().to_dict()
    summary_parts.append(f"\nVerdict distribution: {verdict_counts}")

    summary_parts.append("\n" + "-" * 80)
    summary_parts.append("FULL DATA TABLE (CSV)")
    summary_parts.append("-" * 80)
    summary_parts.append(df.to_csv(index=False))

    # Pre-computed analytics
    summary_parts.append("\n" + "-" * 80)
    summary_parts.append("PRE-COMPUTED ANALYTICS")
    summary_parts.append("-" * 80)

    has_paper = df[df['paper_value'].notna()].copy()
    if not has_paper.empty:
        has_paper['abs_diff_pct'] = has_paper['amd_diff_pct'].abs()
        summary_parts.append(f"\nRows with paper reference values: {len(has_paper)}")
        summary_parts.append(f"Mean absolute % difference from paper: {has_paper['abs_diff_pct'].mean():.2f}%")
        summary_parts.append(f"Median absolute % difference from paper: {has_paper['abs_diff_pct'].median():.2f}%")
        summary_parts.append(f"Max absolute % difference: {has_paper['abs_diff_pct'].max():.2f}% "
                             f"(model={has_paper.loc[has_paper['abs_diff_pct'].idxmax(), 'model']}, "
                             f"method={has_paper.loc[has_paper['abs_diff_pct'].idxmax(), 'method']})")

        summary_parts.append("\nPer-method reproduction fidelity:")
        for method, grp in has_paper.groupby('method'):
            vc = grp['amd_verdict'].value_counts().to_dict()
            summary_parts.append(f"  {method}: mean|diff|={grp['abs_diff_pct'].mean():.2f}%, verdicts={vc}")

        summary_parts.append("\nPer-paper reproduction fidelity:")
        for paper, grp in has_paper.groupby('paper_id'):
            vc = grp['amd_verdict'].value_counts().to_dict()
            summary_parts.append(f"  {paper}: mean|diff|={grp['abs_diff_pct'].mean():.2f}%, verdicts={vc}")

    # Anomalies
    anomalies = df[df['amd_verdict'].isin(['worse', 'better'])]
    if not anomalies.empty:
        summary_parts.append("\n--- ANOMALIES (worse or better than paper) ---")
        for _, row in anomalies.iterrows():
            summary_parts.append(
                f"  {row['model']} | {row['method']} {row['bit_width']}bit | {row['dataset']}/{row['metric']} | "
                f"paper={row['paper_value']} AMD={row['amd_value']} diff={row['amd_diff_pct']}% → {row['amd_verdict']}"
            )

    # Model family scaling
    summary_parts.append("\n--- MODEL SCALING (perplexity by model size, wikitext2, GPTQ 4-bit) ---")
    ppl_gptq = df[(df['metric'] == 'perplexity') & (df['dataset'] == 'wikitext2') & (df['method'] == 'gptq') & (df['bit_width'] == 4)]
    if not ppl_gptq.empty:
        for _, row in ppl_gptq.sort_values('amd_value').iterrows():
            summary_parts.append(f"  {row['model']}: AMD={row['amd_value']}, paper={row['paper_value']}")

    return df, "\n".join(summary_parts)


# ---------------------------------------------------------------------------
# Analysis passes
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a world-class AI research scientist publishing in Nature, Science, and top-tier \
systems conferences (ASPLOS, OSDI, SOSP, ISCA). You are analysing a large-scale LLM \
quantization reproduction study conducted entirely on AMD MI210/MI300X GPUs via ROCm.

This is for a real paper submission to ASPLOS 2027 under the "Profiling, Debugging, and Testing" track, \
and an accompanying thesis. Your analysis must be at the level of rigour expected by these venues.

=== FRAMEWORK CONTEXT ===

The experiments were conducted using "LLM-Quant-Lab", an open-source framework that:
- Wraps LightCompress/LLMC for quantization (GPTQ, AWQ, SmoothQuant, RTN, LLM.int8(), HQQ, QuaRot)
- Tracks experiments in PostgreSQL + Weights & Biases
- Uses lm-eval-harness for downstream task evaluation
- Has an agentic "Scientist" LLM with 13 tools for automated analysis
- Supports ROCm (AMD) and CUDA (NVIDIA) GPU backends
- Implements automatic paper reproduction with verdict classification

Hardware: AMD Instinct MI210 (64GB HBM2e) and MI300X GPUs, ROCm 6.2/6.3, PyTorch 2.3+

=== YOUR MISSION ===

Produce analysis that is:
1. QUANTITATIVELY PRECISE — every claim backed by exact numbers from the data
2. STATISTICALLY RIGOROUS — effect sizes, confidence intervals, significance tests
3. MECHANISTICALLY INSIGHTFUL — explain WHY results differ, not just THAT they differ
4. ARCHITECTURALLY AWARE — discuss transformer layer structure, attention vs FFN, model families
5. HARDWARE-CONSCIOUS — discuss AMD ROCm numerical behaviour, FP16/BF16 differences, kernel implementations
6. PUBLICATION-READY — structured like a top conference paper section

DO NOT produce generic or surface-level analysis. Every paragraph must contain specific numbers, \
model names, and testable hypotheses. If you find yourself writing generic statements like \
"quantization reduces model size", you are being too superficial — go deeper.
"""

ANALYSIS_PASSES = [
    {
        "id": "pass1_comprehensive_overview",
        "prompt": """\
ANALYSIS PASS 1: COMPREHENSIVE DATA OVERVIEW AND REPRODUCTION FIDELITY

You have been given the complete dataset from a large-scale LLM quantization reproduction study.
Analyse it with extreme thoroughness:

1. EXPERIMENTAL MATRIX: Map out the complete experimental coverage. Which (model, method, bit_width, dataset) \
   combinations were tested? Identify gaps in the matrix. Comment on the statistical power of the design.

2. REPRODUCTION FIDELITY ANALYSIS:
   - For each of the 5 reproduced papers (GPTQ, AWQ, SmoothQuant, LLM.int8, ParetoQ), compute:
     * Number of matching/close/better/worse results
     * Mean and std of percentage differences
     * Whether AMD ROCm results systematically deviate in one direction (bias)
   - Perform a meta-analysis: Is there a systematic AMD-vs-paper bias? Run a one-sample t-test on the differences.
   - Identify which paper was hardest/easiest to reproduce and hypothesize why.

3. METHOD RANKING: Across all models and datasets, rank the quantization methods by:
   - Perplexity preservation (lower degradation = better)
   - Downstream task accuracy (HellaSwag, PIQA, WinoGrande, LAMBADA, ARC)
   - Consistency across model families (lowest variance = more reliable)

4. CRITICAL ANOMALIES: Several results demand explanation:
   - RTN consistently "better" than paper values — is this a real improvement or a measurement artefact?
   - Mixtral SmoothQuant catastrophic failure (perplexity ~4.8 million)
   - Mistral-7B-Instruct AWQ 40.9% worse than paper
   - SmoothQuant wikitext2 results dramatically "better" on some models
   Analyse each anomaly with specific numbers and propose mechanistic explanations.

Be exhaustive. Use specific experiment IDs, exact values, and percentage differences.""",
    },
    {
        "id": "pass2_scaling_and_architecture",
        "prompt": """\
ANALYSIS PASS 2: SCALING LAWS, ARCHITECTURE EFFECTS, AND DATA TYPE ANALYSIS

Building on your previous analysis, now go deeper into the physics of quantization:

1. SCALING ANALYSIS:
   - For each method (GPTQ, AWQ, SmoothQuant, RTN), compute the perplexity degradation ratio \
     (quantized_ppl / fp16_ppl) as a function of model size.
   - Is there a power-law relationship? Does degradation decrease with scale (larger models more robust)?
   - Identify crossover points: at what model size does method A become better than method B?
   - Compare OPT vs LLaMA vs BLOOM families — do different architectures scale differently?

2. ARCHITECTURE-SPECIFIC EFFECTS:
   - OPT uses learned positional embeddings; LLaMA uses RoPE. Does this affect quantization?
   - BLOOM uses ALiBi attention. How does SmoothQuant perform on ALiBi vs RoPE models?
   - Mixtral is a Mixture-of-Experts model. Why did SmoothQuant catastrophically fail?
     Hypothesize about MoE router sensitivity, expert activation distributions, and gating mechanisms.
   - Compare decoder-only architectures of different vintages (GPT-J vs OPT vs LLaMA vs Llama-2 vs Llama-3.1)

3. BIT-WIDTH ANALYSIS:
   - Compare 3-bit vs 4-bit vs 8-bit vs 16-bit degradation curves
   - Is the relationship linear or is there a phase transition at certain bit widths?
   - Which methods show graceful degradation vs catastrophic failure at low bit widths?

4. METRIC CORRELATION:
   - Does perplexity degradation predict downstream task degradation? Compute correlation.
   - Are some downstream tasks more sensitive to quantization than others?
   - Is there a task where quantized models paradoxically improve?

Provide exact numbers for every claim. Structure this as you would a Results section.""",
    },
    {
        "id": "pass3_hardware_and_numerical",
        "prompt": """\
ANALYSIS PASS 3: AMD ROCm HARDWARE ANALYSIS AND NUMERICAL BEHAVIOUR

This is the most novel part of your analysis — most quantization papers only report NVIDIA results.

1. AMD vs PUBLISHED (NVIDIA) COMPARISON:
   - The paper values in the dataset are all from NVIDIA GPUs. Our values are all from AMD MI210/MI300X.
   - Compute the systematic bias: on average, are AMD results better or worse?
   - Is the bias method-dependent? (e.g., does GPTQ work better on AMD than AWQ?)
   - Is the bias model-size-dependent? (larger models more/less affected?)
   - Separate the analysis by metric type (perplexity vs accuracy tasks)

2. NUMERICAL PRECISION ANALYSIS:
   - AMD GPUs use different FP16/BF16 implementations than NVIDIA (ROCm vs CUDA math libraries)
   - The "better" RTN results suggest AMD's FP16 handling may differ — analyse this.
   - For LLM.int8() (mixed-precision INT8 + FP16), the close/matching results suggest good parity.
   - SmoothQuant applies per-channel scaling — discuss how AMD's matrix multiplication kernels \
     handle this differently.

3. ROCm-SPECIFIC OBSERVATIONS:
   - The pytorch_rocm_issue_reproducer.py in the repo documents a known FP16 triu_tril_kernel issue \
     on MI210. Could this affect any of our results?
   - ROCm's hipBLAS vs NVIDIA's cuBLAS — different rounding modes could explain systematic differences
   - The Mixtral SmoothQuant failure — could this be a ROCm MoE kernel issue rather than an \
     algorithmic failure?

4. IMPLICATIONS FOR HARDWARE-AWARE QUANTIZATION:
   - Based on our data, which quantization methods are "hardware-portable" (similar results on AMD/NVIDIA)?
   - Which methods seem hardware-sensitive?
   - What should practitioners know when deploying quantized models on AMD?

This section is what makes our paper unique — the AMD/ROCm angle is under-studied in the literature. \
Make it count with deep technical analysis.""",
    },
    {
        "id": "pass4_literature_and_synthesis",
        "prompt": """\
ANALYSIS PASS 4: LITERATURE COMPARISON AND PUBLICATION-READY SYNTHESIS

Now synthesise everything into paper-ready material:

1. LITERATURE POSITIONING:
   - Compare our reproduction results with:
     * GPTQ (Frantar et al., 2022): OPT and BLOOM families
     * AWQ (Lin et al., 2023): LLaMA and Llama-2 families
     * SmoothQuant (Xiao et al., 2023): OPT-IML, LLaMA, Llama-2, Mistral, Mixtral
     * LLM.int8() (Dettmers et al., 2022): OPT family
     * ParetoQ (Wang et al., 2024): Llama-3.1
   - For each paper, what percentage of results do we successfully reproduce?
   - Where do we diverge, and what does this tell us about reproducibility in quantization research?

2. NOVEL FINDINGS suitable for ASPLOS 2027:
   - Finding 1: AMD ROCm quantization parity — frame as profiling/validation contribution
   - Finding 2: Systematic RTN baseline discrepancies — implications for fair benchmarking
   - Finding 3: MoE quantization failures — SmoothQuant on Mixtral
   - Finding 4: Architecture-dependent quantization robustness
   - Finding 5: The LLM-Quant-Lab framework itself as a contribution to reproducible research

3. KEY RESULTS TABLES: Write out the exact LaTeX tables that should appear in the paper:
   - Table 1: GPTQ reproduction (OPT + BLOOM, WikiText-2, C4)
   - Table 2: AWQ reproduction (LLaMA families, WikiText-2)
   - Table 3: SmoothQuant reproduction (accuracy tasks)
   - Table 4: Cross-method comparison on best-covered models
   - Table 5: Anomaly catalog

4. EXECUTIVE SUMMARY: In 500 words, write the core argument of our ASPLOS paper. \
   Why should the program committee accept this paper? What is the contribution \
   to the "Profiling, Debugging, and Testing" community?

Make this publishable. Every sentence should survive peer review.""",
    },
]


# ---------------------------------------------------------------------------
# Quality assessment
# ---------------------------------------------------------------------------

def assess_quality(response: str) -> tuple[bool, list[str]]:
    """Check if the response is deep enough. Returns (is_good, issues)."""
    issues = []
    
    if len(response) < 3000:
        issues.append("Response too short — likely superficial")
    
    numbers_count = sum(1 for c in response if c.isdigit())
    if numbers_count < 50:
        issues.append("Too few specific numbers — need more quantitative backing")
    
    generic_phrases = [
        "quantization reduces model size",
        "there is a trade-off",
        "results vary across",
        "further investigation is needed",
        "as expected",
    ]
    generic_count = sum(1 for p in generic_phrases if p.lower() in response.lower())
    if generic_count >= 3:
        issues.append(f"Too many generic phrases ({generic_count}) — need more specific analysis")
    
    model_names = ["opt", "llama", "bloom", "mistral", "mixtral"]
    model_refs = sum(1 for m in model_names if m.lower() in response.lower())
    if model_refs < 3:
        issues.append("Not enough specific model references")
    
    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_analysis():
    print(f"\n{'=' * 80}")
    print("LLM-Quant-Lab Scientist Agent — Opus 4.6 Analysis Pipeline")
    print(f"{'=' * 80}")
    print(f"Model: {MODEL}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Started: {datetime.now().isoformat()}")
    
    df, data_context = load_and_summarise_data()
    print(f"\nData loaded: {len(df)} rows, {df['model'].nunique()} models, {df['method'].nunique()} methods")
    
    all_results = {}
    conversation_context = []
    
    for pass_info in ANALYSIS_PASSES:
        pass_id = pass_info["id"]
        print(f"\n{'─' * 80}")
        print(f"Running: {pass_id}")
        print(f"{'─' * 80}")
        
        messages = [{"role": "user", "content": f"DATA CONTEXT:\n\n{data_context}\n\n{'=' * 40}\n\n{pass_info['prompt']}"}]
        
        if conversation_context:
            prior_summary = "\n\n".join(
                f"[PRIOR ANALYSIS — {pid}]:\n{text[:2000]}..." 
                for pid, text in conversation_context[-2:]
            )
            messages[0]["content"] = (
                f"PRIOR ANALYSIS CONTEXT:\n{prior_summary}\n\n{'=' * 40}\n\n"
                + messages[0]["content"]
            )
        
        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"  Attempt {attempt + 1}/{max_attempts}...")
            t0 = time.time()
            
            try:
                response = call_anthropic(
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    temperature=0.3 if attempt == 0 else 0.5,
                )
            except httpx.HTTPStatusError as e:
                print(f"  API error: {e.response.status_code} — {e.response.text[:200]}")
                if e.response.status_code == 529:
                    print("  API overloaded, waiting 30s...")
                    time.sleep(30)
                    continue
                raise
            
            elapsed = time.time() - t0
            print(f"  Response: {len(response)} chars in {elapsed:.1f}s")
            
            is_good, issues = assess_quality(response)
            
            if is_good:
                print(f"  Quality: PASS")
                break
            else:
                print(f"  Quality: NEEDS IMPROVEMENT — {issues}")
                if attempt < max_attempts - 1:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Your analysis has these issues: {issues}. "
                            "Please go MUCH deeper. I need:\n"
                            "- Exact numbers for every claim (model name, metric value, percentage)\n"
                            "- Mechanistic explanations (WHY, not just WHAT)\n"
                            "- Statistical analysis (effect sizes, confidence intervals)\n"
                            "- Specific experiment IDs and configurations\n"
                            "- Testable hypotheses for anomalies\n"
                            "- Architecture-level reasoning (attention heads, FFN layers, embeddings)\n"
                            "Rewrite with publication-level depth."
                        ),
                    })
        
        all_results[pass_id] = response
        conversation_context.append((pass_id, response))
        
        out_path = OUTPUT_DIR / f"{pass_id}.md"
        with open(out_path, "w") as f:
            f.write(f"# {pass_id.replace('_', ' ').title()}\n\n")
            f.write(f"*Generated: {datetime.now().isoformat()}*\n")
            f.write(f"*Model: {MODEL}*\n\n")
            f.write(response)
        print(f"  Saved: {out_path}")
    
    # Final combined output
    combined_path = OUTPUT_DIR / "full_scientist_analysis.md"
    with open(combined_path, "w") as f:
        f.write("# LLM-Quant-Lab: Complete Scientist Agent Analysis\n\n")
        f.write(f"*Generated: {datetime.now().isoformat()}*\n")
        f.write(f"*Model: {MODEL}*\n")
        f.write(f"*Data: {len(df)} experiments, {df['model'].nunique()} models*\n\n")
        f.write("---\n\n")
        for pass_id, text in all_results.items():
            f.write(f"## {pass_id.replace('_', ' ').title()}\n\n")
            f.write(text)
            f.write("\n\n---\n\n")
    
    print(f"\n{'=' * 80}")
    print(f"Analysis complete. Combined output: {combined_path}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    run_analysis()
