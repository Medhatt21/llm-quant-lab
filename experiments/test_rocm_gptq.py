#!/usr/bin/env python3
"""Minimal test to validate ROCm + Quark + LightCompress setup.

Run this inside the container to verify the environment is working:
    python experiments/test_rocm_gptq.py

Expected output:
    - PyTorch with ROCm detected
    - GPU information displayed
    - LightCompress imports successful
    - Project wrapper imports successful
"""

import sys
from pathlib import Path

# Ensure paths are set up
WORKSPACE = Path("/workspace")
if WORKSPACE.exists():
    sys.path.insert(0, str(WORKSPACE / "vendors" / "lightcompress"))
    sys.path.insert(0, str(WORKSPACE))
else:
    # Running outside container
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT / "vendors" / "lightcompress"))
    sys.path.insert(0, str(PROJECT_ROOT))


def test_pytorch_rocm():
    """Test 1: Verify PyTorch with ROCm is available."""
    print("=" * 60)
    print("Test 1: PyTorch + ROCm")
    print("=" * 60)
    
    import torch
    
    print(f"PyTorch version: {torch.__version__}")
    
    # Check CUDA/ROCm availability
    if not torch.cuda.is_available():
        print("ERROR: CUDA/ROCm not available!")
        print("Make sure you're running inside the container with GPU access.")
        return False
    
    # Check if it's ROCm
    is_rocm = hasattr(torch.version, 'hip') and torch.version.hip is not None
    if is_rocm:
        print(f"ROCm version: {torch.version.hip}")
    else:
        print("WARNING: Running with CUDA, not ROCm")
    
    # GPU info
    gpu_count = torch.cuda.device_count()
    print(f"GPU count: {gpu_count}")
    
    for i in range(gpu_count):
        props = torch.cuda.get_device_properties(i)
        print(f"  GPU {i}: {props.name}")
        print(f"    Memory: {props.total_memory / 1e9:.1f} GB")
    
    # Quick tensor test
    x = torch.randn(100, 100, device='cuda')
    y = torch.matmul(x, x.T)
    print(f"Tensor computation test: OK (result shape: {y.shape})")
    
    print("PyTorch + ROCm: PASSED\n")
    return True


def test_lightcompress_imports():
    """Test 2: Verify LightCompress core imports work."""
    print("=" * 60)
    print("Test 2: LightCompress Core Imports")
    print("=" * 60)
    
    try:
        # Core quantization imports - these are what we need for GPTQ
        from llmc.compression.quantization import GPTQ, RTN, Awq
        print("  llmc.compression.quantization (GPTQ, RTN, Awq): OK")
        
        from llmc.data.dataset import BaseDataset
        print("  llmc.data.dataset: OK")
        
        # Registry for dynamic model loading
        from llmc.utils.registry_factory import MODEL_REGISTRY, ALGO_REGISTRY
        print("  llmc.utils.registry_factory: OK")
        
        # Base model class (doesn't trigger multimodal model imports)
        from llmc.models.base_model import BaseModel
        print("  llmc.models.base_model: OK")
        
        print("LightCompress imports: PASSED\n")
        return True
        
    except ImportError as e:
        print(f"ERROR: Import failed: {e}")
        print("Make sure PYTHONPATH includes vendors/lightcompress")
        return False


def test_project_wrappers():
    """Test 3: Verify project wrapper imports work."""
    print("=" * 60)
    print("Test 3: Project Wrappers")
    print("=" * 60)
    
    try:
        # Hardware utilities
        from src.eval.hardware import require_gpu, get_gpu_info, GPUNotAvailableError
        print("  src.eval.hardware: OK")
        
        info = get_gpu_info()
        print(f"    GPU: {info.get('name', 'Unknown')}")
        print(f"    Memory: {info.get('memory_gb', 0):.1f} GB")
        print(f"    ROCm: {info.get('is_rocm', False)}")
        
        # Quantization wrappers
        from src.quant.llmc_wrappers import (
            LLMC_AVAILABLE,
            LLMC_ALGORITHMS,
            LLMCConfig,
            create_config_from_experiment,
        )
        print("  src.quant.llmc_wrappers: OK")
        print(f"    LLMC available: {LLMC_AVAILABLE}")
        print(f"    Algorithms: {list(LLMC_ALGORITHMS.keys())[:5]}...")
        
        print("Project wrappers: PASSED\n")
        return True
        
    except ImportError as e:
        print(f"ERROR: Import failed: {e}")
        print("Make sure PYTHONPATH includes the project root")
        return False


def test_quark_available():
    """Test 4: Verify AMD Quark is available."""
    print("=" * 60)
    print("Test 4: AMD Quark")
    print("=" * 60)
    
    try:
        import quark
        print(f"Quark version: {getattr(quark, '__version__', 'unknown')}")
        print("AMD Quark: PASSED\n")
        return True
    except ImportError:
        print("WARNING: AMD Quark not installed (optional)")
        print("AMD Quark: SKIPPED\n")
        return True  # Not a failure, Quark is optional


def test_environment_variables():
    """Test 5: Verify environment variables are set correctly."""
    print("=" * 60)
    print("Test 5: Environment Variables")
    print("=" * 60)
    
    import os
    
    hf_home = os.environ.get('HF_HOME', 'NOT SET')
    pythonpath = os.environ.get('PYTHONPATH', 'NOT SET')
    
    print(f"HF_HOME: {hf_home}")
    print(f"PYTHONPATH: {pythonpath[:80]}..." if len(pythonpath) > 80 else f"PYTHONPATH: {pythonpath}")
    
    # Check if HF_HOME points to workspace
    if '/workspace' in hf_home:
        print("HF_HOME points to workspace: OK")
    else:
        print("WARNING: HF_HOME should point to /workspace/.local/cache inside container")
    
    print("Environment: PASSED\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Quant Lab - ROCm Environment Validation")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run tests
    results.append(("PyTorch + ROCm", test_pytorch_rocm()))
    results.append(("LightCompress", test_lightcompress_imports()))
    results.append(("Project Wrappers", test_project_wrappers()))
    results.append(("AMD Quark", test_quark_available()))
    results.append(("Environment", test_environment_variables()))
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All tests passed! Environment is ready.")
        print("\nNext steps:")
        print("  1. Run Quark baseline: cd $QUARK_EXAMPLES && python quantize_quark.py --model_dir facebook/opt-125m --skip_quantization")
        print("  2. Run notebook: jupyter lab --ip=0.0.0.0 --port=8888")
        return 0
    else:
        print("Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
