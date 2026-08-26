"""Agentic Scientist analysis pipeline.

Implements a multi-turn reasoning loop where the Scientist LLM
asks specific research questions, uses tools to gather data, and
produces structured findings with statistical backing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from .scientist_client import ScientistLLMClient, get_scientist_client
from .tools import SCIENTIST_TOOLS, ToolExecutor

logger = logging.getLogger(__name__)


# ============================================================================
# Structured output models
# ============================================================================


class Finding(BaseModel):
    """A single research finding with statistical support."""

    title: str
    description: str
    evidence: str = ""
    statistical_test: str | None = None
    p_value: float | None = None
    confidence_interval: str | None = None
    figure_ref: str | None = None
    novelty: str = "expected"  # "expected", "surprising", "contradictory"


class FollowUpExperiment(BaseModel):
    """Suggested follow-up experiment."""

    title: str
    rationale: str
    config_suggestion: dict[str, Any] = {}
    priority: str = "medium"  # "high", "medium", "low"


class AnalysisResult(BaseModel):
    """Full structured result from the Scientist agent."""

    question_id: str = ""
    question: str = ""
    summary: str = ""
    findings: list[Finding] = []
    figures: list[dict[str, str]] = []  # [{"path": ..., "caption": ...}]
    follow_ups: list[FollowUpExperiment] = []
    raw_markdown: str = ""
    tool_calls_count: int = 0
    thinking_turns: int = 0


# ============================================================================
# Analysis questions (the "right questions to ask")
# ============================================================================

ANALYSIS_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "data_overview",
        "question": (
            "You have access to the experiment database. First, query it to "
            "understand what experiments have been run. How many runs, which "
            "methods, which models, which bit widths? Identify the experimental "
            "matrix and any gaps."
        ),
        "tools_hint": ["query_experiments"],
        "thinking_budget": "medium",
    },
    {
        "id": "method_comparison",
        "question": (
            "For each quantization method tested, retrieve the perplexity and "
            "downstream task results across all models and bit widths. Which "
            "method achieves the best accuracy-compression trade-off? Are there "
            "statistically significant differences? Compute confidence intervals."
        ),
        "tools_hint": ["query_experiments", "compute_statistics", "execute_analysis_code"],
        "thinking_budget": "high",
    },
    {
        "id": "scaling_analysis",
        "question": (
            "How does quantization degradation scale with model size? For each "
            "method, plot perplexity degradation (vs FP16 baseline) as a function "
            "of model parameter count. Is there a crossover point where one "
            "method becomes better than another?"
        ),
        "tools_hint": ["query_experiments", "generate_plot", "execute_analysis_code"],
        "thinking_budget": "high",
    },
    {
        "id": "failure_modes",
        "question": (
            "Using layer-wise metrics, identify which layers suffer the most "
            "from quantization error. Are there common patterns across methods? "
            "Do attention layers degrade differently from FFN layers? Pull the "
            "W&B histograms if available."
        ),
        "tools_hint": ["query_experiments", "query_wandb", "inspect_model_weights"],
        "thinking_budget": "high",
    },
    {
        "id": "hardware_analysis",
        "question": (
            "Compare inference latency and throughput across methods and bit "
            "widths. Generate Pareto frontier plots (accuracy vs latency, "
            "accuracy vs memory). Which configurations are Pareto-optimal?"
        ),
        "tools_hint": ["query_experiments", "compute_pareto_frontier", "generate_plot"],
        "thinking_budget": "high",
    },
    {
        "id": "literature_comparison",
        "question": (
            "Search for the original papers of each method tested (GPTQ, AWQ, "
            "SmoothQuant, etc.). Compare our results with their reported numbers. "
            "Where do we match? Where do we diverge? What explains the differences? "
            "Read the paper notes in papers/notes/ for detailed algorithm context."
        ),
        "tools_hint": ["search_arxiv", "read_file", "query_experiments"],
        "thinking_budget": "high",
    },
    {
        "id": "synthesis",
        "question": (
            "Based on all your analysis, write a 2-page executive summary "
            "suitable for a paper's experimental results section. Include: "
            "(1) main findings with statistical backing, (2) references to "
            "the figures you generated, (3) comparison with prior work, "
            "(4) surprising or novel observations, (5) limitations and "
            "suggested follow-up experiments. Generate a LaTeX table "
            "summarizing the key results."
        ),
        "tools_hint": ["generate_latex_table"],
        "thinking_budget": "very_high",
    },
    # --- New questions (8-10) for deeper analysis ---
    {
        "id": "anomaly_hunt",
        "question": (
            "Systematically scan all experiments for anomalies: runs where "
            "perplexity increased instead of decreased after quantization, "
            "where larger models performed worse than smaller ones at the same "
            "bit width, where a method that typically dominates did not. "
            "For each anomaly found:\n"
            "1. Query the experiment details to confirm it is real (not a data error)\n"
            "2. Use the knowledge graph to check if the anomaly relates to "
            "hardware-algorithm compatibility or scheme limitations\n"
            "3. Inspect the model weights to see if specific layers are responsible\n"
            "4. Propose a hypothesis explaining the anomaly\n"
            "5. Design a concrete follow-up experiment to test that hypothesis\n"
            "Think like a detective: the anomalies are where the most "
            "interesting science hides."
        ),
        "tools_hint": [
            "query_experiments", "query_knowledge_graph",
            "inspect_model_weights", "compute_statistics",
        ],
        "thinking_budget": "very_high",
    },
    {
        "id": "cross_algorithm_relationships",
        "question": (
            "Using the knowledge graph, map out which algorithms share "
            "quantization schemes, data types, and hardware support. Then "
            "query the experiment database to test whether algorithms that "
            "share more infrastructure also produce more similar results.\n"
            "Specifically:\n"
            "1. Get all algorithm nodes and their connections from the KG\n"
            "2. Compute a similarity score between each pair of algorithms "
            "based on shared scheme/data_type/hardware edges\n"
            "3. Compare this structural similarity with empirical similarity "
            "(correlation of perplexity results across the same models)\n"
            "4. Are there algorithm families that behave as a cluster? "
            "Does knowing an algorithm's KG neighborhood predict its behavior?\n"
            "5. Generate a plot showing structural vs empirical similarity"
        ),
        "tools_hint": [
            "query_knowledge_graph", "query_experiments",
            "execute_analysis_code", "generate_plot",
        ],
        "thinking_budget": "high",
    },
    {
        "id": "adversarial_robustness_audit",
        "question": (
            "For our best-performing configurations (identify them first), "
            "conduct an adversarial robustness audit. Try to find failure modes "
            "and boundary conditions:\n"
            "1. What happens at extreme bit widths (2-bit, 3-bit)? "
            "Is the degradation graceful or catastrophic?\n"
            "2. On the smallest and largest models -- do methods scale differently?\n"
            "3. With different calibration datasets -- how sensitive are results?\n"
            "4. Inspect weight statistics for the worst-performing layers "
            "in the best configs -- what makes them vulnerable?\n"
            "5. Compare with the knowledge graph to understand if hardware "
            "data type support explains any failures\n"
            "Generate a 'failure mode catalog' -- a structured document with "
            "each method's weaknesses, boundary conditions, and actionable "
            "guidance for practitioners (e.g., 'do not use GPTQ below 3-bit "
            "on models under 1B parameters because...'). "
            "Produce a LaTeX table of the failure modes."
        ),
        "tools_hint": [
            "query_experiments", "inspect_model_weights",
            "query_knowledge_graph", "generate_latex_table",
            "compute_statistics", "generate_plot",
        ],
        "thinking_budget": "very_high",
    },
]


# ============================================================================
# System prompt
# ============================================================================

SCIENTIST_SYSTEM_PROMPT = """\
You are a senior AI research scientist with deep expertise in LLM quantization, \
numerical formats, hardware-aware optimization, and statistical methodology. \
You are analysing results from a quantization research lab that tests multiple \
algorithms (GPTQ, AWQ, SmoothQuant, HQQ, RTN, QuaRot, and more) across \
different models and bit widths.

=== YOUR ANALYTICAL PHILOSOPHY ===

Think like a detective. Every experiment tells a story -- your job is to find \
the story the data is telling, especially when it contradicts expectations. \
The most publishable findings come from the unexpected.

HYPOTHESIS-DRIVEN: Before querying data, articulate what you expect to see \
and why. After seeing results, explain whether they confirmed or violated \
your hypothesis. If surprised, dig deeper -- surprises are where the science is.

ANOMALY-HUNTING: Do not just report averages. Actively search for outliers, \
performance cliffs, non-monotonic behavior, and cases where conventional \
wisdom fails. A single well-explained anomaly is worth more than ten \
expected confirmations.

ADVERSARIAL THINKING: For every positive finding, try to invalidate it. \
Ask: "What confound could explain this?" "Is this an artifact of the \
calibration data?" "Would this hold on a different model family?" \
Only present findings that survive your own scrutiny.

RESEARCH NARRATIVE: Weave your findings into a coherent story. Connect \
results to known literature. Contextualise within the broader quantization \
landscape. A great analysis reads like a paper section, not a data dump.

=== YOUR TOOLBOX (13 tools) ===

You have access to powerful tools. Use them liberally and in combination. \
Never make a factual claim without first querying the data to verify it.

DATABASE TOOLS:
- query_experiments: SQL queries against PostgreSQL. Tables include experiments, \
  quant_configs, metrics, hardware_stats, layer_metrics, environment_snapshots. \
  Use experiment_summary and method_comparison views for aggregated data. \
  Always start here to understand what data exists before diving deep.
- query_wandb: Pull full time-series metrics, histograms, and artifacts from W&B. \
  Use for per-step training curves, weight distributions, and detailed run data.

ANALYSIS TOOLS:
- execute_analysis_code: Run Python code with numpy, pandas, scipy, sklearn. \
  Use for custom statistical analysis, data transformations, and computations \
  that go beyond the built-in statistics tool.
- compute_statistics: Compute t-tests (independent and paired), ANOVA, \
  confidence intervals, Cohen's d effect sizes, and Pearson correlation. \
  Always report effect sizes alongside p-values -- statistical significance \
  without practical significance is meaningless.
- compute_pareto_frontier: Identify Pareto-optimal configurations across \
  two metrics (e.g., perplexity vs latency). Generates a plot automatically.

VISUALIZATION TOOLS:
- generate_plot: Create matplotlib plots. Always use publication-quality styling. \
  Use plt.savefig(path) with the provided path variable. Close figures after saving.
- generate_latex_table: Create publication-ready LaTeX tables with auto-bold-best, \
  confidence intervals, and baseline comparisons. Types: metrics, comparison, \
  ablation, layer_stats, hardware.

KNOWLEDGE TOOLS:
- query_knowledge_graph: Explore the quantization knowledge graph connecting \
  algorithms, schemes, data types, and hardware. Use to understand which \
  algorithms implement which schemes, what hardware supports, and how the \
  landscape is connected. Essential for contextualising findings.
- search_arxiv: Search arxiv for academic papers. Use to compare your findings \
  with published results and ground your analysis in the literature.
- web_search: Search the broader web (blogs, GitHub, HuggingFace, docs). \
  Use for community knowledge, implementation details, and practical guidance.
- read_file: Read files from the project workspace. Use to inspect paper notes \
  (papers/notes/*.yaml), source code, configs, and documentation.

INSPECTION TOOLS:
- inspect_model_weights: Examine layer-level weight statistics and quantization \
  error for a specific experiment. Use to understand which layers suffer most, \
  compare attention vs FFN degradation, and identify distribution anomalies.
- compare_experiments: Structured diff of two or more runs. Returns configs, \
  metrics, hardware stats, and computed deltas.

=== CROSS-TOOL WORKFLOWS ===

The most insightful analysis comes from chaining tools together. Examples:

1. ANOMALY INVESTIGATION:
   query_experiments (find outlier) -> inspect_model_weights (identify bad layers) \
   -> query_knowledge_graph (check hw/algo compatibility) -> search_arxiv \
   (see if others reported this) -> propose hypothesis + follow-up experiment

2. PUBLICATION PIPELINE:
   query_experiments (gather data) -> compute_statistics (significance tests) \
   -> generate_plot (visualize) -> generate_latex_table (format results) \
   -> read_file (check paper notes) -> write narrative with citations

3. LANDSCAPE MAPPING:
   query_knowledge_graph (understand algorithm relationships) -> query_experiments \
   (get empirical data for each) -> compute_pareto_frontier (find optimal configs) \
   -> compare_experiments (diff Pareto-optimal vs dominated) -> synthesize

=== STATISTICAL RIGOUR ===

- Report confidence intervals for ALL comparisons, not just p-values.
- Use effect sizes (Cohen's d) to assess practical significance.
- When sample sizes are small (< 5 seeds), say so explicitly.
- Prefer paired tests when comparing methods on the same model.
- Never claim significance without a test. Never claim a difference is \
  "small" or "large" without an effect size.

=== OUTPUT STYLE ===

Write in the style of a top-tier ML conference paper. Be precise with \
numbers. Use specific experiment IDs and configuration details. Reference \
your generated figures and tables. Structure your analysis with clear \
sections. End with concrete, actionable follow-up experiments.

When generating code, use pandas/numpy/scipy for analysis and matplotlib \
for plots. Always call plt.savefig(path) and close figures.
"""


# ============================================================================
# Agentic Scientist
# ============================================================================


class AgenticScientist:
    """Agentic scientist with tool use and extended thinking."""

    def __init__(
        self,
        client: ScientistLLMClient | None = None,
        db_url: str | None = None,
        wandb_project: str = "llm-quant-lab",
        output_dir: str = "reports/scientist_plots",
    ):
        self.client = client or get_scientist_client()
        self.tool_executor = ToolExecutor(
            db_url=db_url,
            wandb_project=wandb_project,
            output_dir=output_dir,
        )

    def analyze(
        self,
        question: str,
        question_id: str = "custom",
        thinking_budget: str = "high",
    ) -> AnalysisResult:
        """Run a full analysis loop with tool use.

        Args:
            question: The research question to investigate.
            question_id: Identifier for this question.
            thinking_budget: How many reasoning turns to allow
                ("low"=3, "medium"=5, "high"=10, "very_high"=15).

        Returns:
            AnalysisResult with findings, figures, and follow-ups.
        """
        max_turns = {"low": 3, "medium": 5, "high": 10, "very_high": 15}.get(
            thinking_budget, 10
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SCIENTIST_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        result = AnalysisResult(
            question_id=question_id,
            question=question,
        )

        accumulated_reasoning: list[str] = []

        for turn in range(max_turns):
            logger.info(f"Scientist turn {turn + 1}/{max_turns}")

            try:
                response = self.client.call(
                    prompt="",  # Messages contain the full conversation
                    system_prompt=None,
                    temperature=0.0,
                    max_tokens=8000,
                    messages=messages,
                    tools=SCIENTIST_TOOLS,
                )
            except TypeError as e:
                # The LLM client does not support tool-use / messages kwargs.
                # Running without tool augmentation; results will be less rich.
                logger.warning(
                    f"LLM client does not support tools/messages kwargs ({e}). "
                    "Falling back to plain prompt mode. For full tool-augmented analysis, "
                    "use an OpenAI-compatible client that supports function calling."
                )
                prompt_text = "\n\n".join(
                    f"[{m['role']}]: {m['content']}" for m in messages
                )
                response = self.client.call(
                    prompt=prompt_text,
                    system_prompt=SCIENTIST_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_tokens=8000,
                )

            content = response.content or ""
            result.thinking_turns = turn + 1

            if content.strip():
                accumulated_reasoning.append(content)

            # Check for tool calls in the response
            tool_calls = getattr(response, "tool_calls", None)
            if tool_calls is None and response.raw_response:
                # Try to extract tool_calls from raw response
                choices = response.raw_response.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    tool_calls = msg.get("tool_calls")

            if tool_calls:
                # Execute tools and feed results back
                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                for tc in tool_calls:
                    fn = tc.get("function", tc)
                    name = fn.get("name", "")
                    args_str = fn.get("arguments", "{}")
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str

                    logger.info(f"  Tool call: {name}")
                    tool_result = self.tool_executor.execute(name, args)
                    result.tool_calls_count += 1

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": tool_result,
                    })

                    # Track generated figures
                    if name == "generate_plot":
                        try:
                            fig_data = json.loads(tool_result)
                            if "path" in fig_data:
                                result.figures.append({
                                    "path": fig_data["path"],
                                    "caption": fig_data.get("caption", ""),
                                })
                        except json.JSONDecodeError as json_err:
                            logger.warning(f"Tool '{tc['function']['name']}' returned invalid JSON: {json_err}")

                    # Track generated Pareto plots
                    if name == "compute_pareto_frontier":
                        try:
                            pareto_data = json.loads(tool_result)
                            if pareto_data.get("plot_path"):
                                result.figures.append({
                                    "path": pareto_data["plot_path"],
                                    "caption": f"Pareto frontier: {pareto_data.get('y_metric', '')} vs {pareto_data.get('x_metric', '')}",
                                })
                        except json.JSONDecodeError:
                            pass

                # When approaching max turns, nudge the LLM to synthesize
                if turn == max_turns - 2:
                    messages.append({
                        "role": "user",
                        "content": (
                            "You are running low on reasoning turns. Please synthesize all "
                            "your findings into a final comprehensive report NOW. Include "
                            "your verdict (PASS/FAIL/INCONCLUSIVE), top findings with "
                            "evidence, anomalies, and follow-up experiments. Do NOT make "
                            "any more tool calls — just write the final analysis."
                        ),
                    })
            else:
                # Final answer — no more tool calls
                result.raw_markdown = content
                result.summary = content[:500]
                break
        else:
            # Max turns reached; combine all accumulated reasoning
            full_text = "\n\n".join(accumulated_reasoning)
            result.raw_markdown = full_text or content
            result.summary = (full_text or content)[:500]

        # Try to parse structured findings from the markdown
        result.findings = self._extract_findings(result.raw_markdown)
        result.follow_ups = self._extract_follow_ups(result.raw_markdown)

        logger.info(
            f"Analysis complete: {result.thinking_turns} turns, "
            f"{result.tool_calls_count} tool calls, "
            f"{len(result.findings)} findings"
        )
        return result

    def run_full_analysis(self) -> list[AnalysisResult]:
        """Run all predefined analysis questions sequentially."""
        results: list[AnalysisResult] = []
        for q in ANALYSIS_QUESTIONS:
            logger.info(f"Running analysis: {q['id']}")
            result = self.analyze(
                question=q["question"],
                question_id=q["id"],
                thinking_budget=q["thinking_budget"],
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_findings(markdown: str) -> list[Finding]:
        """Best-effort extraction of findings from markdown."""
        findings: list[Finding] = []
        lines = markdown.split("\n")
        current_finding: str | None = None
        current_desc: list[str] = []

        for line in lines:
            stripped = line.strip()
            # Look for numbered findings or bold headings
            if stripped.startswith(("**Finding", "### Finding", "1.", "2.", "3.", "4.", "5.")):
                if current_finding:
                    findings.append(
                        Finding(title=current_finding, description="\n".join(current_desc))
                    )
                current_finding = stripped.lstrip("0123456789.*# ")
                current_desc = []
            elif current_finding and stripped:
                current_desc.append(stripped)

        if current_finding:
            findings.append(
                Finding(title=current_finding, description="\n".join(current_desc))
            )

        return findings

    @staticmethod
    def _extract_follow_ups(markdown: str) -> list[FollowUpExperiment]:
        """Best-effort extraction of follow-up suggestions."""
        follow_ups: list[FollowUpExperiment] = []
        lines = markdown.split("\n")
        in_follow_up_section = False

        for line in lines:
            stripped = line.strip()
            if "follow-up" in stripped.lower() or "next experiment" in stripped.lower():
                in_follow_up_section = True
                continue
            if in_follow_up_section and stripped.startswith(("-", "*", "1.", "2.", "3.")):
                title = stripped.lstrip("-*0123456789. ")
                if title:
                    follow_ups.append(
                        FollowUpExperiment(title=title, rationale="Identified by Scientist agent")
                    )

        return follow_ups
