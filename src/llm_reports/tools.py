"""Tool definitions and executor for the Agentic Scientist.

Each tool follows the OpenAI function-calling schema so it can be
passed directly to any compatible LLM API.
"""

from __future__ import annotations

import io
import json
import logging
import os
import traceback
from contextlib import redirect_stdout
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================================
# Tool schema definitions (OpenAI function-calling format)
# ============================================================================

SCIENTIST_TOOLS: list[dict[str, Any]] = [
    # ── Tool 1: query_experiments ──────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_experiments",
            "description": (
                "Execute a SQL query against the experiment database to retrieve "
                "metrics, configs, hardware stats, or layer-level data. "
                "Available tables: experiments, quant_configs, metrics, hardware_stats, "
                "layer_metrics, environment_snapshots, experiment_groups, calibration_records. "
                "Key columns: experiments(id, name, model_name, status, gpu_type, gpu_count, created_at), "
                "quant_configs(id, experiment_id, method_name, bit_width, group_size, is_symmetric, "
                "calib_dataset, calib_size, duration_seconds), "
                "metrics(id, experiment_id, dataset, metric_name, value, split), "
                "hardware_stats(id, experiment_id, latency_p50, tokens_per_second, memory_peak, "
                "model_size_mb, compression_ratio). "
                "JOIN quant_configs ON quant_configs.experiment_id = experiments.id to get method info. "
                "The experiments table does NOT have method or bit_width columns — use quant_configs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "PostgreSQL SELECT query (read-only).",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why you need this data.",
                    },
                },
                "required": ["sql"],
            },
        },
    },
    # ── Tool 2: query_wandb ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_wandb",
            "description": (
                "Query W&B for full metric time-series, histograms, or "
                "artifacts for a specific run."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "wandb_run_id": {"type": "string"},
                    "data_type": {
                        "type": "string",
                        "enum": ["history", "summary", "artifacts", "config"],
                    },
                    "metric_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific metrics to retrieve from history.",
                    },
                },
                "required": ["wandb_run_id", "data_type"],
            },
        },
    },
    # ── Tool 3: execute_analysis_code ──────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "execute_analysis_code",
            "description": (
                "Execute Python code for statistical analysis. Has access to "
                "pandas, numpy, scipy.stats, sklearn.metrics, json, os.path. "
                "Returns stdout + any printed results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute.",
                    },
                    "purpose": {
                        "type": "string",
                        "description": "What this analysis computes.",
                    },
                },
                "required": ["code"],
            },
        },
    },
    # ── Tool 4: generate_plot ──────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "generate_plot",
            "description": (
                "Generate a matplotlib plot and save it. "
                "Must call plt.savefig(path). Returns the file path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Matplotlib code. Must call plt.savefig().",
                    },
                    "filename": {"type": "string"},
                    "caption": {
                        "type": "string",
                        "description": "Caption for the figure.",
                    },
                },
                "required": ["code", "filename"],
            },
        },
    },
    # ── Tool 5: search_arxiv ───────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_arxiv",
            "description": (
                "Search arxiv for academic papers. Use this for finding "
                "specific research papers, comparing findings against "
                "published results, and grounding analysis in the literature."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query.",
                    },
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    # ── Tool 6: compute_statistics ─────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "compute_statistics",
            "description": (
                "Compute statistical tests (t-test, paired t-test, ANOVA, "
                "confidence intervals, effect size, correlation) on experiment "
                "results. Always use this to back empirical claims."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "test_type": {
                        "type": "string",
                        "enum": [
                            "t_test",
                            "paired_t_test",
                            "anova",
                            "confidence_interval",
                            "effect_size",
                            "correlation",
                        ],
                    },
                    "data": {
                        "type": "object",
                        "description": "Data for the test.",
                    },
                    "alpha": {"type": "number", "default": 0.05},
                },
                "required": ["test_type", "data"],
            },
        },
    },
    # ── Tool 7: read_file ──────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the project workspace. Use this to inspect "
                "source code, configuration files, paper notes (YAML), "
                "markdown documentation, or experiment configs. "
                "Path is relative to the workspace root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Path relative to workspace root, e.g. "
                            "'papers/notes/awq.yaml' or 'src/quant/llmc_wrappers.py'."
                        ),
                    },
                    "max_lines": {
                        "type": "integer",
                        "default": 200,
                        "description": "Maximum number of lines to return.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    # ── Tool 8: generate_latex_table ───────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "generate_latex_table",
            "description": (
                "Generate a publication-ready LaTeX table from experiment data. "
                "Supports metrics tables, comparison tables with baselines, "
                "ablation tables, layer statistics, and hardware performance tables. "
                "Tables auto-bold best values and include confidence intervals."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table_type": {
                        "type": "string",
                        "enum": [
                            "metrics",
                            "comparison",
                            "ablation",
                            "layer_stats",
                            "hardware",
                        ],
                        "description": "Type of table to generate.",
                    },
                    "experiment_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Experiment IDs to include in the table.",
                    },
                    "options": {
                        "type": "object",
                        "description": (
                            "Options: bold_best (bool), confidence_intervals (bool), "
                            "baseline_id (int), precision (int), caption (string)."
                        ),
                    },
                },
                "required": ["table_type", "experiment_ids"],
            },
        },
    },
    # ── Tool 9: inspect_model_weights ──────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "inspect_model_weights",
            "description": (
                "Inspect layer-level weight statistics and quantization error "
                "for an experiment. Use this to understand which layers suffer "
                "most from quantization, compare attention vs FFN degradation, "
                "and identify weight distribution anomalies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "Experiment ID to inspect.",
                    },
                    "layer_filter": {
                        "type": "string",
                        "description": (
                            "Optional filter: 'attention', 'ffn', 'embedding', "
                            "or a layer name substring."
                        ),
                    },
                    "stat_type": {
                        "type": "string",
                        "enum": ["summary", "per_layer", "distribution"],
                        "description": (
                            "summary: aggregate stats across all layers. "
                            "per_layer: stats for each layer individually. "
                            "distribution: histogram-style breakdown."
                        ),
                    },
                },
                "required": ["experiment_id"],
            },
        },
    },
    # ── Tool 10: query_knowledge_graph ─────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_graph",
            "description": (
                "Query the quantization knowledge graph to explore relationships "
                "between algorithms, schemes, data types, and hardware. Use this "
                "to understand which algorithms implement which schemes, what "
                "data types hardware supports, and how the quantization landscape "
                "is connected. Node types: algorithm, scheme, data_type, hardware."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "get_node",
                            "search_nodes",
                            "get_neighbors",
                            "get_subgraph",
                        ],
                        "description": (
                            "get_node: get a single node by ID. "
                            "search_nodes: search by label. "
                            "get_neighbors: get all connected nodes. "
                            "get_subgraph: get a set of nodes and their edges."
                        ),
                    },
                    "node_id": {
                        "type": "string",
                        "description": (
                            "Node ID (e.g. 'algo_gptq', 'hw_mi300x', "
                            "'dt_int4', 'sch_w4')."
                        ),
                    },
                    "node_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filter by node types: 'algorithm', 'scheme', "
                            "'data_type', 'hardware'."
                        ),
                    },
                    "edge_type": {
                        "type": "string",
                        "enum": ["implements", "uses", "supports"],
                        "description": "Filter by edge type.",
                    },
                    "search_term": {
                        "type": "string",
                        "description": "Search nodes by label (case-insensitive).",
                    },
                },
                "required": ["query_type"],
            },
        },
    },
    # ── Tool 11: compare_experiments ───────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "compare_experiments",
            "description": (
                "Perform a structured comparison of two or more experiments. "
                "Returns per-experiment data, deltas between runs, and a "
                "markdown summary. Use this to diff configs, metrics, or "
                "hardware performance across runs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "experiment_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Experiment IDs to compare (2+).",
                    },
                    "comparison_type": {
                        "type": "string",
                        "enum": ["metrics", "hardware", "configs", "full"],
                        "description": (
                            "metrics: compare evaluation metrics. "
                            "hardware: compare latency/throughput/memory. "
                            "configs: compare quantization configurations. "
                            "full: all of the above."
                        ),
                    },
                },
                "required": ["experiment_ids"],
            },
        },
    },
    # ── Tool 12: compute_pareto_frontier ───────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "compute_pareto_frontier",
            "description": (
                "Compute the Pareto frontier from experiment data. Identifies "
                "configurations that are not dominated on both axes (e.g. no "
                "other config is both faster AND more accurate). Also generates "
                "a Pareto plot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x_metric": {
                        "type": "string",
                        "description": (
                            "Metric for x-axis, e.g. 'latency_ms', "
                            "'memory_peak', 'model_size_mb'."
                        ),
                    },
                    "y_metric": {
                        "type": "string",
                        "description": (
                            "Metric for y-axis, e.g. 'perplexity', "
                            "'accuracy', 'throughput'."
                        ),
                    },
                    "filter": {
                        "type": "object",
                        "description": (
                            "Optional filters: method, model, bit_width. "
                            "E.g. {'method': 'gptq', 'bit_width': 4}."
                        ),
                    },
                },
                "required": ["x_metric", "y_metric"],
            },
        },
    },
    # ── Tool 13: web_search ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web using Perplexity AI for information beyond arxiv. "
                "Use for blog posts, GitHub issues, HuggingFace model cards, "
                "documentation, and community discussions about quantization. "
                "Returns AI-synthesized answers with source citations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query.",
                    },
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]


# ============================================================================
# Tool executor
# ============================================================================


class ToolExecutor:
    """Executes tool calls from the Scientist LLM."""

    def __init__(
        self,
        db_url: str | None = None,
        wandb_project: str = "llm-quant-lab",
        output_dir: str = "reports/scientist_plots",
        workspace_root: str | None = None,
    ):
        self.db_url = db_url or os.getenv("DATABASE_URL", "")
        self.wandb_project = wandb_project
        self.output_dir = output_dir
        self.workspace_root = workspace_root or os.getenv(
            "WORKSPACE_ROOT", os.getcwd()
        )
        os.makedirs(output_dir, exist_ok=True)

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool call and return the string result."""
        dispatch = {
            "query_experiments": self._query_experiments,
            "query_wandb": self._query_wandb,
            "execute_analysis_code": self._execute_code,
            "generate_plot": self._generate_plot,
            # Keep old name as alias for backwards compatibility
            "search_literature": self._search_arxiv,
            "search_arxiv": self._search_arxiv,
            "compute_statistics": self._compute_statistics,
            "read_file": self._read_file,
            "generate_latex_table": self._generate_latex_table,
            "inspect_model_weights": self._inspect_model_weights,
            "query_knowledge_graph": self._query_knowledge_graph,
            "compare_experiments": self._compare_experiments,
            "compute_pareto_frontier": self._compute_pareto_frontier,
            "web_search": self._web_search,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = handler(arguments)
            return result if isinstance(result, str) else json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _query_experiments(self, args: dict[str, Any]) -> str:
        """Execute a read-only SQL query against Postgres."""
        import pandas as pd
        from sqlalchemy import text

        from ..db.models import get_engine

        sql = args["sql"].strip()

        # Safety: only allow SELECT statements
        if not sql.upper().startswith("SELECT"):
            return json.dumps({"error": "Only SELECT queries are allowed."})

        engine = get_engine(self.db_url)
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)

        if len(df) == 0:
            return json.dumps({"rows": 0, "data": []})

        # Truncate very large results
        if len(df) > 200:
            df = df.head(200)
            truncated = True
        else:
            truncated = False

        return json.dumps(
            {
                "rows": len(df),
                "columns": list(df.columns),
                "data": df.to_dict(orient="records"),
                "truncated": truncated,
            },
            default=str,
        )

    def _query_wandb(self, args: dict[str, Any]) -> str:
        """Query W&B API for run data."""
        try:
            import wandb

            api = wandb.Api()
            run = api.run(f"{self.wandb_project}/{args['wandb_run_id']}")

            data_type = args["data_type"]
            if data_type == "history":
                keys = args.get("metric_keys")
                hist = run.history(keys=keys) if keys else run.history()
                return hist.to_json()
            elif data_type == "summary":
                return json.dumps(dict(run.summary), default=str)
            elif data_type == "config":
                return json.dumps(dict(run.config), default=str)
            elif data_type == "artifacts":
                arts = [{"name": a.name, "type": a.type} for a in run.logged_artifacts()]
                return json.dumps(arts)
            else:
                return json.dumps({"error": f"Unknown data_type: {data_type}"})
        except ImportError:
            return json.dumps({"error": "wandb is not installed"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _execute_code(self, args: dict[str, Any]) -> str:
        """Execute Python code in a restricted namespace."""
        code = args["code"]

        # Build namespace with common libraries
        namespace: dict[str, Any] = {"__builtins__": __builtins__}
        try:
            import numpy as np
            import pandas as pd

            namespace["np"] = np
            namespace["pd"] = pd
        except ImportError:
            logger.debug("numpy/pandas not available in code execution sandbox")
        try:
            import scipy.stats

            namespace["scipy"] = __import__("scipy")
            namespace["stats"] = scipy.stats
        except ImportError:
            logger.debug("scipy not available in code execution sandbox")
        try:
            import sklearn.metrics

            namespace["sklearn"] = __import__("sklearn")
            namespace["sklearn_metrics"] = sklearn.metrics
        except ImportError:
            logger.debug("sklearn.metrics not available in code execution sandbox")

        # Convenience modules
        namespace["json"] = json
        namespace["os_path"] = os.path

        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                exec(code, namespace)  # noqa: S102
        except Exception as e:
            return json.dumps({"error": str(e), "stdout": buf.getvalue()})

        return json.dumps({"stdout": buf.getvalue()})

    def _generate_plot(self, args: dict[str, Any]) -> str:
        """Execute matplotlib code and save the plot."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        code = args["code"]
        filename = args["filename"]
        path = os.path.join(self.output_dir, filename)

        namespace: dict[str, Any] = {
            "plt": plt,
            "np": __import__("numpy"),
            "path": path,
        }
        try:
            import pandas as pd
            namespace["pd"] = pd
        except ImportError:
            logger.debug("pandas not available in plotting sandbox")

        try:
            exec(code, namespace)  # noqa: S102
            plt.close("all")
            return json.dumps({"path": path, "caption": args.get("caption", "")})
        except Exception as e:
            plt.close("all")
            return json.dumps({"error": str(e)})

    def _search_arxiv(self, args: dict[str, Any]) -> str:
        """Search arxiv for papers (via public API)."""
        import urllib.parse
        import xml.etree.ElementTree as ET

        query = args["query"]
        max_results = args.get("max_results", 5)
        url = (
            f"http://export.arxiv.org/api/query?"
            f"search_query=all:{urllib.parse.quote(query)}"
            f"&start=0&max_results={max_results}"
        )

        try:
            import httpx

            r = httpx.get(url, timeout=30)
            root = ET.fromstring(r.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            papers = []
            for entry in root.findall("atom:entry", ns):
                title = entry.findtext("atom:title", "", ns).strip()
                summary = entry.findtext("atom:summary", "", ns).strip()[:300]
                arxiv_id = entry.findtext("atom:id", "", ns).split("/")[-1]
                papers.append(
                    {"title": title, "arxiv_id": arxiv_id, "summary": summary}
                )
            return json.dumps(papers)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _compute_statistics(self, args: dict[str, Any]) -> str:
        """Compute statistical tests."""
        import numpy as np

        test_type = args["test_type"]
        data = args["data"]
        alpha = args.get("alpha", 0.05)

        try:
            from scipy import stats as sp_stats

            if test_type == "t_test":
                group1 = np.array(data.get("group1", []))
                group2 = np.array(data.get("group2", []))
                t_stat, p_val = sp_stats.ttest_ind(group1, group2)
                return json.dumps(
                    {
                        "t_statistic": float(t_stat),
                        "p_value": float(p_val),
                        "significant": p_val < alpha,
                        "alpha": alpha,
                    }
                )
            elif test_type == "paired_t_test":
                group1 = np.array(data.get("group1", []))
                group2 = np.array(data.get("group2", []))
                t_stat, p_val = sp_stats.ttest_rel(group1, group2)
                return json.dumps(
                    {
                        "t_statistic": float(t_stat),
                        "p_value": float(p_val),
                        "significant": p_val < alpha,
                        "alpha": alpha,
                        "test": "paired_t_test",
                    }
                )
            elif test_type == "anova":
                groups = [np.array(g) for g in data.get("groups", [])]
                f_stat, p_val = sp_stats.f_oneway(*groups)
                return json.dumps(
                    {
                        "f_statistic": float(f_stat),
                        "p_value": float(p_val),
                        "significant": p_val < alpha,
                    }
                )
            elif test_type == "confidence_interval":
                values = np.array(data.get("values", []))
                mean = float(np.mean(values))
                sem = float(sp_stats.sem(values))
                ci = sp_stats.t.interval(
                    1 - alpha, len(values) - 1, loc=mean, scale=sem
                )
                return json.dumps(
                    {"mean": mean, "sem": sem, "ci_lower": ci[0], "ci_upper": ci[1]}
                )
            elif test_type == "effect_size":
                group1 = np.array(data.get("group1", []))
                group2 = np.array(data.get("group2", []))
                # Use sample variance (ddof=1) for Cohen's d
                pooled_std = np.sqrt(
                    (np.var(group1, ddof=1) + np.var(group2, ddof=1)) / 2
                )
                cohens_d = float(
                    (np.mean(group1) - np.mean(group2)) / pooled_std
                ) if pooled_std > 0 else 0.0
                return json.dumps({
                    "cohens_d": cohens_d,
                    "interpretation": (
                        "negligible" if abs(cohens_d) < 0.2
                        else "small" if abs(cohens_d) < 0.5
                        else "medium" if abs(cohens_d) < 0.8
                        else "large"
                    ),
                })
            elif test_type == "correlation":
                x = np.array(data.get("x", []))
                y = np.array(data.get("y", []))
                r, p = sp_stats.pearsonr(x, y)
                return json.dumps(
                    {"pearson_r": float(r), "p_value": float(p)}
                )
            else:
                return json.dumps({"error": f"Unknown test: {test_type}"})
        except ImportError:
            return json.dumps({"error": "scipy is not installed"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------
    # New tools (7-13)
    # ------------------------------------------------------------------

    def _read_file(self, args: dict[str, Any]) -> str:
        """Read a file from the project workspace."""
        rel_path = args["path"]
        max_lines = args.get("max_lines", 200)

        # Resolve and validate path is within workspace
        full_path = os.path.normpath(os.path.join(self.workspace_root, rel_path))
        if not full_path.startswith(os.path.normpath(self.workspace_root)):
            return json.dumps({"error": "Path is outside the workspace."})

        if not os.path.isfile(full_path):
            return json.dumps({"error": f"File not found: {rel_path}"})

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            truncated = total_lines > max_lines
            content = "".join(lines[:max_lines])

            return json.dumps({
                "path": rel_path,
                "total_lines": total_lines,
                "lines_returned": min(total_lines, max_lines),
                "truncated": truncated,
                "content": content,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _generate_latex_table(self, args: dict[str, Any]) -> str:
        """Generate a publication-ready LaTeX table."""
        import pandas as pd
        from sqlalchemy import text

        from ..db.models import get_engine

        table_type = args["table_type"]
        experiment_ids = args["experiment_ids"]
        options = args.get("options", {})

        if not experiment_ids:
            return json.dumps({"error": "experiment_ids must not be empty."})

        engine = get_engine(self.db_url)

        try:
            with engine.connect() as conn:
                # Fetch experiment data
                placeholders = ", ".join(f":id{i}" for i in range(len(experiment_ids)))
                id_params = {f"id{i}": eid for i, eid in enumerate(experiment_ids)}

                # Get experiments
                exp_df = pd.read_sql(
                    text(f"SELECT * FROM experiments WHERE id IN ({placeholders})"),
                    conn,
                    params=id_params,
                )

                # Get metrics
                metrics_df = pd.read_sql(
                    text(
                        f"SELECT m.*, e.model_name, qc.method_name, qc.bit_width "
                        f"FROM metrics m "
                        f"JOIN experiments e ON m.experiment_id = e.id "
                        f"LEFT JOIN quant_configs qc ON m.quant_config_id = qc.id "
                        f"WHERE m.experiment_id IN ({placeholders})"
                    ),
                    conn,
                    params=id_params,
                )

                # Get hardware stats
                hw_df = pd.read_sql(
                    text(
                        f"SELECT * FROM hardware_stats WHERE experiment_id IN ({placeholders})"
                    ),
                    conn,
                    params=id_params,
                )

            bold_best = options.get("bold_best", True)
            precision = options.get("precision", 2)
            caption = options.get("caption", "")

            if table_type == "metrics":
                latex = self._latex_metrics_table(metrics_df, bold_best, precision, caption)
            elif table_type == "comparison":
                baseline_id = options.get("baseline_id")
                latex = self._latex_comparison_table(
                    metrics_df, baseline_id, bold_best, precision, caption
                )
            elif table_type == "ablation":
                latex = self._latex_ablation_table(metrics_df, bold_best, precision, caption)
            elif table_type == "hardware":
                latex = self._latex_hardware_table(hw_df, exp_df, bold_best, precision, caption)
            elif table_type == "layer_stats":
                layer_df = pd.DataFrame()
                with engine.connect() as conn:
                    layer_df = pd.read_sql(
                        text(
                            f"SELECT * FROM layer_metrics "
                            f"WHERE experiment_id IN ({placeholders})"
                        ),
                        conn,
                        params=id_params,
                    )
                latex = self._latex_layer_stats_table(layer_df, precision, caption)
            else:
                return json.dumps({"error": f"Unknown table_type: {table_type}"})

            # Save to file
            filename = f"table_{table_type}_{'_'.join(str(i) for i in experiment_ids)}.tex"
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w") as f:
                f.write(latex)

            return json.dumps({
                "latex": latex,
                "path": filepath,
                "table_type": table_type,
            })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @staticmethod
    def _latex_metrics_table(
        df: "pd.DataFrame", bold_best: bool, precision: int, caption: str
    ) -> str:
        """Generate a metrics comparison LaTeX table."""
        if df.empty:
            return "% No metrics data available"

        pivot = df.pivot_table(
            index=["method_name", "bit_width"],
            columns="metric_name",
            values="value",
            aggfunc="mean",
        ).reset_index()

        lines = [
            "\\begin{table}[ht]",
            "\\centering",
            f"\\caption{{{caption or 'Quantization Metrics Comparison'}}}",
            "\\begin{tabular}{ll" + "r" * (len(pivot.columns) - 2) + "}",
            "\\toprule",
        ]

        headers = ["Method", "Bits"] + [
            c for c in pivot.columns if c not in ("method_name", "bit_width")
        ]
        lines.append(" & ".join(headers) + " \\\\")
        lines.append("\\midrule")

        # Find best values per metric column
        metric_cols = [c for c in pivot.columns if c not in ("method_name", "bit_width")]
        best_vals = {}
        for col in metric_cols:
            if "perplexity" in col.lower() or "loss" in col.lower():
                best_vals[col] = pivot[col].min()
            else:
                best_vals[col] = pivot[col].max()

        for _, row in pivot.iterrows():
            cells = [str(row["method_name"]).upper(), str(int(row["bit_width"]))]
            for col in metric_cols:
                val = row[col]
                formatted = f"{val:.{precision}f}" if not pd.isna(val) else "--"
                if bold_best and not pd.isna(val) and val == best_vals.get(col):
                    formatted = f"\\textbf{{{formatted}}}"
                cells.append(formatted)
            lines.append(" & ".join(cells) + " \\\\")

        lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
        return "\n".join(lines)

    @staticmethod
    def _latex_comparison_table(
        df: "pd.DataFrame",
        baseline_id: int | None,
        bold_best: bool,
        precision: int,
        caption: str,
    ) -> str:
        """Generate a comparison table with baseline deltas."""
        if df.empty:
            return "% No metrics data available"

        lines = [
            "\\begin{table}[ht]",
            "\\centering",
            f"\\caption{{{caption or 'Comparison with Baseline'}}}",
            "\\begin{tabular}{llrrr}",
            "\\toprule",
            "Method & Bits & Value & $\\Delta$ & $\\Delta$\\% \\\\",
            "\\midrule",
        ]

        if baseline_id:
            baseline_df = df[df["experiment_id"] == baseline_id]
            if not baseline_df.empty:
                baseline_val = baseline_df["value"].mean()
                for _, row in df.iterrows():
                    delta = row["value"] - baseline_val
                    delta_pct = (delta / baseline_val * 100) if baseline_val else 0
                    lines.append(
                        f"{row.get('method_name', 'N/A')} & "
                        f"{row.get('bit_width', 'N/A')} & "
                        f"{row['value']:.{precision}f} & "
                        f"{delta:+.{precision}f} & "
                        f"{delta_pct:+.1f}\\% \\\\"
                    )

        lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
        return "\n".join(lines)

    @staticmethod
    def _latex_ablation_table(
        df: "pd.DataFrame", bold_best: bool, precision: int, caption: str
    ) -> str:
        """Generate an ablation study table (method x bit_width)."""
        if df.empty:
            return "% No metrics data available"

        pivot = df.pivot_table(
            index="method_name",
            columns="bit_width",
            values="value",
            aggfunc="mean",
        )

        bit_widths = sorted(pivot.columns)
        lines = [
            "\\begin{table}[ht]",
            "\\centering",
            f"\\caption{{{caption or 'Ablation: Method vs Bit Width'}}}",
            "\\begin{tabular}{l" + "r" * len(bit_widths) + "}",
            "\\toprule",
            "Method & " + " & ".join(f"{int(b)}-bit" for b in bit_widths) + " \\\\",
            "\\midrule",
        ]

        for method in pivot.index:
            cells = [method.upper()]
            for bw in bit_widths:
                val = pivot.loc[method, bw]
                cells.append(f"{val:.{precision}f}" if not pd.isna(val) else "--")
            lines.append(" & ".join(cells) + " \\\\")

        lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
        return "\n".join(lines)

    @staticmethod
    def _latex_hardware_table(
        hw_df: "pd.DataFrame",
        exp_df: "pd.DataFrame",
        bold_best: bool,
        precision: int,
        caption: str,
    ) -> str:
        """Generate a hardware performance table."""
        if hw_df.empty:
            return "% No hardware stats available"

        merged = hw_df.merge(
            exp_df[["id", "model_name"]], left_on="experiment_id", right_on="id", how="left"
        )

        lines = [
            "\\begin{table}[ht]",
            "\\centering",
            f"\\caption{{{caption or 'Hardware Performance'}}}",
            "\\begin{tabular}{lrrrr}",
            "\\toprule",
            "Config & Latency (ms) & Throughput (tok/s) & Memory (GB) & Size (MB) \\\\",
            "\\midrule",
        ]

        for _, row in merged.iterrows():
            name = str(row.get("model_name", "N/A")).split("/")[-1]
            lines.append(
                f"{name} & "
                f"{row.get('latency_mean', 0):.1f} & "
                f"{row.get('tokens_per_second', 0):.0f} & "
                f"{row.get('memory_peak', 0):.1f} & "
                f"{row.get('model_size_mb', 0):.0f} \\\\"
            )

        lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
        return "\n".join(lines)

    @staticmethod
    def _latex_layer_stats_table(
        df: "pd.DataFrame", precision: int, caption: str
    ) -> str:
        """Generate a layer-level statistics table."""
        if df.empty:
            return "% No layer metrics available"

        import pandas as pd

        summary = df.groupby("layer_name").agg(
            quant_error_mean=("quant_error", "mean"),
            quant_error_std=("quant_error", "std"),
            weight_norm_mean=("weight_norm", "mean"),
        ).reset_index().head(30)

        lines = [
            "\\begin{table}[ht]",
            "\\centering",
            f"\\caption{{{caption or 'Layer-wise Quantization Statistics'}}}",
            "\\begin{tabular}{lrrr}",
            "\\toprule",
            "Layer & Error (mean) & Error (std) & Weight Norm \\\\",
            "\\midrule",
        ]

        for _, row in summary.iterrows():
            lines.append(
                f"{row['layer_name']} & "
                f"{row['quant_error_mean']:.{precision}f} & "
                f"{row.get('quant_error_std', 0):.{precision}f} & "
                f"{row['weight_norm_mean']:.{precision}f} \\\\"
            )

        lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
        return "\n".join(lines)

    def _inspect_model_weights(self, args: dict[str, Any]) -> str:
        """Inspect layer-level weight statistics from the database."""
        import numpy as np
        import pandas as pd
        from sqlalchemy import text

        from ..db.models import get_engine

        experiment_id = args["experiment_id"]
        layer_filter = args.get("layer_filter")
        stat_type = args.get("stat_type", "summary")

        engine = get_engine(self.db_url)

        query = "SELECT * FROM layer_metrics WHERE experiment_id = :eid"
        params: dict[str, Any] = {"eid": experiment_id}

        if layer_filter:
            query += " AND LOWER(layer_name) LIKE :lfilter"
            params["lfilter"] = f"%{layer_filter.lower()}%"

        query += " ORDER BY layer_index"

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        if df.empty:
            return json.dumps({
                "error": f"No layer metrics found for experiment {experiment_id}",
                "hint": "Layer metrics are only available if the experiment was run with capture_weights=True.",
            })

        if stat_type == "summary":
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            # Exclude id and index columns
            numeric_cols = [
                c for c in numeric_cols
                if c not in ("id", "experiment_id", "layer_index", "quant_config_id")
            ]
            summary = {}
            for col in numeric_cols:
                summary[col] = {
                    "mean": float(df[col].mean()),
                    "std": float(df[col].std()),
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "median": float(df[col].median()),
                }
            return json.dumps({
                "experiment_id": experiment_id,
                "total_layers": len(df),
                "stat_type": "summary",
                "statistics": summary,
            })

        elif stat_type == "per_layer":
            # Return per-layer data (limited to 100 layers)
            layer_data = df.head(100).to_dict(orient="records")
            return json.dumps({
                "experiment_id": experiment_id,
                "total_layers": len(df),
                "layers_returned": min(len(df), 100),
                "stat_type": "per_layer",
                "layers": layer_data,
            }, default=str)

        elif stat_type == "distribution":
            # Compute histogram-style breakdown of quantization error
            if "quant_error" in df.columns:
                errors = df["quant_error"].dropna()
                hist, bin_edges = np.histogram(errors, bins=20)
                return json.dumps({
                    "experiment_id": experiment_id,
                    "total_layers": len(df),
                    "stat_type": "distribution",
                    "metric": "quant_error",
                    "histogram": {
                        "counts": hist.tolist(),
                        "bin_edges": bin_edges.tolist(),
                    },
                    "percentiles": {
                        "p10": float(np.percentile(errors, 10)),
                        "p25": float(np.percentile(errors, 25)),
                        "p50": float(np.percentile(errors, 50)),
                        "p75": float(np.percentile(errors, 75)),
                        "p90": float(np.percentile(errors, 90)),
                        "p99": float(np.percentile(errors, 99)),
                    },
                })
            else:
                return json.dumps({
                    "error": "No quant_error column found in layer_metrics.",
                    "available_columns": df.columns.tolist(),
                })

        return json.dumps({"error": f"Unknown stat_type: {stat_type}"})

    def _query_knowledge_graph(self, args: dict[str, Any]) -> str:
        """Query the quantization knowledge graph."""
        from sqlalchemy import text

        from ..db.models import get_engine

        query_type = args["query_type"]
        engine = get_engine(self.db_url)

        with engine.connect() as conn:
            if query_type == "get_node":
                node_id = args.get("node_id")
                if not node_id:
                    return json.dumps({"error": "node_id is required for get_node."})

                result = conn.execute(
                    text("SELECT * FROM knowledge_nodes WHERE id = :nid"),
                    {"nid": node_id},
                )
                row = result.fetchone()
                if not row:
                    return json.dumps({"error": f"Node not found: {node_id}"})

                node = dict(row._mapping)
                # Get edges for this node
                edges_result = conn.execute(
                    text(
                        "SELECT * FROM knowledge_edges "
                        "WHERE source_id = :nid OR target_id = :nid"
                    ),
                    {"nid": node_id},
                )
                edges = [dict(r._mapping) for r in edges_result]

                return json.dumps({"node": node, "edges": edges}, default=str)

            elif query_type == "search_nodes":
                search_term = args.get("search_term", "")
                node_types = args.get("node_types")

                query_str = "SELECT * FROM knowledge_nodes WHERE 1=1"
                params: dict[str, Any] = {}

                if search_term:
                    query_str += " AND LOWER(label) LIKE :search"
                    params["search"] = f"%{search_term.lower()}%"
                if node_types:
                    query_str += " AND node_type = ANY(:types)"
                    params["types"] = node_types

                result = conn.execute(text(query_str), params)
                nodes = [dict(r._mapping) for r in result]
                return json.dumps({"nodes": nodes, "count": len(nodes)}, default=str)

            elif query_type == "get_neighbors":
                node_id = args.get("node_id")
                edge_type = args.get("edge_type")
                if not node_id:
                    return json.dumps({"error": "node_id is required for get_neighbors."})

                edge_query = (
                    "SELECT * FROM knowledge_edges "
                    "WHERE (source_id = :nid OR target_id = :nid)"
                )
                params_e: dict[str, Any] = {"nid": node_id}
                if edge_type:
                    edge_query += " AND edge_type = :etype"
                    params_e["etype"] = edge_type

                edges_result = conn.execute(text(edge_query), params_e)
                edges = [dict(r._mapping) for r in edges_result]

                # Collect neighbor IDs
                neighbor_ids = set()
                for e in edges:
                    if e["source_id"] != node_id:
                        neighbor_ids.add(e["source_id"])
                    if e["target_id"] != node_id:
                        neighbor_ids.add(e["target_id"])

                neighbors = []
                if neighbor_ids:
                    n_result = conn.execute(
                        text("SELECT * FROM knowledge_nodes WHERE id = ANY(:ids)"),
                        {"ids": list(neighbor_ids)},
                    )
                    neighbors = [dict(r._mapping) for r in n_result]

                return json.dumps({
                    "center_node": node_id,
                    "neighbors": neighbors,
                    "edges": edges,
                    "count": len(neighbors),
                }, default=str)

            elif query_type == "get_subgraph":
                node_types = args.get("node_types")
                if not node_types:
                    return json.dumps({"error": "node_types is required for get_subgraph."})

                n_result = conn.execute(
                    text("SELECT * FROM knowledge_nodes WHERE node_type = ANY(:types)"),
                    {"types": node_types},
                )
                nodes = [dict(r._mapping) for r in n_result]
                node_ids = [n["id"] for n in nodes]

                edges = []
                if node_ids:
                    e_result = conn.execute(
                        text(
                            "SELECT * FROM knowledge_edges "
                            "WHERE source_id = ANY(:ids) AND target_id = ANY(:ids)"
                        ),
                        {"ids": node_ids},
                    )
                    edges = [dict(r._mapping) for r in e_result]

                return json.dumps({
                    "nodes": nodes,
                    "edges": edges,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                }, default=str)

            return json.dumps({"error": f"Unknown query_type: {query_type}"})

    def _compare_experiments(self, args: dict[str, Any]) -> str:
        """Compare two or more experiments."""
        import pandas as pd
        from sqlalchemy import text

        from ..db.models import get_engine

        experiment_ids = args["experiment_ids"]
        comparison_type = args.get("comparison_type", "full")

        if len(experiment_ids) < 2:
            return json.dumps({"error": "Need at least 2 experiment IDs to compare."})

        engine = get_engine(self.db_url)
        placeholders = ", ".join(f":id{i}" for i in range(len(experiment_ids)))
        id_params = {f"id{i}": eid for i, eid in enumerate(experiment_ids)}

        result: dict[str, Any] = {"experiment_ids": experiment_ids}

        with engine.connect() as conn:
            if comparison_type in ("configs", "full"):
                exp_df = pd.read_sql(
                    text(f"SELECT * FROM experiments WHERE id IN ({placeholders})"),
                    conn,
                    params=id_params,
                )
                qc_df = pd.read_sql(
                    text(f"SELECT * FROM quant_configs WHERE experiment_id IN ({placeholders})"),
                    conn,
                    params=id_params,
                )
                result["configs"] = {
                    "experiments": exp_df.to_dict(orient="records"),
                    "quant_configs": qc_df.to_dict(orient="records"),
                }

            if comparison_type in ("metrics", "full"):
                metrics_df = pd.read_sql(
                    text(
                        f"SELECT m.*, e.model_name FROM metrics m "
                        f"JOIN experiments e ON m.experiment_id = e.id "
                        f"WHERE m.experiment_id IN ({placeholders})"
                    ),
                    conn,
                    params=id_params,
                )
                if not metrics_df.empty:
                    pivot = metrics_df.pivot_table(
                        index="experiment_id",
                        columns="metric_name",
                        values="value",
                        aggfunc="mean",
                    )
                    result["metrics"] = {
                        "raw": metrics_df.to_dict(orient="records"),
                        "pivot": pivot.to_dict(),
                    }
                else:
                    result["metrics"] = {"raw": [], "pivot": {}}

            if comparison_type in ("hardware", "full"):
                hw_df = pd.read_sql(
                    text(
                        f"SELECT * FROM hardware_stats WHERE experiment_id IN ({placeholders})"
                    ),
                    conn,
                    params=id_params,
                )
                result["hardware"] = hw_df.to_dict(orient="records")

        return json.dumps(result, default=str)

    def _compute_pareto_frontier(self, args: dict[str, Any]) -> str:
        """Compute Pareto frontier from experiment data."""
        import numpy as np
        import pandas as pd
        from sqlalchemy import text

        from ..db.models import get_engine

        x_metric = args["x_metric"]
        y_metric = args["y_metric"]
        filters = args.get("filter", {})

        engine = get_engine(self.db_url)

        # Build query to get both metrics
        query = """
            SELECT 
                e.id AS experiment_id,
                e.model_name,
                qc.method_name,
                qc.bit_width,
                MAX(CASE WHEN m.metric_name = :x_metric THEN m.value END) AS x_val,
                MAX(CASE WHEN m.metric_name = :y_metric THEN m.value END) AS y_val,
                MAX(CASE WHEN hs.experiment_id = e.id THEN hs.latency_mean END) AS latency_ms,
                MAX(CASE WHEN hs.experiment_id = e.id THEN hs.tokens_per_second END) AS throughput,
                MAX(CASE WHEN hs.experiment_id = e.id THEN hs.memory_peak END) AS memory_peak,
                MAX(CASE WHEN hs.experiment_id = e.id THEN hs.model_size_mb END) AS model_size_mb
            FROM experiments e
            LEFT JOIN metrics m ON m.experiment_id = e.id
            LEFT JOIN quant_configs qc ON qc.experiment_id = e.id
            LEFT JOIN hardware_stats hs ON hs.experiment_id = e.id
            WHERE e.status = 'completed'
        """
        params: dict[str, Any] = {"x_metric": x_metric, "y_metric": y_metric}

        if filters.get("method"):
            query += " AND qc.method_name = :method"
            params["method"] = filters["method"]
        if filters.get("bit_width"):
            query += " AND qc.bit_width = :bit_width"
            params["bit_width"] = filters["bit_width"]

        query += " GROUP BY e.id, e.model_name, qc.method_name, qc.bit_width"

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        if df.empty:
            return json.dumps({"error": "No data found matching the criteria."})

        # Use hardware columns as fallback for x/y
        for col_name in ("x_val", "y_val"):
            metric_name = x_metric if col_name == "x_val" else y_metric
            if df[col_name].isna().all() and metric_name in df.columns:
                df[col_name] = df[metric_name]

        # Drop rows with missing values
        df = df.dropna(subset=["x_val", "y_val"])
        if df.empty:
            return json.dumps({
                "error": f"No experiments have both '{x_metric}' and '{y_metric}' metrics."
            })

        # Compute Pareto frontier
        x_vals = df["x_val"].values
        y_vals = df["y_val"].values
        is_pareto = np.ones(len(x_vals), dtype=bool)

        for i in range(len(x_vals)):
            for j in range(len(x_vals)):
                if i != j:
                    # Point j dominates point i if j is <= on both axes
                    # (assuming lower is better for both)
                    if x_vals[j] <= x_vals[i] and y_vals[j] <= y_vals[i]:
                        if x_vals[j] < x_vals[i] or y_vals[j] < y_vals[i]:
                            is_pareto[i] = False
                            break

        pareto_df = df[is_pareto]
        non_pareto_df = df[~is_pareto]

        # Generate plot
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 7))
            ax.scatter(
                non_pareto_df["x_val"], non_pareto_df["y_val"],
                alpha=0.4, label="Dominated", color="gray",
            )
            ax.scatter(
                pareto_df["x_val"], pareto_df["y_val"],
                color="red", s=80, zorder=5, label="Pareto-optimal",
            )
            # Connect Pareto points
            sorted_pareto = pareto_df.sort_values("x_val")
            ax.plot(
                sorted_pareto["x_val"], sorted_pareto["y_val"],
                "r--", alpha=0.7, linewidth=1.5,
            )
            for _, row in pareto_df.iterrows():
                label = f"{row.get('method_name', '')} {int(row.get('bit_width', 0))}b"
                ax.annotate(
                    label, (row["x_val"], row["y_val"]),
                    textcoords="offset points", xytext=(5, 5),
                    fontsize=8, alpha=0.8,
                )
            ax.set_xlabel(x_metric)
            ax.set_ylabel(y_metric)
            ax.set_title(f"Pareto Frontier: {y_metric} vs {x_metric}")
            ax.legend()
            ax.grid(True, alpha=0.3)

            plot_path = os.path.join(self.output_dir, f"pareto_{x_metric}_vs_{y_metric}.png")
            fig.savefig(plot_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
        except Exception as plot_err:
            plot_path = None
            logger.warning(f"Failed to generate Pareto plot: {plot_err}")

        return json.dumps({
            "x_metric": x_metric,
            "y_metric": y_metric,
            "total_points": len(df),
            "pareto_points": len(pareto_df),
            "pareto_configurations": pareto_df[
                ["experiment_id", "model_name", "method_name", "bit_width", "x_val", "y_val"]
            ].to_dict(orient="records"),
            "plot_path": plot_path,
        }, default=str)

    def _web_search(self, args: dict[str, Any]) -> str:
        """Search the web using Perplexity AI."""
        query = args["query"]

        api_key = os.getenv("PERPLEXITY_API_KEY", "")
        base_url = os.getenv("PERPLEXITY_URL", "https://api.perplexity.ai/chat/completions")
        model = os.getenv("PERPLEXITY_MODEL", "sonar-pro")

        if not api_key:
            logger.warning("PERPLEXITY_API_KEY not set, falling back to arxiv search.")
            return self._search_arxiv({"query": query, "max_results": args.get("max_results", 5)})

        try:
            import httpx

            resp = httpx.post(
                base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a research assistant helping with LLM quantization research. "
                                "Provide concise, factual answers with source URLs when available."
                            ),
                        },
                        {"role": "user", "content": query},
                    ],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = data.get("citations", [])

            result = {"answer": content, "sources": citations, "model": model}
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning(f"Perplexity search failed: {e}, falling back to arxiv.")
            return self._search_arxiv({"query": query, "max_results": args.get("max_results", 5)})
