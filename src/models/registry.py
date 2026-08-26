"""Dynamic model registry using HuggingFace Hub API.

Instead of the static ``LLMC_MODEL_TYPES`` dict (16 entries) in
``llmc_wrappers.py``, this module maps **all** HuggingFace
architecture strings to their LightCompress model class names.

The frontend can call ``/api/models/search`` which uses this
registry to tag every HF model with a LightCompress compatibility
badge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Complete HuggingFace architecture -> LightCompress type mapping
# ============================================================================
# Built from `vendors/lightcompress/llmc/models/__init__.py`.

ARCHITECTURE_TO_LLMC: dict[str, str] = {
    # --- Eagerly loaded models ---
    "LlamaForCausalLM": "Llama",
    "MistralForCausalLM": "Mistral",
    "MixtralForCausalLM": "Mixtral",
    "OPTForCausalLM": "Opt",
    "BloomForCausalLM": "Bloom",
    "FalconForCausalLM": "Falcon",
    "Gemma2ForCausalLM": "Gemma2",
    "GemmaForCausalLM": "Gemma2",
    "PhiForCausalLM": "Phi",
    "Phi3ForCausalLM": "Phi3",
    "PhiMoEForCausalLM": "Phi3",
    "Qwen2ForCausalLM": "Qwen2",
    "QwenForCausalLM": "Qwen",
    "Qwen3ForCausalLM": "Qwen3",
    "Qwen2MoeForCausalLM": "Qwen2Moe",
    "Qwen3MoeForCausalLM": "Qwen3Moe",
    "DeepseekV2ForCausalLM": "DeepseekV2",
    "DeepseekV3ForCausalLM": "DeepseekV3",
    "MiniCPMForCausalLM": "MiniCPM",
    "StableLmForCausalLM": "StableLm",
    "GPTBigCodeForCausalLM": "Starcoder",
    "ChatGLMForConditionalGeneration": "ChatGLM",
    "ChatGLMModel": "ChatGLM",
    "SmolLMForCausalLM": "SmolLM",
    # --- Lazy-loaded / multimodal models ---
    "InternLM2ForCausalLM": "InternLM2",
    "InternVLChatModel": "InternVL2",
    "LlavaForConditionalGeneration": "Llava",
    "LlavaNextForConditionalGeneration": "LlavaHf",
    "MllamaForConditionalGeneration": "Mllama",
    "Qwen2VLForConditionalGeneration": "Qwen2VL",
    "Qwen2AudioForConditionalGeneration": "Qwen2Audio",
    # Common aliases / older architectures
    "LLaMAForCausalLM": "Llama",
    "CodeLlamaForCausalLM": "Llama",
    "CohereForCausalLM": "Llama",
    "StarcoderForCausalLM": "Starcoder",
}


# ============================================================================
# Data model
# ============================================================================


@dataclass
class ModelInfo:
    """HuggingFace model annotated with LightCompress compatibility."""

    hf_id: str
    architecture: str = "unknown"
    llmc_type: str | None = None
    is_llmc_compatible: bool = False
    downloads: int = 0
    likes: int = 0
    size_category: str = "unknown"
    pipeline_tag: str | None = None
    tags: list[str] = field(default_factory=list)
    # Extra metadata from HF
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hf_id": self.hf_id,
            "architecture": self.architecture,
            "llmc_type": self.llmc_type,
            "is_llmc_compatible": self.is_llmc_compatible,
            "downloads": self.downloads,
            "likes": self.likes,
            "size_category": self.size_category,
            "pipeline_tag": self.pipeline_tag,
            "tags": self.tags,
        }


# ============================================================================
# Registry
# ============================================================================


class ModelRegistry:
    """Dynamic model registry backed by HuggingFace Hub API."""

    def __init__(self) -> None:
        self._api: Any = None

    @property
    def api(self) -> Any:
        if self._api is None:
            try:
                from huggingface_hub import HfApi

                self._api = HfApi()
            except ImportError:
                raise RuntimeError(
                    "huggingface_hub is required for the model registry. "
                    "Install with: pip install huggingface_hub"
                )
        return self._api

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_models(
        self,
        query: str,
        limit: int = 20,
        compatible_only: bool = False,
    ) -> list[ModelInfo]:
        """Search HuggingFace Hub with LightCompress compatibility tagging.

        Args:
            query: Search string (model name, architecture, etc.).
            limit: Max results.
            compatible_only: If True, filter to compatible models only.

        Returns:
            List of ModelInfo with compatibility badges.
        """
        try:
            models = list(
                self.api.list_models(
                    search=query,
                    pipeline_tag="text-generation",
                    sort="downloads",
                    direction=-1,
                    limit=limit * 2 if compatible_only else limit,
                    fetch_config=True,
                )
            )
        except Exception as e:
            raise ConnectionError(
                f"HuggingFace Hub search failed: {e}. "
                f"Check your network connection and HF_TOKEN."
            ) from e

        results: list[ModelInfo] = []
        for m in models:
            info = self._enrich_with_compatibility(m)
            if compatible_only and not info.is_llmc_compatible:
                continue
            results.append(info)
            if len(results) >= limit:
                break

        return results

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Get detailed info for a single model."""
        try:
            m = self.api.model_info(model_id)
            return self._enrich_with_compatibility(m)
        except Exception as e:
            raise ValueError(
                f"Failed to retrieve model info for '{model_id}': {e}."
            ) from e

    def check_compatibility(self, model_id: str) -> tuple[bool, str | None]:
        """Check if a model is compatible with LightCompress.

        Returns:
            (is_compatible, llmc_type or None)
        """
        info = self.get_model_info(model_id)
        return info.is_llmc_compatible, info.llmc_type

    def detect_llmc_type(self, architecture: str) -> str | None:
        """Map a HuggingFace architecture string to LightCompress type."""
        return ARCHITECTURE_TO_LLMC.get(architecture)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _enrich_with_compatibility(self, model: Any) -> ModelInfo:
        """Tag a HF model with LightCompress compatibility info."""
        architectures: list[str] = []
        llmc_type: str | None = None

        # Try to get architectures from model config
        if hasattr(model, "config") and model.config:
            cfg = model.config
            if isinstance(cfg, dict):
                architectures = cfg.get("architectures", [])
            elif hasattr(cfg, "architectures"):
                architectures = getattr(cfg, "architectures", []) or []

        # If config not available, try tags
        if not architectures and hasattr(model, "tags"):
            for tag in (model.tags or []):
                if tag in ARCHITECTURE_TO_LLMC:
                    architectures = [tag]
                    break

        # Match architecture from config
        for arch in architectures:
            if arch in ARCHITECTURE_TO_LLMC:
                llmc_type = ARCHITECTURE_TO_LLMC[arch]
                break

        # Fallback: detect from model name using the same logic as the
        # quantization runner (LLMC_MODEL_TYPES in llmc_wrappers.py).
        # This catches models where HF list_models() doesn't return config.
        model_id = getattr(model, "id", getattr(model, "modelId", "unknown"))
        if llmc_type is None:
            llmc_type = self._detect_from_name(model_id)

        # Estimate size category
        size_cat = "unknown"
        if hasattr(model, "safetensors") and model.safetensors:
            params = getattr(model.safetensors, "total", 0)
            if params:
                size_cat = self._size_category(params)

        downloads = getattr(model, "downloads", 0) or 0
        likes = getattr(model, "likes", 0) or 0
        pipeline_tag = getattr(model, "pipeline_tag", None)
        tags = list(getattr(model, "tags", []) or [])

        return ModelInfo(
            hf_id=model_id,
            architecture=architectures[0] if architectures else "unknown",
            llmc_type=llmc_type,
            is_llmc_compatible=llmc_type is not None,
            downloads=downloads,
            likes=likes,
            size_category=size_cat,
            pipeline_tag=pipeline_tag,
            tags=tags,
        )

    @staticmethod
    def _detect_from_name(model_id: str) -> str | None:
        """Detect LightCompress type from model name/path.

        Uses the same name-based detection as the quantization runner
        so that any model the runner can quantize is tagged as compatible.
        """
        try:
            from src.quant.llmc_wrappers import LLMC_MODEL_TYPES

            model_lower = model_id.lower()
            for key, llmc_type in LLMC_MODEL_TYPES.items():
                if key in model_lower:
                    return llmc_type
        except ImportError:
            pass
        return None

    @staticmethod
    def _size_category(num_params: int) -> str:
        """Human-friendly size label from parameter count."""
        b = num_params / 1e9
        if b < 0.5:
            return f"{num_params / 1e6:.0f}M"
        elif b < 1.5:
            return f"{b:.1f}B"
        else:
            return f"{b:.0f}B"
