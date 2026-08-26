"""LightCompress (LLMC) unified quantization interface.

This module provides a research-grade interface to LightCompress
(https://github.com/ModelTC/LightCompress) for LLM quantization experiments.

LightCompress is a comprehensive toolkit supporting:
- Weight-only quantization: AWQ, GPTQ, RTN, HQQ, SpQR, OWQ, DGQ
- Weight+Activation quantization: SmoothQuant, OS+, QuaRot, QUIK
- Mixed-precision and adaptive quantization: OmniQuant, AdaDim, TesseraQ

Usage:
    from src.quant.llmc_wrappers import create_config_from_experiment, LLMCRunner
    
    config = create_config_from_experiment(
        model_path="facebook/opt-125m",
        algorithm="gptq",
        bit_width=4,
    )
    runner = LLMCRunner()
    result = runner.run_quantization(config)
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch
import yaml

from .base import (
    QuantizationState,
    QuantizationType,
    Quantizer,
    QuantizerConfig,
    register_quantizer,
)

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer

logger = logging.getLogger(__name__)


# ============================================================================
# LightCompress Installation Check
# ============================================================================

def check_llmc_installation() -> tuple[bool, str | None, Path | None]:
    """Check if LightCompress is installed and locate it.
    
    Returns:
        Tuple of (is_available, version, install_path)
    """
    # Check for local vendor installation (preferred)
    vendor_paths = [
        Path(__file__).parent.parent.parent / "vendors" / "lightcompress",
        Path(__file__).parent.parent.parent / "vendors" / "LightCompress",
        Path("/workspace/vendors/lightcompress"),  # Docker container path
    ]
    
    for vendor_path in vendor_paths:
        llmc_path = vendor_path / "llmc"
        if llmc_path.exists() and (llmc_path / "__init__.py").exists():
            # Add to sys.path if not already there
            vendor_str = str(vendor_path)
            if vendor_str not in sys.path:
                sys.path.insert(0, vendor_str)
            return True, "vendor", vendor_path
    
    # Try importing as installed package
    try:
        import llmc
        version = getattr(llmc, "__version__", "unknown")
        if llmc.__file__ is not None:
            install_path = Path(llmc.__file__).parent.parent
        else:
            install_path = None
        return True, version, install_path
    except ImportError:
        logger.debug("LLMC (LightCompress) is not installed")
    
    return False, None, None


LLMC_AVAILABLE, LLMC_VERSION, LLMC_PATH = check_llmc_installation()

if LLMC_AVAILABLE:
    logger.info(f"LightCompress available: version={LLMC_VERSION}, path={LLMC_PATH}")
else:
    logger.debug(
        "LightCompress not found. Install from: "
        "https://github.com/ModelTC/LightCompress"
    )


# ============================================================================
# LLMC Algorithm Definitions
# ============================================================================

@dataclass
class LLMCAlgorithmSpec:
    """Specification for an LLMC quantization algorithm."""
    
    name: str
    llmc_method: str
    quant_type: QuantizationType
    supported_bits: list[int]
    requires_calibration: bool
    supports_activation_quant: bool = False
    default_group_size: int = 128
    special_config: dict[str, Any] = field(default_factory=dict)
    description: str = ""


# Complete algorithm registry matching LightCompress capabilities
LLMC_ALGORITHMS: dict[str, LLMCAlgorithmSpec] = {
    # Weight-only methods
    "awq": LLMCAlgorithmSpec(
        name="awq",
        llmc_method="Awq",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[4],
        requires_calibration=True,
        special_config={"trans": True, "trans_version": "v2", "weight_clip": True},
        description="Activation-aware Weight Quantization (Lin et al., 2023)",
    ),
    "gptq": LLMCAlgorithmSpec(
        name="gptq",
        llmc_method="GPTQ",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[2, 3, 4, 8],
        requires_calibration=True,
        special_config={"actorder": True, "static_groups": False, "percdamp": 0.01, "blocksize": 128, "true_sequential": True},
        description="Accurate Post-Training Quantization (Frantar et al., 2022)",
    ),
    "rtn": LLMCAlgorithmSpec(
        name="rtn",
        llmc_method="RTN",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[2, 3, 4, 8, 16],
        requires_calibration=False,
        description="Round-To-Nearest baseline",
    ),
    "hqq": LLMCAlgorithmSpec(
        name="hqq",
        llmc_method="HQQ",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[2, 3, 4, 8],
        requires_calibration=False,
        special_config={"optimize": True},
        description="Half-Quadratic Quantization (Badri & Shaji, 2023)",
    ),
    "spqr": LLMCAlgorithmSpec(
        name="spqr",
        llmc_method="SpQR",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[3, 4],
        requires_calibration=True,
        special_config={"outlier_ratio": 0.01},
        description="Sparse-Quantized Representation (Dettmers et al., 2023)",
    ),
    "owq": LLMCAlgorithmSpec(
        name="owq",
        llmc_method="OWQ",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[3, 4],
        requires_calibration=True,
        description="Outlier-aware Weight Quantization",
    ),
    "dgq": LLMCAlgorithmSpec(
        name="dgq",
        llmc_method="DGQ",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[4],
        requires_calibration=True,
        description="Distribution-Guided Quantization",
    ),
    "llmint8": LLMCAlgorithmSpec(
        name="llmint8",
        llmc_method="LlmInt8",
        quant_type=QuantizationType.WEIGHT_ACTIVATION,
        supported_bits=[8],
        requires_calibration=False,
        supports_activation_quant=True,
        special_config={"threshold": 6.0},
        description="LLM.int8() mixed-precision decomposition (Dettmers et al., 2022)",
    ),
    
    # Weight + Activation methods
    "smoothquant": LLMCAlgorithmSpec(
        name="smoothquant",
        llmc_method="SmoothQuant",
        quant_type=QuantizationType.WEIGHT_ACTIVATION,
        supported_bits=[8],
        requires_calibration=True,
        supports_activation_quant=True,
        special_config={"alpha": 0.5, "migrate_scale": True},
        description="SmoothQuant W8A8 (Xiao et al., 2022)",
    ),
    "os+": LLMCAlgorithmSpec(
        name="os+",
        llmc_method="OsPlus",
        quant_type=QuantizationType.WEIGHT_ACTIVATION,
        supported_bits=[8],
        requires_calibration=True,
        supports_activation_quant=True,
        description="Outlier Suppression+ (Wei et al., 2023)",
    ),
    "quarot": LLMCAlgorithmSpec(
        name="quarot",
        llmc_method="QuaRot",
        quant_type=QuantizationType.WEIGHT_ACTIVATION,
        supported_bits=[4, 8],
        requires_calibration=True,
        supports_activation_quant=True,
        special_config={"rotate": True, "fp32_had": True},
        description="QuaRot rotation-based quantization (Ashkboos et al., 2024)",
    ),
    
    # Learnable/Adaptive methods
    "omniquant": LLMCAlgorithmSpec(
        name="omniquant",
        llmc_method="OmniQuant",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[2, 3, 4, 8],
        requires_calibration=True,
        special_config={"let": True, "lwc": True, "let_lr": 1e-3, "lwc_lr": 1e-2, "epochs": 20},
        description="OmniQuant learnable quantization (Shao et al., 2023)",
    ),
    "normtweaking": LLMCAlgorithmSpec(
        name="normtweaking",
        llmc_method="NormTweaking",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[4, 8],
        requires_calibration=True,
        description="Norm Tweaking for quantization",
    ),
    "tesseraq": LLMCAlgorithmSpec(
        name="tesseraq",
        llmc_method="TesseraQ",
        quant_type=QuantizationType.WEIGHT_ONLY,
        supported_bits=[2, 3, 4],
        requires_calibration=True,
        description="TesseraQ mixed-precision (Yale, 2024)",
    ),
}


# Model type detection for LLMC
# Keys are lowercase substrings matched against model_path.lower().
# Values are LightCompress model class names (must match llmc.models.__init__).
# Order matters: more specific keys must come before generic ones
# (e.g. "qwen3moe" before "qwen3" before "qwen2" before "qwen").
LLMC_MODEL_TYPES = {
    # --- Llama family ---
    "tinyllama": "Llama",
    "codellama": "Llama",
    "llama": "Llama",
    "cohere": "Llama",
    # --- OPT ---
    "opt": "Opt",
    # --- Qwen family (order: most specific first) ---
    "qwen3moe": "Qwen3Moe",
    "qwen3": "Qwen3",
    "qwen2moe": "Qwen2Moe",
    "qwen2.5vl": "Qwen2_5VL",
    "qwen2.5-vl": "Qwen2_5VL",
    "qwen2vl": "Qwen2VL",
    "qwen2audio": "Qwen2Audio",
    "qwen2": "Qwen2",
    "qwen": "Qwen2",
    # --- Mistral / Mixtral ---
    "mixtral": "Mixtral",
    "mistral": "Mistral",
    # --- InternLM / InternVL ---
    "internvl3": "InternVL3_5",
    "internvl2": "InternVL2",
    "internomni": "InternOmni",
    "internlm": "InternLM2",
    # --- Phi ---
    "phi3": "Phi3",
    "phi-3": "Phi3",
    "phi": "Phi",
    # --- Gemma ---
    "gemma2": "Gemma2",
    "gemma": "Gemma2",
    # --- Falcon ---
    "falcon": "Falcon",
    # --- DeepSeek (order: v3 before v2) ---
    "deepseekv3": "DeepseekV3",
    "deepseek-v3": "DeepseekV3",
    "deepseekv2": "DeepseekV2",
    "deepseek-v2": "DeepseekV2",
    "deepseek": "DeepseekV2",
    # --- Bloom ---
    "bloom": "Bloom",
    # --- StarCoder ---
    "starcoder": "Starcoder",
    # --- StableLM ---
    "stablelm": "StableLm",
    # --- MiniCPM ---
    "minicpmv": "MiniCPMV",
    "minicpm": "MiniCPM",
    # --- SmolLM ---
    "smollm": "SmolLM",
    # --- ChatGLM ---
    "chatglm": "ChatGLM",
    "glm4v": "GLM4V",
    # --- Multimodal / Vision-Language ---
    "llava-onevision": "Llava_OneVision",
    "llavahf": "LlavaHf",
    "llava-next": "LlavaHf",
    "llava": "Llava",
    "mllama": "Mllama",
    "videollava": "VideoLLaVA",
    "vila": "Vila",
}


def detect_model_type(model_path: str) -> str:
    """Detect LLMC model type from model path/name."""
    model_lower = model_path.lower()
    
    for key, llmc_type in LLMC_MODEL_TYPES.items():
        if key in model_lower:
            return llmc_type
    
    raise ValueError(
        f"Unknown model architecture for '{model_path}'. "
        f"Add it to LLMC_MODEL_TYPES or ARCHITECTURE_TO_LLMC. "
        f"Supported: {sorted(LLMC_MODEL_TYPES.keys())}"
    )


# ============================================================================
# LLMC Configuration Builder
# ============================================================================

@dataclass
class LLMCConfig:
    """Complete LLMC configuration for a quantization run."""
    
    # Model config
    model_type: str
    model_path: str
    torch_dtype: str = "auto"
    
    # Quantization config
    method: str = "Awq"
    weight_bit: int = 4
    weight_symmetric: bool = False
    weight_granularity: str = "per_group"
    group_size: int = 128
    
    # Activation quantization (optional)
    act_quant: bool = False
    act_bit: int = 8
    act_symmetric: bool = True
    act_granularity: str = "per_token"
    
    # Calibration config
    calib_dataset: str = "wikitext2"
    calib_n_samples: int = 128
    calib_seq_len: int = 2048
    calib_bs: int = 1
    
    # Evaluation config
    eval_datasets: list[str] = field(default_factory=lambda: ["wikitext2"])
    eval_seq_len: int = 2048
    eval_bs: int = 1
    
    # Algorithm-specific config
    special: dict[str, Any] = field(default_factory=dict)
    
    # Output config
    save_path: str | None = None
    save_vllm: bool = False
    
    # Misc
    seed: int = 42
    
    def to_yaml_dict(self) -> dict[str, Any]:
        """Convert to LLMC YAML configuration dictionary."""
        config = {
            "base": {"seed": self.seed},
            "model": {
                "type": self.model_type,
                "path": self.model_path,
                "torch_dtype": self.torch_dtype,
            },
            "calib": {
                "name": self.calib_dataset,
                "download": True,
                "n_samples": self.calib_n_samples,
                "bs": self.calib_bs,
                "seq_len": self.calib_seq_len,
                "preproc": self._get_calib_preproc(),
                "seed": self.seed,
            },
            "eval": {
                "eval_pos": ["pretrain", "fake_quant"],
                "name": self.eval_datasets[0] if self.eval_datasets else "wikitext2",
                "download": True,
                "bs": self.eval_bs,
                "seq_len": self.eval_seq_len,
                "inference_per_block": False,
            },
            "quant": {
                "method": self.method,
                "weight": {
                    "bit": self.weight_bit,
                    "symmetric": self.weight_symmetric,
                    "granularity": self.weight_granularity,
                    "group_size": self.group_size if self.weight_granularity == "per_group" else -1,
                },
                "quant_out": True,
            },
        }
        
        # Add activation quantization if enabled
        if self.act_quant:
            config["quant"]["act"] = {
                "bit": self.act_bit,
                "symmetric": self.act_symmetric,
                "granularity": self.act_granularity,
            }
        
        # Add special config
        if self.special:
            config["quant"]["special"] = self.special
        
        # Add save config
        if self.save_path:
            config["save"] = {
                "save_fake": False,
                "save_path": self.save_path,
            }
            if self.save_vllm:
                config["save"]["save_vllm"] = True
        
        return config
    
    def _get_calib_preproc(self) -> str:
        """Get calibration preprocessing type."""
        preproc_map = {
            "wikitext2": "wikitext2_gptq",
            "c4": "c4_gptq",
            "ptb": "ptb_gptq",
            "pile": "pile_gptq",
        }
        return preproc_map.get(self.calib_dataset, "general")
    
    def to_yaml_file(self, path: str | Path) -> Path:
        """Write configuration to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_yaml_dict(), f, default_flow_style=False, sort_keys=False)
        return path


# ============================================================================
# LLMC Quantization Runner
# ============================================================================

@dataclass
class LLMCQuantizationResult:
    """Result from an LLMC quantization run."""
    
    success: bool
    model_path: str
    method: str
    
    # Timing
    total_time_seconds: float = 0.0
    calibration_time_seconds: float = 0.0
    quantization_time_seconds: float = 0.0
    
    # Model info
    original_size_mb: float = 0.0
    quantized_size_mb: float = 0.0
    compression_ratio: float = 0.0
    
    # Evaluation results
    eval_results: dict[str, dict[str, float]] = field(default_factory=dict)
    
    # Layer statistics
    layer_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Errors
    error: str | None = None
    
    # Paths
    config_path: str | None = None
    output_path: str | None = None


class LLMCRunner:
    """Runner for LightCompress quantization experiments.
    
    This class provides a unified interface to run LLMC quantization.
    
    Example:
        runner = LLMCRunner()
        config = create_config_from_experiment(model_path="facebook/opt-125m", algorithm="gptq", bit_width=4)
        result = runner.run_quantization(config)
    """
    
    def __init__(self, device: str = "cuda", num_gpus: int = 1):
        """Initialize LLMC runner.
        
        Args:
            device: Device to run on
            num_gpus: Number of GPUs for distributed quantization via torchrun
        """
        if not LLMC_AVAILABLE:
            raise RuntimeError(
                "LightCompress not available. Install from: "
                "https://github.com/ModelTC/LightCompress\n"
                "Or run: make llmc-clone && set PYTHONPATH=vendors/lightcompress"
            )
        
        self.device = device
        self.num_gpus = num_gpus
        
        # Validate GPU availability (fail-fast)
        if device == "cuda" and num_gpus > 1:
            available = torch.cuda.device_count()
            if num_gpus > available:
                raise ValueError(
                    f"Requested {num_gpus} GPUs but only {available} available. "
                    f"Reduce --num-gpus or ensure all GPUs are visible via CUDA_VISIBLE_DEVICES."
                )
        
        self._validate_installation()
    
    def _validate_installation(self) -> None:
        """Validate LLMC installation."""
        try:
            from llmc.compression.quantization import Awq, GPTQ, RTN
            from llmc.models import Llama, Opt
            logger.info("LLMC installation validated")
        except ImportError as e:
            raise RuntimeError(f"LLMC installation incomplete: {e}")
    
    def run_quantization(
        self,
        config: LLMCConfig,
        capture_stats: bool = True,
    ) -> LLMCQuantizationResult:
        """Run quantization using LLMC via subprocess (CLI).
        
        This uses the LLMC CLI which is more robust and matches the official workflow.
        
        Args:
            config: LLMC configuration
            capture_stats: Whether to capture layer statistics
            
        Returns:
            LLMCQuantizationResult with all results
        """
        import subprocess
        import tempfile
        import yaml
        import re
        
        start_time = time.time()
        
        result = LLMCQuantizationResult(
            success=False,
            model_path=config.model_path,
            method=config.method,
        )
        
        try:
            # Write config to temp YAML file
            config_dict = config.to_yaml_dict()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
                yaml.dump(config_dict, f, default_flow_style=False)
                config_path = f.name
            
            logger.info(f"Running LLMC with config: {config_path}")
            logger.info(f"Model: {config.model_path}, Method: {config.method}")
            
            # Clean stale output directories from previous runs.
            # LLMC's mkdirs() raises an exception if the directory already
            # exists, so we need to remove leftover directories beforehand.
            import shutil
            if config.save_path:
                save_base = Path(config.save_path)
                for subdir in ["transformed_model", "fake_quant_model",
                               "vllm_quant_model", "lightllm_quant_model",
                               "sgl_quant_model", "autoawq_quant_model",
                               "mlcllm_quant_model", "lightx2v_quant_model",
                               "trtllm_transformed_model", "trtllm_engine"]:
                    stale = save_base / subdir
                    if stale.exists():
                        logger.info(f"Removing stale output directory: {stale}")
                        shutil.rmtree(stale)
            
            # Find a free port for distributed training
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                free_port = s.getsockname()[1]
            
            # Run LLMC via torchrun
            cmd = [
                "torchrun", f"--nproc_per_node={self.num_gpus}",
                f"--master_port={free_port}",
                "-m", "llmc",
                "--config", config_path,
                "--task_id", "0"
            ]
            
            logger.info(f"Command: {' '.join(cmd)}")
            
            # Build environment with explicit PYTHONPATH for llmc
            env = os.environ.copy()
            # Ensure PYTHONPATH includes lightcompress
            pythonpath_parts = [
                str(Path("/workspace/vendors/lightcompress")),
                str(Path("/workspace")),
            ]
            existing_pythonpath = env.get("PYTHONPATH", "")
            if existing_pythonpath:
                pythonpath_parts.append(existing_pythonpath)
            env["PYTHONPATH"] = ":".join(pythonpath_parts)
            
            # Use subprocess.run for reliable execution
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
            )
            
            # Combine stdout and stderr for parsing
            output = proc.stdout + proc.stderr
            output_lines = output.split('\n')
            
            # Parse perplexity results
            pretrain_ppl = None
            fake_quant_ppl = None
            
            for i, line in enumerate(output_lines):
                # Log progress
                if "block index:" in line or "EVAL:" in line:
                    logger.info(line.strip())
                
                # Parse perplexity results
                if "EVAL: ppl on" in line:
                    match = re.search(r"EVAL: ppl on (\w+) is ([\d.]+)", line)
                    if match:
                        dataset = match.group(1)
                        ppl = float(match.group(2))
                        
                        # Determine if pretrain or fake_quant based on context
                        if dataset not in result.eval_results:
                            result.eval_results[dataset] = {}
                        
                        # Check previous lines to determine eval position
                        context = "\n".join(output_lines[max(0, i-30):i])
                        if fake_quant_ppl is None and pretrain_ppl is not None:
                            # Second occurrence is fake_quant
                            result.eval_results[dataset]["perplexity"] = ppl
                            fake_quant_ppl = ppl
                        elif pretrain_ppl is None:
                            # First occurrence is pretrain
                            result.eval_results[dataset]["pretrain_ppl"] = ppl
                            pretrain_ppl = ppl
                        else:
                            # Subsequent occurrences update fake_quant
                            result.eval_results[dataset]["perplexity"] = ppl
                            fake_quant_ppl = ppl
            
            # Clean up temp file
            Path(config_path).unlink(missing_ok=True)
            
            if proc.returncode == 0 or "llmc finished" in output:
                result.success = True
                result.total_time_seconds = time.time() - start_time
                result.quantization_time_seconds = result.total_time_seconds
                
                # Estimate sizes (may be None for unknown models)
                estimated_size = self._estimate_model_size_from_name(config.model_path)
                if estimated_size is not None:
                    result.original_size_mb = estimated_size
                    result.quantized_size_mb = self._estimate_quantized_size(
                        result.original_size_mb, config.weight_bit, config.group_size
                    )
                    result.compression_ratio = result.original_size_mb / max(result.quantized_size_mb, 0.01)
                else:
                    logger.info(
                        f"Model size unknown for '{config.model_path}'; "
                        f"skipping size-based metrics. Add to size_map for size estimates."
                    )
                
                if config.save_path:
                    result.output_path = config.save_path
                
                logger.info(
                    f"Quantization complete: {config.method} "
                    f"({result.compression_ratio:.2f}x compression, {result.total_time_seconds:.1f}s)"
                )
                if fake_quant_ppl:
                    logger.info(f"Fake quant perplexity: {fake_quant_ppl:.2f}")
            else:
                # Extract the actual error from the subprocess output.
                # torchrun wraps the real traceback in [rank0]: prefixed lines.
                real_errors = []
                for line in output_lines:
                    stripped = line.strip()
                    # Capture rank0 traceback lines (the actual error)
                    if stripped.startswith("[rank0]:"):
                        real_errors.append(stripped.removeprefix("[rank0]:").strip())
                    # Also capture bare Exception/Error lines
                    elif "Error:" in stripped or "Exception:" in stripped:
                        real_errors.append(stripped)
                
                if real_errors:
                    # Use the last exception line as the summary
                    error_summary = real_errors[-1] if real_errors else "Unknown error"
                    result.error = f"LLMC failed: {error_summary}"
                else:
                    result.error = f"LLMC exited with code {proc.returncode}"
                
                logger.error(result.error)
                # Log the full rank0 traceback for debugging
                if real_errors:
                    logger.error("Full traceback:")
                    for line in real_errors:
                        logger.error(f"  {line}")
                else:
                    # Fallback: log last 30 lines
                    for line in output_lines[-30:]:
                        if line.strip():
                            logger.error(line.strip())
                    
        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            result.error = str(e)
            result.total_time_seconds = time.time() - start_time
        
        return result
    
    def _estimate_model_size_from_name(self, model_path: str) -> float | None:
        """Estimate model size based on model name."""
        # Common model sizes in MB
        size_map = {
            "opt-125m": 500,
            "opt-350m": 1400,
            "opt-1.3b": 5200,
            "opt-2.7b": 10800,
            "opt-6.7b": 26800,
            "opt-13b": 52000,
            "llama-7b": 28000,
            "llama-13b": 52000,
            "llama-2-7b": 28000,
            "llama-2-13b": 52000,
        }
        
        model_name = model_path.lower().split("/")[-1]
        for key, size in size_map.items():
            if key in model_name:
                return size
        
        # Unknown model size — return None so callers can handle explicitly
        return None
    
    def _estimate_model_size(self, model: torch.nn.Module) -> float:
        """Estimate model size in MB."""
        total_bytes = sum(p.numel() * p.element_size() for p in model.parameters())
        return total_bytes / (1024 * 1024)
    
    def _estimate_quantized_size(self, original_size_mb: float, bit_width: int, group_size: int) -> float:
        """Estimate quantized model size."""
        base_ratio = bit_width / 16
        overhead = 1 + (32 / (group_size * bit_width)) if group_size > 0 else 1.01
        return original_size_mb * base_ratio * overhead
    
    def _run_evaluation(
        self, llmc_model, datasets: list[str], seq_len: int, batch_size: int
    ) -> dict[str, dict[str, float]]:
        """Run perplexity evaluation on datasets."""
        from easydict import EasyDict
        from llmc.eval.eval_ppl import PerplexityEval
        
        results = {}
        
        for dataset_name in datasets:
            try:
                eval_cfg = EasyDict({
                    "eval": {
                        "name": dataset_name,
                        "download": True,
                        "seq_len": seq_len,
                        "bs": batch_size,
                    },
                    "model": {"type": llmc_model.__class__.__name__},
                })
                
                evaluator = PerplexityEval(llmc_model, eval_cfg)
                ppl = evaluator.eval(llmc_model)
                
                results[dataset_name] = {"perplexity": ppl}
                logger.info(f"  {dataset_name} perplexity: {ppl:.2f}")
                
            except Exception as e:
                raise RuntimeError(
                    f"Evaluation failed on {dataset_name}: {e}"
                ) from e
        
        return results


# ============================================================================
# Simplified Quantizer Interface (wraps LLMCRunner)
# ============================================================================

class LLMCQuantizer(Quantizer):
    """Unified quantizer using LightCompress backend.
    
    This is a simplified wrapper that provides the standard Quantizer interface
    while delegating to LLMCRunner for actual quantization.
    """
    
    def __init__(self, config: QuantizerConfig, algorithm: str):
        self._algorithm = algorithm.lower()
        if self._algorithm not in LLMC_ALGORITHMS:
            raise ValueError(f"Unknown algorithm: {algorithm}. Available: {list(LLMC_ALGORITHMS.keys())}")
        
        self._spec = LLMC_ALGORITHMS[self._algorithm]
        self._runner: LLMCRunner | None = None
        super().__init__(config)
    
    def _validate_dependencies(self) -> None:
        if not LLMC_AVAILABLE:
            raise ImportError("LightCompress required. See: https://github.com/ModelTC/LightCompress")
    
    @property
    def name(self) -> str:
        return self._algorithm
    
    @property
    def quantization_type(self) -> QuantizationType:
        return self._spec.quant_type
    
    @property
    def supported_bit_widths(self) -> list[int]:
        return self._spec.supported_bits
    
    @property
    def requires_calibration(self) -> bool:
        return self._spec.requires_calibration
    
    @property
    def backend_name(self) -> str:
        return f"LightCompress/{self._spec.llmc_method}"
    
    def prepare(self, model: "PreTrainedModel", calibration_data=None) -> QuantizationState:
        model_path = getattr(model.config, "_name_or_path", "unknown")
        return QuantizationState(
            model_name=model_path,
            original_dtype=next(model.parameters()).dtype,
            original_size_mb=self.estimate_model_size(model),
            method=self.name,
            bit_width=self.config.bit_width,
            per_channel=not self.config.group_size,
            symmetric=self.config.symmetric,
            group_size=self.config.group_size,
        )
    
    def apply(self, model: "PreTrainedModel", state: QuantizationState) -> "PreTrainedModel":
        """Apply quantization in-process via the full LightCompress pipeline.

        Uses LLMC's MODEL_REGISTRY + ALGO_REGISTRY, matching the same flow
        as ``llmc/__main__.py`` so every algorithm works out of the box.

        Args:
            model: HuggingFace model (unused directly — LLMC reloads from path).
            state: QuantizationState from ``prepare()``.

        Returns:
            The quantized model.
        """
        if not LLMC_AVAILABLE:
            raise ImportError("LightCompress is required for in-process quantization.")

        import gc
        import os

        import torch
        import torch.distributed as dist
        from easydict import EasyDict

        try:
            from llmc.data import BaseDataset
            from llmc.utils.registry_factory import ALGO_REGISTRY, MODEL_REGISTRY
            from llmc.utils import get_modality

            # Importing the submodules triggers @ALGO_REGISTRY / @MODEL_REGISTRY
            # decorators which populate the registries.
            import llmc.compression.quantization  # noqa: F401
            import llmc.models  # noqa: F401

            model_path = getattr(model.config, "_name_or_path", "unknown")
            model_type = detect_model_type(model_path)

            if model_type is None:
                raise ValueError(
                    f"Cannot detect LLMC model type for '{model_path}'. "
                    f"Supported types: {list(LLMC_MODEL_TYPES.keys())}"
                )

            # Ensure RANK/WORLD_SIZE are set (required by LLMC internals)
            os.environ.setdefault("RANK", "0")
            os.environ.setdefault("WORLD_SIZE", "1")
            os.environ.setdefault("LOCAL_RANK", "0")
            os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
            os.environ.setdefault("MASTER_PORT", "29500")

            # LLMC uses torch.distributed internally (e.g. all_reduce in GPTQ).
            # Initialize a single-process group if not already done.
            _dist_initialized_here = False
            if not dist.is_initialized():
                dist.init_process_group(backend="nccl", world_size=1, rank=0)
                torch.cuda.set_device(0)
                _dist_initialized_here = True

            # Build LLMC-compatible config (mirrors a YAML config file)
            # Build the quant config with method-specific 'special' defaults
            # that mirror the typical LLMC YAML config files.
            method_name = self._spec.llmc_method

            # Sensible defaults for each algorithm's special config
            special_defaults = {
                "GPTQ": {
                    "true_sequential": True,
                    "static_groups": False,
                    "actorder": True,
                    "percdamp": 0.01,
                    "blocksize": 128,
                },
                "Awq": {
                    "trans": True,
                    "trans_version": "v2",
                    "weight_clip": True,
                },
                "SmoothQuant": {
                    "alpha": 0.5,
                    "trans": True,
                },
                "OsPlus": {
                    "trans": True,
                },
                "SpQR": {
                    "percents": [1.0],
                    "perm": True,
                },
                "OmniQuant": {
                    "let": True,
                    "lwc": True,
                    "epochs": 20,
                    "lr": 1e-2,
                },
                "Quarot": {
                    "rotate": True,
                },
            }

            quant_cfg = {
                "method": method_name,
                "weight": {
                    "bit": self.config.bit_width,
                    "symmetric": getattr(self.config, "symmetric", False),
                    "granularity": "per_group" if self.config.group_size else "per_channel",
                    "group_size": self.config.group_size or -1,
                },
                "special": special_defaults.get(method_name, {}),
            }

            calib_cfg = {
                "name": getattr(self.config, "calib_dataset", "wikitext2"),
                "download": True,
                "n_samples": getattr(self.config, "calib_size", 128),
                "bs": 1,
                "seq_len": getattr(self.config, "calib_seq_length", 2048),
                "preproc": "wikitext2_gptq",
                "seed": 42,
            }

            llmc_config = EasyDict({
                "model": {
                    "type": model_type,
                    "path": model_path,
                    "torch_dtype": "auto",
                },
                "calib": calib_cfg,
                "quant": quant_cfg,
                "base": {"seed": 42},
            })

            logger.info(f"LLMC pipeline: model_type={model_type}, method={self._spec.llmc_method}")

            # Resolve modalities the same way __main__.py does
            modalities, modality_configs = get_modality(llmc_config)

            # 1. Create LLMC model wrapper via its registry.
            #    Pass device_map="auto" so the model loads directly onto GPU.
            llmc_model = MODEL_REGISTRY[model_type](llmc_config, device_map="auto")

            for modality, modality_config in zip(modalities, modality_configs):
                llmc_model.set_modality(modality)

                # 2. Load calibration data
                dataset = BaseDataset(
                    llmc_model.get_tokenizer(), llmc_config.calib, llmc_model.batch_process
                )
                calib_data, padding_mask = dataset.get_calib_dataset()

                # 3. Collect first block input (LLMC does internal hooks)
                llmc_model.collect_first_block_input(calib_data, padding_mask)
                del calib_data
                gc.collect()
                torch.cuda.empty_cache()

                # 4. Create and run the compressor
                compressor = ALGO_REGISTRY[modality_config.method](
                    llmc_model,
                    modality_config,
                    llmc_model.get_first_block_input(),
                    llmc_model.get_padding_mask(),
                    llmc_config,
                )
                compressor.run_block_loop()

            logger.info(
                f"In-process quantization complete: {self._spec.llmc_method} "
                f"@ {self.config.bit_width}-bit"
            )

            # Return the underlying HF model from the LLMC wrapper
            return llmc_model.model

        except Exception as exc:
            raise RuntimeError(
                f"In-process quantization failed for {self._spec.llmc_method}: {exc}.\n"
                "Troubleshooting:\n"
                "  1. Verify LLMC is installed: pip install -e ./LightCompress\n"
                "  2. Check that the quantization algorithm exists in llmc.compression.quantization\n"
                "  3. Ensure CUDA/ROCm is available and the model is on the correct device\n"
                "  4. Run with LOG_LEVEL=DEBUG for detailed tracing"
            ) from exc
        finally:
            # Clean up the process group if we initialized it
            if _dist_initialized_here and dist.is_initialized():
                try:
                    dist.destroy_process_group()
                except Exception:
                    pass
    
    def metadata(self, state: QuantizationState) -> dict[str, Any]:
        return {
            "method": self.name,
            "llmc_method": self._spec.llmc_method,
            "backend": self.backend_name,
            "description": self._spec.description,
            "bit_width": state.bit_width,
            "group_size": state.group_size,
        }
    
    def save(self, model: "PreTrainedModel", state: QuantizationState, path: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
        model.save_pretrained(path)
    
    def load(self, path: str) -> "PreTrainedModel":
        from transformers import AutoModelForCausalLM
        return AutoModelForCausalLM.from_pretrained(path, device_map="auto", trust_remote_code=True)

    def export_for_vllm(self, model_path: str, save_path: str) -> str:
        """Export a quantized model in vLLM-compatible format.

        This uses LightCompress's ``update_vllm_quant_config`` to patch the
        saved model's ``config.json`` with the ``compressed-tensors`` quantization
        metadata that vLLM expects.

        Args:
            model_path: Path to the *already-saved* quantized model directory
                        (i.e. ``state.output_path`` or ``config.save_path``).
            save_path:  Path where the vLLM-compatible model should be written.
                        If it differs from *model_path* the directory is copied first.

        Returns:
            Absolute path to the vLLM-ready model directory.

        Raises:
            RuntimeError: If the export fails for any reason.
        """
        import json
        import shutil
        from easydict import EasyDict

        try:
            model_dir = Path(model_path).resolve()
            export_dir = Path(save_path).resolve()

            if not model_dir.exists():
                raise FileNotFoundError(
                    f"Quantized model directory not found: {model_dir}"
                )

            # Copy to export location if different
            if export_dir != model_dir:
                if export_dir.exists():
                    shutil.rmtree(export_dir)
                shutil.copytree(model_dir, export_dir)

            # Build a minimal EasyDict config matching what update_vllm_quant_config expects
            quant_cfg: dict[str, Any] = {
                "weight": {
                    "bit": self.config.bit_width,
                    "symmetric": self.config.symmetric,
                    "granularity": "per_group" if self.config.group_size else "per_channel",
                    "group_size": self.config.group_size or -1,
                    "quant_type": "int-quant",
                },
            }
            if self.config.activation_quant:
                quant_cfg["act"] = {
                    "bit": self.config.activation_bits or 8,
                    "symmetric": True,
                    "granularity": "per_token",
                    "quant_type": "int-quant",
                }
            cfg = EasyDict({"quant": quant_cfg})

            # Create a minimal model stub with skip_layer_name
            class _ModelStub:
                def skip_layer_name(self) -> list[str]:
                    return ["lm_head"]

            from vendors.lightcompress.llmc.utils.export_vllm import update_vllm_quant_config

            update_vllm_quant_config(
                model=_ModelStub(),
                config=cfg,
                save_quant_path=str(export_dir),
            )

            logger.info(f"vLLM export complete: {export_dir}")
            return str(export_dir)

        except Exception as exc:
            raise RuntimeError(
                f"vLLM export failed for model at '{model_path}': {exc}.\n"
                "Ensure the quantized model was saved correctly and "
                "LightCompress is installed."
            ) from exc


# ============================================================================
# Register All LLMC Quantizers
# ============================================================================

def _create_quantizer_class(algorithm: str) -> type[LLMCQuantizer]:
    """Factory to create quantizer class for an algorithm."""
    class _SpecificQuantizer(LLMCQuantizer):
        def __init__(self, config: QuantizerConfig):
            super().__init__(config, algorithm=algorithm)
    
    _SpecificQuantizer.__name__ = f"{algorithm.upper()}Quantizer"
    return _SpecificQuantizer


if LLMC_AVAILABLE:
    for algo_name in LLMC_ALGORITHMS:
        register_quantizer(algo_name, _create_quantizer_class(algo_name))
    logger.info(f"Registered {len(LLMC_ALGORITHMS)} LLMC quantizers")


# ============================================================================
# Utility Functions
# ============================================================================

def get_smoothquant_alpha(model_path: str) -> float:
    """Return the paper-recommended SmoothQuant alpha for a given model.

    Values from the SmoothQuant paper (Tables 6-7) and follow-up experiments.
    Users can always override via ``special_config``.
    """
    name = model_path.lower()
    rules: list[tuple[list[str], float]] = [
        (["llama-2-70b", "llama2-70b"], 0.9),
        (["llama-2-7b", "llama-2-13b", "llama2-7b", "llama2-13b"], 0.85),
        (["llama"], 0.8),
        (["mistral", "mixtral"], 0.8),
        (["glm-130b", "glm130b", "chatglm"], 0.75),
        (["falcon-40b"], 0.7),
        (["falcon"], 0.6),
        (["opt", "bloom"], 0.5),
    ]
    for patterns, alpha in rules:
        for pat in patterns:
            if pat in name:
                return alpha
    return 0.5


def list_algorithms() -> list[str]:
    """List available quantization algorithms."""
    return list(LLMC_ALGORITHMS.keys())


def get_algorithm_spec(algorithm: str) -> LLMCAlgorithmSpec | None:
    """Get specification for an algorithm."""
    return LLMC_ALGORITHMS.get(algorithm.lower())


def create_config_from_experiment(
    model_path: str,
    algorithm: str,
    bit_width: int = 4,
    group_size: int = 128,
    calib_dataset: str = "wikitext2",
    calib_samples: int = 128,
    calib_seq_len: int = 2048,
    eval_datasets: list[str] | None = None,
    save_path: str | None = None,
    **extra_config,
) -> LLMCConfig:
    """Create LLMC config from experiment parameters.
    
    This is the main entry point for creating quantization configs programmatically.
    
    Args:
        model_path: HuggingFace model path
        algorithm: Quantization algorithm (gptq, awq, rtn, etc.)
        bit_width: Target bit width
        group_size: Quantization group size
        calib_dataset: Calibration dataset
        calib_samples: Number of calibration samples
        calib_seq_len: Calibration sequence length
        eval_datasets: Evaluation datasets
        save_path: Path to save quantized model
        **extra_config: Additional algorithm-specific config
        
    Returns:
        LLMCConfig ready for use with LLMCRunner
    """
    spec = LLMC_ALGORITHMS.get(algorithm.lower())
    if spec is None:
        raise ValueError(f"Unknown algorithm: {algorithm}. Available: {list(LLMC_ALGORITHMS.keys())}")
    
    config = LLMCConfig(
        model_type=detect_model_type(model_path),
        model_path=model_path,
        method=spec.llmc_method,
        weight_bit=bit_width,
        weight_granularity="per_group" if group_size > 0 else "per_channel",
        group_size=group_size,
        act_quant=spec.supports_activation_quant,
        calib_dataset=calib_dataset,
        calib_n_samples=calib_samples,
        calib_seq_len=calib_seq_len,
        eval_datasets=eval_datasets or ["wikitext2"],
        save_path=save_path,
        special=spec.special_config.copy(),
    )
    
    # Merge extra config
    config.special.update(extra_config)
    
    return config
