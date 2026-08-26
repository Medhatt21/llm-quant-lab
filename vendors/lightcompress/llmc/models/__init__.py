# Lazy loading to avoid importing heavy multimodal dependencies upfront
# Core models are imported eagerly, multimodal models are lazy

from .base_model import BaseModel
from .bloom import Bloom
from .chatglm import ChatGLM
from .deepseekv2 import DeepseekV2
from .deepseekv3 import DeepseekV3
from .falcon import Falcon
from .gemma2 import Gemma2
from .llama import Llama
from .minicpm import MiniCPM
from .mistral import Mistral
from .mixtral import Mixtral
from .opt import Opt
from .phi import Phi
from .phi3 import Phi3
from .qwen import Qwen
from .qwen2 import Qwen2
from .qwen2moe import Qwen2Moe
from .qwen3 import Qwen3
from .qwen3moe import Qwen3Moe
from .smollm import SmolLM
from .stablelm import StableLm
from .starcoder import Starcoder

# Lazy imports for multimodal models that require lmms_eval
def __getattr__(name):
    """Lazy import for multimodal models."""
    _lazy_imports = {
        'InternLM2': '.internlm2',
        'InternOmni': '.internomni',
        'InternVL2': '.internvl2',
        'InternVL3_5': '.internvl3_5',
        'GLM4V': '.glm4v',
        'Llava': '.llava',
        'LlavaHf': '.llava_hf',
        'Llava_OneVision': '.llava_onevision',
        'MiniCPMV': '.minicpmv',
        'Mllama': '.mllama',
        'Qwen2_5VL': '.qwen2_5vl',
        'Qwen2Audio': '.qwen2audio',
        'Qwen2VL': '.qwen2vl',
        'VideoLLaVA': '.videollava',
        'Vila': '.vila',
        'Vit': '.vit',
        'WanI2V': '.wan_i2v',
        'WanT2V': '.wan_t2v',
    }
    
    if name in _lazy_imports:
        import importlib
        module = importlib.import_module(_lazy_imports[name], __package__)
        return getattr(module, name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Only include eagerly loaded classes in __all__ to avoid triggering lazy imports on 'from llmc.models import *'
__all__ = [
    'BaseModel',
    'Bloom',
    'ChatGLM',
    'DeepseekV2',
    'DeepseekV3',
    'Falcon',
    'Gemma2',
    'Llama',
    'MiniCPM',
    'Mistral',
    'Mixtral',
    'Opt',
    'Phi',
    'Phi3',
    'Qwen',
    'Qwen2',
    'Qwen2Moe',
    'Qwen3',
    'Qwen3Moe',
    'SmolLM',
    'StableLm',
    'Starcoder',
]
