"""Dataset and evaluation wrappers for LightCompress.

This module provides thin wrappers around LightCompress (LLMC) evaluation
functionality. All evaluation logic delegates to LLMC's production-tested
implementations to ensure reproducibility with published results.

LightCompress is REQUIRED - there are no fallback implementations.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

logger = logging.getLogger(__name__)


def _get_llmc_path() -> Path:
    """Get path to LightCompress installation."""
    candidates = [
        Path(__file__).parent.parent.parent / "vendors" / "lightcompress",
        Path("/u01/llm-quant-lab/vendors/lightcompress"),
    ]
    
    for path in candidates:
        if (path / "llmc").exists():
            return path
    
    raise ImportError(
        "LightCompress is REQUIRED for this project.\n"
        "Install: git clone https://github.com/ModelTC/LightCompress vendors/lightcompress\n"
        "Then: export PYTHONPATH=vendors/lightcompress:$PYTHONPATH\n"
        "Or run: make llmc-clone"
    )


def _load_module_from_file(module_name: str, file_path: Path):
    """Load a Python module directly from file, bypassing __init__.py."""
    if module_name in sys.modules:
        return sys.modules[module_name]
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _get_perplexity_eval_class():
    """Import PerplexityEval from LLMC directly."""
    llmc_path = _get_llmc_path()
    llmc_str = str(llmc_path)
    if llmc_str not in sys.path:
        sys.path.insert(0, llmc_str)
    
    # Load eval_base first (dependency)
    eval_base_path = llmc_path / "llmc" / "eval" / "eval_base.py"
    _load_module_from_file("llmc.eval.eval_base", eval_base_path)
    
    # Load eval_ppl
    eval_ppl_path = llmc_path / "llmc" / "eval" / "eval_ppl.py"
    eval_ppl = _load_module_from_file("llmc.eval.eval_ppl", eval_ppl_path)
    
    return eval_ppl.PerplexityEval


def _get_base_dataset_class():
    """Import BaseDataset from LLMC.

    LightCompress moved ``get_calib_dataset`` from a free function to a
    method on ``BaseDataset``.  This helper returns the class so callers
    can instantiate it and call ``.get_calib_dataset()`` on the instance.
    """
    llmc_path = _get_llmc_path()

    llmc_str = str(llmc_path)
    if llmc_str not in sys.path:
        sys.path.insert(0, llmc_str)

    from llmc.data.dataset import BaseDataset
    return BaseDataset


# ============================================================================
# LightCompress Perplexity Evaluation
# ============================================================================


def compute_perplexity(
    model: "PreTrainedModel",
    tokenizer: "PreTrainedTokenizerBase",
    dataset_name: str = "wikitext2",
    seq_len: int = 2048,
    batch_size: int = 1,
    download: bool = True,
) -> dict[str, float]:
    """Compute perplexity using LightCompress's PerplexityEval.

    This delegates to LLMC's evaluation code to ensure we use the exact
    same methodology as the original quantization papers.

    Args:
        model: HuggingFace model
        tokenizer: HuggingFace tokenizer
        dataset_name: Dataset to evaluate on ('wikitext2', 'c4', 'ptb')
        seq_len: Sequence length for evaluation
        batch_size: Batch size for evaluation
        download: Whether to download dataset (vs load from disk)

    Returns:
        Dictionary with 'perplexity' key

    Raises:
        ImportError: If LightCompress is not installed
    """
    from easydict import EasyDict

    PerplexityEval = _get_perplexity_eval_class()

    logger.info(f"Computing perplexity on {dataset_name} via LightCompress")

    # Check model's max sequence length and adjust if needed
    max_model_length = getattr(model.config, "max_position_embeddings", None)
    if max_model_length and seq_len > max_model_length:
        logger.warning(
            f"Requested seq_len ({seq_len}) exceeds model's max_position_embeddings "
            f"({max_model_length}). LightCompress will handle chunking internally."
        )
        # LightCompress will chunk sequences internally, so we keep the requested seq_len
        # but log a note that chunking will occur

    # Create LLMC-compatible model wrapper
    llmc_model = _LLMCModelWrapper(model, tokenizer)

    # Detect model type from model name/path
    from src.quant.llmc_wrappers import detect_model_type
    model_path = getattr(model.config, "_name_or_path", "unknown")
    llmc_model_type = detect_model_type(model_path)

    # Build config matching LLMC's expected format
    config = EasyDict({
        "eval": {
            "name": dataset_name,
            "type": "ppl",
            "seq_len": seq_len,
            "bs": batch_size,
            "download": download,
        },
        "model": {
            "type": llmc_model_type,
        },
    })

    # Run evaluation using LLMC's implementation
    evaluator = PerplexityEval(llmc_model, config)
    ppl = evaluator.eval(llmc_model)

    logger.info(f"Perplexity on {dataset_name}: {ppl:.2f}")

    return {"perplexity": ppl}


class _LLMCModelWrapper:
    """Minimal wrapper to make HuggingFace models compatible with LLMC eval.

    LLMC expects models to have certain methods like get_tokenizer(),
    get_model(), and reset_kv(). This wrapper provides that interface.
    """

    def __init__(self, model: "PreTrainedModel", tokenizer: "PreTrainedTokenizerBase"):
        self.model = model
        self._tokenizer = tokenizer
        self.mm_model = None  # Not a multimodal model

    def get_tokenizer(self) -> "PreTrainedTokenizerBase":
        return self._tokenizer

    def get_model(self) -> "PreTrainedModel":
        return self.model

    def reset_kv(self) -> None:
        """Reset KV cache if present."""
        pass


# ============================================================================
# Direct LLMC Evaluation (for LLMC model objects)
# ============================================================================


def evaluate_with_llmc(
    llmc_model,
    eval_config: dict[str, Any],
) -> dict[str, Any]:
    """Run evaluation using LightCompress directly on LLMC model objects.

    This is the preferred method when working with models loaded/quantized
    through LLMC (e.g., via LLMCRunner).

    Args:
        llmc_model: LLMC model object (from llmc.models)
        eval_config: Evaluation configuration dict with keys:
            - name: Dataset name ('wikitext2', 'c4', 'ptb')
            - type: Eval type ('ppl' for perplexity)
            - seq_len: Sequence length
            - bs: Batch size
            - download: Whether to download dataset

    Returns:
        Dictionary with evaluation results

    Raises:
        ImportError: If LightCompress is not installed
        ValueError: If eval type is not supported
    """
    from easydict import EasyDict

    PerplexityEval = _get_perplexity_eval_class()

    config = EasyDict({
        "eval": eval_config,
        "model": {"type": "unknown"},
    })

    eval_type = eval_config.get("type", "ppl")

    if eval_type == "ppl":
        evaluator = PerplexityEval(llmc_model, config)
        result = evaluator.eval(llmc_model)
        return {"perplexity": result}
    else:
        raise ValueError(f"Unsupported eval type: {eval_type}. Supported: 'ppl'")


# ============================================================================
# Calibration Data Loading
# ============================================================================


def load_calibration_data(
    dataset_name: str,
    tokenizer: "PreTrainedTokenizerBase",
    num_samples: int = 128,
    seq_length: int = 2048,
    seed: int = 42,
) -> list[torch.Tensor]:
    """Load calibration data using LightCompress's BaseDataset.

    Args:
        dataset_name: Name of the dataset ('wikitext2', 'c4', 'ptb')
        tokenizer: Tokenizer for encoding text
        num_samples: Number of calibration samples
        seq_length: Sequence length for each sample
        seed: Random seed for reproducibility

    Returns:
        List of input_ids tensors

    Raises:
        ImportError: If LightCompress is not installed
    """
    from easydict import EasyDict

    BaseDataset = _get_base_dataset_class()

    logger.info(f"Loading calibration data from {dataset_name} via LightCompress")

    # Determine the preprocessing type matching LLMC conventions
    preproc_map = {
        "wikitext2": "wikitext2_gptq",
        "c4": "c4_gptq",
        "ptb": "ptb_gptq",
        "pile": "pile_gptq",
    }
    preproc = preproc_map.get(dataset_name, "general")

    # Build LLMC-compatible config
    calib_cfg = EasyDict({
        "name": dataset_name,
        "download": True,
        "n_samples": num_samples,
        "bs": 1,
        "seq_len": seq_length,
        "preproc": preproc,
        "seed": seed,
    })

    # LLMC's BaseDataset.get_calib_dataset() reads RANK and WORLD_SIZE
    # env vars (set by torchrun). When running in-process (not via torchrun)
    # we default to single-process values.
    import os
    if "RANK" not in os.environ:
        os.environ["RANK"] = "0"
    if "WORLD_SIZE" not in os.environ:
        os.environ["WORLD_SIZE"] = "1"

    # Use BaseDataset the same way LLMC's __main__.py does
    dataset = BaseDataset(tokenizer, calib_cfg)
    calib_data, padding_mask = dataset.get_calib_dataset()

    # calib_data is typically a list of dicts with 'input_ids', 'attention_mask'
    # or a list of tensors. Normalise to list of tensors.
    calibration_data: list[torch.Tensor] = []
    if isinstance(calib_data, torch.Tensor):
        # Single batched tensor — split along batch dim
        for i in range(calib_data.size(0)):
            calibration_data.append(calib_data[i])
    elif isinstance(calib_data, (list, tuple)):
        for item in calib_data:
            if isinstance(item, dict) and "input_ids" in item:
                calibration_data.append(item["input_ids"])
            elif isinstance(item, torch.Tensor):
                calibration_data.append(item)
            else:
                calibration_data.append(torch.tensor(item))
    else:
        # Fallback: treat the whole thing as a single tensor
        calibration_data.append(torch.as_tensor(calib_data))

    logger.info(f"Loaded {len(calibration_data)} calibration samples of length {seq_length}")

    return calibration_data


# ============================================================================
# Calibration Data Fingerprinting
# ============================================================================


def fingerprint_calibration_data(calibration_data: list[torch.Tensor]) -> str:
    """Compute a deterministic SHA-256 fingerprint of calibration data.

    This allows tracking whether two experiments used identical calibration
    data, which is critical for reproducibility claims in papers.

    The hash is computed over the raw int64 byte representation of every
    tensor, concatenated in order.  It is invariant to device placement.

    Args:
        calibration_data: List of input_ids tensors (shape [seq_len]).

    Returns:
        Hex-encoded SHA-256 hash string (64 chars).
    """
    import hashlib

    h = hashlib.sha256()
    for tensor in calibration_data:
        # Move to CPU and use a deterministic dtype for hashing
        t = tensor.detach().cpu().to(torch.int64).contiguous()
        h.update(t.numpy().tobytes())
    return h.hexdigest()


# ============================================================================
# Dataset Info
# ============================================================================

SUPPORTED_DATASETS = {
    "wikitext2": "WikiText-2 (standard LLM perplexity benchmark)",
    "c4": "C4 (Colossal Clean Crawled Corpus)",
    "ptb": "Penn Treebank",
    "pile": "The Pile (validation split, used by SmoothQuant and AWQ)",
}


def list_supported_datasets() -> list[str]:
    """List datasets supported by LightCompress evaluation."""
    return list(SUPPORTED_DATASETS.keys())
