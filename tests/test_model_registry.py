"""Tests for the dynamic model registry."""

from src.models.registry import ARCHITECTURE_TO_LLMC, ModelInfo, ModelRegistry


def test_architecture_mapping_complete():
    """Architecture mapping should cover key architectures."""
    expected = [
        "LlamaForCausalLM",
        "MistralForCausalLM",
        "OPTForCausalLM",
        "Qwen2ForCausalLM",
        "Phi3ForCausalLM",
        "BloomForCausalLM",
        "FalconForCausalLM",
        "Gemma2ForCausalLM",
    ]
    for arch in expected:
        assert arch in ARCHITECTURE_TO_LLMC, f"Missing architecture: {arch}"


def test_detect_llmc_type():
    """Registry should correctly detect LightCompress types."""
    reg = ModelRegistry.__new__(ModelRegistry)
    assert reg.detect_llmc_type("LlamaForCausalLM") == "Llama"
    assert reg.detect_llmc_type("MistralForCausalLM") == "Mistral"
    assert reg.detect_llmc_type("OPTForCausalLM") == "Opt"
    assert reg.detect_llmc_type("UnknownArchitecture") is None


def test_model_info_to_dict():
    """ModelInfo should serialise correctly."""
    info = ModelInfo(
        hf_id="test/model",
        architecture="LlamaForCausalLM",
        llmc_type="Llama",
        is_llmc_compatible=True,
        downloads=1000,
    )
    d = info.to_dict()
    assert d["hf_id"] == "test/model"
    assert d["is_llmc_compatible"] is True
    assert d["llmc_type"] == "Llama"
