"""Payload builder for scientist LLM prompts.

This module builds structured prompts from experiment data, metrics,
and paper notes for the scientist LLM to analyze.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# System prompt
# ============================================================================

SCIENTIST_SYSTEM_PROMPT = """You are an expert AI research scientist specializing in LLM quantization and compression. 
Your role is to analyze quantization experiment results and produce rigorous research reports.

You have deep knowledge of:
- Post-training quantization methods (GPTQ, AWQ, SmoothQuant, etc.)
- Weight, activation, and KV-cache quantization
- Quantization theory: bit-width, per-channel vs per-tensor, group sizes
- Common failure modes and their causes
- State-of-the-art benchmarks and evaluation metrics

When analyzing experiments, you should:
1. Describe the experimental setup clearly
2. Analyze the results in context of the methods used
3. Compare findings to published results when papers are provided
4. Identify interesting patterns, anomalies, or failure modes
5. Make a clear pass/fail judgment on whether meaningful insights were achieved
6. Suggest concrete next experiments

Be precise, quantitative, and scientific in your analysis."""


# ============================================================================
# Prompt templates
# ============================================================================

EXPERIMENT_PROMPT_TEMPLATE = """# Quantization Experiment Analysis Request

## Experiment Metadata
- **Experiment ID**: {experiment_id}
- **Model**: {model_name}
- **Base Precision**: {base_precision}
- **Hardware**: {gpu_type} (x{gpu_count})
- **Created**: {created_at}

## Quantization Configuration
{quant_config_section}

## Evaluation Metrics
{metrics_section}

## Hardware Performance
{hardware_section}

## Layer-wise Statistics (Sample)
{layer_stats_section}

## Reference Papers
{papers_section}

---

## Analysis Request

Please provide a comprehensive research report with the following sections:

### 1. Experimental Setup
Describe the methodology and what was tested.

### 2. Key Findings
Analyze the results. What worked? What didn't? Are there interesting patterns?

### 3. Comparison to Literature
If reference papers are provided, compare the results to published claims and hypotheses.
Are the results consistent with expectations? Any surprises?

### 4. Layer-wise Analysis
If layer statistics are provided, identify any problematic layers or interesting patterns.

### 5. Pass/Fail Judgment
Make a clear determination:
- **PASS**: The experiment yielded a meaningful new insight, confirmed a non-trivial hypothesis, or achieved notable results.
- **FAIL**: Results are inconclusive, uninteresting, or contradict expectations without explanation.
- **INCONCLUSIVE**: More data or experiments are needed.

Explain your reasoning.

### 6. Suggested Next Experiments
Based on these results, what should be tested next? Be specific.

---

Please format your response as a well-structured Markdown report."""


# ============================================================================
# Payload builder
# ============================================================================


def build_scientist_payload(
    experiment_data: dict[str, Any],
    paper_notes: list[dict[str, Any]] | None = None,
    max_layer_stats: int = 10,
) -> dict[str, Any]:
    """Build the payload for the scientist LLM.
    
    Args:
        experiment_data: Full experiment data from database
        paper_notes: Optional paper notes for context
        max_layer_stats: Maximum layer statistics to include
        
    Returns:
        Dictionary with 'system_prompt' and 'user_prompt'
    """
    exp = experiment_data.get("experiment", {})
    quant_configs = experiment_data.get("quant_configs", [])
    metrics = experiment_data.get("metrics", [])
    hardware_stats = experiment_data.get("hardware_stats", [])
    layer_metrics = experiment_data.get("layer_metrics", [])
    
    # Build quant config section
    quant_config_section = _build_quant_config_section(quant_configs)
    
    # Build metrics section
    metrics_section = _build_metrics_section(metrics)
    
    # Build hardware section
    hardware_section = _build_hardware_section(hardware_stats)
    
    # Build layer stats section (limited)
    layer_stats_section = _build_layer_stats_section(layer_metrics, max_layer_stats)
    
    # Build papers section
    papers_section = _build_papers_section(paper_notes)
    
    # Format the prompt
    user_prompt = EXPERIMENT_PROMPT_TEMPLATE.format(
        experiment_id=exp.get("id", "unknown"),
        model_name=exp.get("model_name", "unknown"),
        base_precision=exp.get("base_precision", "unknown"),
        gpu_type=exp.get("gpu_type", "unknown"),
        gpu_count=exp.get("gpu_count", 1),
        created_at=exp.get("created_at", "unknown"),
        quant_config_section=quant_config_section,
        metrics_section=metrics_section,
        hardware_section=hardware_section,
        layer_stats_section=layer_stats_section,
        papers_section=papers_section,
    )
    
    return {
        "system_prompt": SCIENTIST_SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "temperature": 0.0,
        "max_tokens": 4000,
    }


def _build_quant_config_section(quant_configs: list[dict[str, Any]]) -> str:
    """Build the quantization configuration section."""
    if not quant_configs:
        return "No quantization configurations recorded."
    
    lines = []
    for i, qc in enumerate(quant_configs):
        lines.append(f"### Configuration {i + 1}: {qc.get('method_name', 'unknown')}")
        lines.append(f"- **Bit Width**: {qc.get('bit_width', 'N/A')}")
        lines.append(f"- **Per-Channel**: {qc.get('per_channel', 'N/A')}")
        lines.append(f"- **Group Size**: {qc.get('group_size', 'N/A')}")
        lines.append(f"- **Activation Quant**: {qc.get('activation_quant', False)}")
        lines.append(f"- **KV Quant**: {qc.get('kv_quant', False)}")
        lines.append(f"- **Calibration Dataset**: {qc.get('calib_dataset', 'N/A')}")
        lines.append(f"- **Calibration Samples**: {qc.get('calib_size', 'N/A')}")
        lines.append(f"- **Status**: {qc.get('status', 'unknown')}")
        if qc.get('duration_seconds'):
            lines.append(f"- **Duration**: {qc['duration_seconds']:.1f}s")
        lines.append("")
    
    return "\n".join(lines)


def _build_metrics_section(metrics: list[dict[str, Any]]) -> str:
    """Build the metrics section."""
    if not metrics:
        return "No metrics recorded."
    
    # Group by dataset
    by_dataset: dict[str, list[dict[str, Any]]] = {}
    for m in metrics:
        dataset = m.get("dataset", "unknown")
        if dataset not in by_dataset:
            by_dataset[dataset] = []
        by_dataset[dataset].append(m)
    
    lines = []
    for dataset, dataset_metrics in by_dataset.items():
        lines.append(f"### {dataset}")
        lines.append("| Metric | Value | Split |")
        lines.append("|--------|-------|-------|")
        for m in dataset_metrics:
            value = m.get("value", 0)
            if isinstance(value, float):
                value_str = f"{value:.4f}"
            else:
                value_str = str(value)
            lines.append(f"| {m.get('metric_name', 'unknown')} | {value_str} | {m.get('split', 'test')} |")
        lines.append("")
    
    return "\n".join(lines)


def _build_hardware_section(hardware_stats: list[dict[str, Any]]) -> str:
    """Build the hardware performance section."""
    if not hardware_stats:
        return "No hardware statistics recorded."
    
    # Use the most recent stats
    hw = hardware_stats[-1] if hardware_stats else {}
    
    lines = [
        f"- **GPU**: {hw.get('gpu_type', 'unknown')}",
        f"- **GPU Memory**: {hw.get('gpu_memory_gb', 'N/A')} GB",
        "",
        "**Latency:**",
        f"- P50: {hw.get('latency_p50', 'N/A')} ms",
        f"- P95: {hw.get('latency_p95', 'N/A')} ms",
        f"- Mean: {hw.get('latency_mean', 'N/A')} ms",
        "",
        "**Throughput:**",
        f"- Tokens/second: {hw.get('tokens_per_second', 'N/A')}",
        "",
        "**Memory:**",
        f"- Allocated: {hw.get('memory_allocated', 'N/A')} GB",
        f"- Peak: {hw.get('memory_peak', 'N/A')} GB",
        f"- Model Size: {hw.get('model_size_mb', 'N/A')} MB",
    ]
    
    if hw.get('compression_ratio'):
        lines.append(f"- Compression Ratio: {hw['compression_ratio']:.2f}x")
    
    return "\n".join(lines)


def _build_layer_stats_section(
    layer_metrics: list[dict[str, Any]],
    max_stats: int = 10,
) -> str:
    """Build the layer-wise statistics section."""
    if not layer_metrics:
        return "No layer-wise statistics recorded."
    
    # Group by stat type
    by_type: dict[str, list[dict[str, Any]]] = {}
    for lm in layer_metrics:
        stat_type = lm.get("stat_type", "unknown")
        if stat_type not in by_type:
            by_type[stat_type] = []
        by_type[stat_type].append(lm)
    
    lines = []
    
    for stat_type, stats in by_type.items():
        lines.append(f"### {stat_type.replace('_', ' ').title()} Statistics")
        
        # Show summary statistics
        stat_names = list(set(s.get("stat_name", "") for s in stats))
        
        for stat_name in stat_names[:5]:  # Limit stat types
            stat_values = [s for s in stats if s.get("stat_name") == stat_name]
            
            if stat_values:
                values = [s.get("value", 0) for s in stat_values[:max_stats]]
                if values:
                    avg = sum(values) / len(values)
                    min_val = min(values)
                    max_val = max(values)
                    lines.append(f"- **{stat_name}**: avg={avg:.4f}, min={min_val:.4f}, max={max_val:.4f}")
        
        lines.append("")
    
    return "\n".join(lines)


def _build_papers_section(paper_notes: list[dict[str, Any]] | None) -> str:
    """Build the reference papers section."""
    if not paper_notes:
        return "No reference papers provided."
    
    lines = []
    
    for paper in paper_notes:
        lines.append(f"### {paper.get('title', 'Unknown Paper')}")
        lines.append(f"**Paper ID**: {paper.get('paper_id', 'unknown')}")
        
        if paper.get("citation"):
            lines.append(f"**Citation**: {paper['citation']}")
        
        if paper.get("core_idea"):
            lines.append(f"\n**Core Idea**: {paper['core_idea']}")
        
        if paper.get("expected_behavior"):
            lines.append(f"\n**Expected Behavior**: {paper['expected_behavior']}")
        
        if paper.get("known_limitations"):
            lines.append(f"\n**Known Limitations**: {paper['known_limitations']}")
        
        lines.append("")
    
    return "\n".join(lines)


# ============================================================================
# Paper notes loading
# ============================================================================


def load_paper_notes(paper_ids: list[str]) -> list[dict[str, Any]]:
    """Load paper notes from the papers/notes directory.
    
    Args:
        paper_ids: List of paper IDs to load
        
    Returns:
        List of paper note dictionaries
    """
    import yaml
    
    notes_dir = Path(__file__).parent.parent.parent / "papers" / "notes"
    
    loaded_notes = []
    
    for paper_id in paper_ids:
        # Try different file extensions
        for ext in [".yaml", ".yml", ".json"]:
            note_path = notes_dir / f"{paper_id}{ext}"
            if note_path.exists():
                try:
                    with open(note_path) as f:
                        if ext == ".json":
                            note = json.load(f)
                        else:
                            note = yaml.safe_load(f)
                    
                    note["paper_id"] = paper_id
                    loaded_notes.append(note)
                    logger.info(f"Loaded paper note: {paper_id}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load paper note {paper_id}: {e}")
    
    return loaded_notes


def load_paper_notes_from_db(
    session: Any,
    paper_ids: list[str],
) -> list[dict[str, Any]]:
    """Load paper notes from the database.
    
    Args:
        session: Database session
        paper_ids: List of paper IDs to load
        
    Returns:
        List of paper note dictionaries
    """
    from ..db.models import PaperNote
    
    notes = session.query(PaperNote).filter(PaperNote.paper_id.in_(paper_ids)).all()
    
    return [note.to_dict() for note in notes]
