# Lazy loading for eval modules to avoid importing lmms_eval upfront
# Core evals (PPL) are imported eagerly, multimodal evals are lazy

from .eval_acc import AccuracyEval
from .eval_ppl import DecodePerplexityEval, PerplexityEval
from .eval_token_consist import TokenConsistencyEval

# Lazy imports for evals that require heavy dependencies
def __getattr__(name):
    """Lazy import for multimodal and special eval classes."""
    _lazy_imports = {
        'HumanEval': '.eval_code',
        'CustomGenerate': '.eval_custom_generate',
        'CustomGenerateJustInfer': '.eval_custom_generate_just_infer',
        'VideoGenerateEval': '.eval_video_generate',
        'VQAEval': '.eval_vqa',
    }
    
    if name in _lazy_imports:
        import importlib
        module = importlib.import_module(_lazy_imports[name], __package__)
        return getattr(module, name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'AccuracyEval',
    'DecodePerplexityEval',
    'PerplexityEval',
    'TokenConsistencyEval',
    # Lazy-loaded
    'HumanEval',
    'CustomGenerate',
    'CustomGenerateJustInfer',
    'VideoGenerateEval',
    'VQAEval',
]
