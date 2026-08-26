"""Deterministic seed enforcement for reproducibility.

Sets seeds for Python, NumPy, PyTorch, and CUDA.
Optionally enables ``torch.use_deterministic_algorithms``.
"""

from __future__ import annotations

import logging
import os
import random
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SEED = 42


def set_deterministic_seeds(
    seed: int = DEFAULT_SEED,
    deterministic_algorithms: bool = True,
) -> dict[str, Any]:
    """Set all random seeds and optionally enable deterministic algorithms.

    Args:
        seed: Random seed to use everywhere.
        deterministic_algorithms: If True, call
            ``torch.use_deterministic_algorithms(True)`` (may raise errors
            for non-deterministic ops).

    Returns:
        Dict describing what was set.
    """
    report: dict[str, Any] = {"seed": seed}

    # 1. Python stdlib
    random.seed(seed)
    report["python"] = True

    # 2. NumPy
    try:
        import numpy as np

        np.random.seed(seed)
        report["numpy"] = True
    except ImportError:
        report["numpy"] = False

    # 3. PyTorch
    try:
        import torch

        torch.manual_seed(seed)
        report["torch"] = True

        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            report["cuda"] = True
        else:
            report["cuda"] = False

        # Deterministic algorithms
        if deterministic_algorithms:
            try:
                torch.use_deterministic_algorithms(True)
                # Allow CUDA fallback for operations that don't have deterministic impl
                os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
                report["deterministic_algorithms"] = True
            except Exception as e:
                logger.warning(f"Could not enable deterministic algorithms: {e}")
                report["deterministic_algorithms"] = False
        else:
            report["deterministic_algorithms"] = False

        # Disable benchmark for reproducibility
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        report["cudnn_deterministic"] = True

    except ImportError:
        report["torch"] = False

    # 4. Hash seed
    os.environ["PYTHONHASHSEED"] = str(seed)
    report["hash_seed"] = True

    logger.info(f"Deterministic seeds set: seed={seed}")
    return report
