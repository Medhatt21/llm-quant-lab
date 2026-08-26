"""Integration with lm-evaluation-harness for downstream task evaluation.

Wraps ``lm_eval.simple_evaluate()`` to provide standardised
evaluation suites (quick / standard / full) and multi-seed support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Evaluation suite presets
# ============================================================================

EVALUATION_SUITES: dict[str, dict[str, Any]] = {
    "quick": {
        "tasks": ["hellaswag"],
        "description": "Fast sanity check (~2 min on 7B model)",
        "num_fewshot": {"hellaswag": 0},
    },
    "standard": {
        "tasks": ["mmlu", "hellaswag", "arc_challenge", "winogrande"],
        "description": "Standard benchmark suite for papers",
        "num_fewshot": {
            "mmlu": 5,
            "hellaswag": 10,
            "arc_challenge": 25,
            "winogrande": 5,
        },
    },
    "full": {
        "tasks": [
            "mmlu",
            "hellaswag",
            "arc_challenge",
            "winogrande",
            "piqa",
            "lambada_openai",
        ],
        "description": "Comprehensive evaluation for top-tier papers",
        "num_fewshot": {
            "mmlu": 5,
            "hellaswag": 10,
            "arc_challenge": 25,
            "winogrande": 5,
            "piqa": 0,
            "lambada_openai": 0,
        },
    },

    # Paper-specific suites matching exactly what each paper reports
    "smoothquant_175b": {
        "tasks": [
            "lambada_openai",
            "hellaswag",
            "piqa",
            "winogrande",
            "openbookqa",
            "rte",
            "copa",
        ],
        "description": "SmoothQuant Table 3: OPT-175B 7-task zero-shot accuracy",
        "num_fewshot": {
            "lambada_openai": 0,
            "hellaswag": 0,
            "piqa": 0,
            "winogrande": 0,
            "openbookqa": 0,
            "rte": 0,
            "copa": 0,
        },
    },
    "gptq_zeroshot": {
        "tasks": [
            "lambada_openai",
            "piqa",
            "arc_easy",
            "arc_challenge",
            "storycloze",
        ],
        "description": "GPTQ Tables 13-22: zero-shot accuracy on OPT/BLOOM",
        "num_fewshot": {
            "lambada_openai": 0,
            "piqa": 0,
            "arc_easy": 0,
            "arc_challenge": 0,
            "storycloze": 0,
        },
    },
    "bitnet_full": {
        "tasks": [
            "arc_easy",
            "arc_challenge",
            "hellaswag",
            "boolq",
            "openbookqa",
            "piqa",
            "winogrande",
        ],
        "description": "BitNet b1.58 Table 2: 7-task zero-shot evaluation",
        "num_fewshot": {
            "arc_easy": 0,
            "arc_challenge": 0,
            "hellaswag": 0,
            "boolq": 0,
            "openbookqa": 0,
            "piqa": 0,
            "winogrande": 0,
        },
    },
    "paretoq": {
        "tasks": [
            "arc_easy",
            "arc_challenge",
            "boolq",
            "piqa",
            "siqa",
            "hellaswag",
            "openbookqa",
            "winogrande",
        ],
        "description": "ParetoQ Tables 1-5: 8-task zero-shot evaluation",
        "num_fewshot": {
            "arc_easy": 0,
            "arc_challenge": 0,
            "boolq": 0,
            "piqa": 0,
            "siqa": 0,
            "hellaswag": 0,
            "openbookqa": 0,
            "winogrande": 0,
        },
    },
    "awq_math": {
        "tasks": ["gsm8k"],
        "description": "AWQ Table 8: GSM8K 4-shot math reasoning",
        "num_fewshot": {"gsm8k": 4},
    },
}


@dataclass
class LMEvalResult:
    """Structured result from an lm-eval run."""

    task_name: str
    metric_name: str
    value: float
    stderr: float | None = None
    num_fewshot: int = 0
    num_samples: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def run_lm_eval(
    model_path: str,
    suite: str = "standard",
    tasks: list[str] | None = None,
    device: str = "cuda",
    batch_size: str | int = "auto",
    model_args: str | None = None,
    num_fewshot: dict[str, int] | None = None,
    limit: int | None = None,
) -> list[LMEvalResult]:
    """Run lm-evaluation-harness and return structured results.

    Args:
        model_path: HuggingFace model ID or local path.
        suite: Preset suite name ("quick", "standard", "full").
        tasks: Override task list. If None, uses the suite preset.
        device: Device to run on.
        batch_size: Batch size or "auto".
        model_args: Additional model args for lm_eval.
        num_fewshot: Per-task fewshot overrides.
        limit: Max samples per task (for debugging).

    Returns:
        List of LMEvalResult objects.
    """
    try:
        import lm_eval
    except ImportError:
        raise RuntimeError(
            "lm-evaluation-harness is required. "
            "Install with: pip install lm-eval"
        )

    # Resolve suite
    suite_config = EVALUATION_SUITES.get(suite, EVALUATION_SUITES["standard"])
    task_list = tasks or suite_config["tasks"]
    fewshot_map = num_fewshot or suite_config.get("num_fewshot", {})

    # Build model args
    args_parts = [f"pretrained={model_path}"]
    if model_args:
        args_parts.append(model_args)
    full_model_args = ",".join(args_parts)

    logger.info(
        f"Running lm-eval: tasks={task_list}, model={model_path}, "
        f"device={device}, batch_size={batch_size}"
    )

    results_list: list[LMEvalResult] = []

    try:
        results = lm_eval.simple_evaluate(
            model="hf",
            model_args=full_model_args,
            tasks=task_list,
            device=device,
            batch_size=batch_size,
            limit=limit,
        )

        if results and "results" in results:
            for task_name, task_results in results["results"].items():
                for metric_key, value in task_results.items():
                    if metric_key.startswith("alias"):
                        continue
                    # lm_eval uses "acc,none", "acc_norm,none" format
                    if isinstance(value, (int, float)):
                        parts = metric_key.split(",")
                        metric_name = parts[0] if parts else metric_key
                        stderr_key = f"{metric_key}_stderr"
                        stderr = task_results.get(stderr_key)

                        results_list.append(
                            LMEvalResult(
                                task_name=task_name,
                                metric_name=metric_name,
                                value=float(value),
                                stderr=float(stderr) if stderr is not None else None,
                                num_fewshot=fewshot_map.get(task_name, 0),
                            )
                        )
    except Exception as e:
        logger.error(f"lm-eval failed: {e}")
        raise

    logger.info(f"lm-eval completed: {len(results_list)} metrics from {len(task_list)} tasks")
    return results_list


def run_multi_seed_eval(
    model_path: str,
    seeds: list[int] | None = None,
    suite: str = "standard",
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    """Run evaluation with multiple seeds and compute mean/std.

    Args:
        model_path: HuggingFace model ID or local path.
        seeds: Seeds to use (default: [42, 1337, 2024]).
        suite: Evaluation suite preset.
        **kwargs: Passed to ``run_lm_eval``.

    Returns:
        Dict keyed by ``task/metric`` with ``mean``, ``std``,
        ``values`` list, and ``seeds`` list.
    """
    import numpy as np

    seeds = seeds or [42, 1337, 2024]

    # Collect results per seed
    all_results: dict[str, list[float]] = {}

    for seed in seeds:
        logger.info(f"Running evaluation with seed={seed}")
        # lm-eval doesn't natively support seeds in simple_evaluate,
        # but we set the global seed before each run
        from ..utils.seeds import set_deterministic_seeds

        set_deterministic_seeds(seed, deterministic_algorithms=False)

        results = run_lm_eval(model_path=model_path, suite=suite, **kwargs)

        for r in results:
            key = f"{r.task_name}/{r.metric_name}"
            if key not in all_results:
                all_results[key] = []
            all_results[key].append(r.value)

    # Compute statistics
    summary: dict[str, dict[str, Any]] = {}
    for key, values in all_results.items():
        arr = np.array(values)
        summary[key] = {
            "mean": float(arr.mean()),
            "std": float(arr.std()),
            "values": values,
            "seeds": seeds,
            "n": len(values),
        }

    return summary
