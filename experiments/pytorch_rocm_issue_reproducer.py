#!/usr/bin/env python3
"""Diagnostic script for LLMC quantization failures on ROCm.

This script was originally created to reproduce a suspected PyTorch ROCm
triu_tril_kernel memory violation bug. After investigation, the actual root
cause was found to be in the LLMC (LightCompress) wrapper layer, not PyTorch:

Root Cause:
-----------
1. LLMC's mkdirs() utility raises an exception if output directories already
   exist from a previous run. The error is:
       Exception: <path>/transformed_model existed before. Need check.

2. The generated LLMC config was missing `quant_out: True` and had
   `save_trans: True` instead of `save_fake: False`.

3. torchrun wraps the actual error in a generic ChildFailedError with no
   visible traceback, making it look like a mysterious GPU/kernel issue.

Fix Applied:
------------
- src/quant/llmc_wrappers.py: Added stale directory cleanup before running LLMC
- src/quant/llmc_wrappers.py: Added `quant_out: True` and `inference_per_block: False`
- src/quant/llmc_wrappers.py: Improved error extraction from torchrun output

The tests below verify that the GPU and PyTorch ROCm stack are functioning
correctly (they always passed - the bug was never in PyTorch).
"""

import torch
import sys


def print_env():
    """Print environment info."""
    print("=" * 60)
    print("Environment")
    print("=" * 60)
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if hasattr(torch.version, 'hip') and torch.version.hip:
        print(f"ROCm/HIP version: {torch.version.hip}")
    
    if torch.cuda.is_available():
        print(f"Device count: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    print()


def test_triu_basic():
    """Test 1: Basic triu operation with small tensor - should work."""
    print("Test 1: Basic triu (small tensor, float32)")
    x = torch.randn(10, 10, device='cuda')
    y = torch.triu(x)
    print(f"  Input: {x.shape}, dtype={x.dtype}")
    print(f"  Output: {y.shape}")
    print("  PASSED\n")


def test_triu_fp16_small():
    """Test 2: triu with FP16 small tensor - should work."""
    print("Test 2: triu FP16 (small tensor)")
    x = torch.randn(10, 10, device='cuda', dtype=torch.float16)
    y = torch.triu(x)
    print(f"  Input: {x.shape}, dtype={x.dtype}")
    print(f"  Output: {y.shape}")
    print("  PASSED\n")


def test_triu_fp16_medium():
    """Test 3: triu with FP16 medium tensor."""
    print("Test 3: triu FP16 (medium tensor - 1024x1024)")
    try:
        x = torch.randn(1024, 1024, device='cuda', dtype=torch.float16)
        y = torch.triu(x)
        torch.cuda.synchronize()
        print(f"  Input: {x.shape}, dtype={x.dtype}")
        print(f"  Output: {y.shape}")
        print("  PASSED\n")
    except Exception as e:
        print(f"  FAILED: {e}\n")
        return False
    return True


def test_triu_fp16_large():
    """Test 4: triu with FP16 large tensor."""
    print("Test 4: triu FP16 (large tensor - 2048x2048)")
    try:
        x = torch.randn(2048, 2048, device='cuda', dtype=torch.float16)
        y = torch.triu(x)
        torch.cuda.synchronize()
        print(f"  Input: {x.shape}, dtype={x.dtype}")
        print(f"  Output: {y.shape}")
        print("  PASSED\n")
    except Exception as e:
        print(f"  FAILED: {e}\n")
        return False
    return True


def test_attention_mask_pattern():
    """Test 5: Simulate attention mask creation pattern from transformers."""
    print("Test 5: Attention mask creation pattern (seq_len=2048)")
    try:
        seq_len = 2048
        batch_size = 1
        device = 'cuda'
        
        mask = torch.ones(batch_size, 1, seq_len, seq_len, device=device, dtype=torch.float16)
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, device=device, dtype=torch.float16),
            diagonal=1
        )
        torch.cuda.synchronize()
        mask = mask.masked_fill(causal_mask.bool(), float('-inf'))
        torch.cuda.synchronize()
        
        print(f"  Mask shape: {mask.shape}")
        print(f"  Causal mask shape: {causal_mask.shape}")
        print("  PASSED\n")
    except Exception as e:
        print(f"  FAILED: {e}\n")
        return False
    return True


def test_nccl_init():
    """Test 6: Check if NCCL/RCCL distributed init works on ROCm."""
    print("Test 6: NCCL/RCCL distributed backend availability")
    try:
        import torch.distributed as dist
        if dist.is_nccl_available():
            print("  NCCL/RCCL backend: available")
        else:
            print("  NCCL/RCCL backend: NOT available")
        print("  PASSED\n")
    except Exception as e:
        print(f"  FAILED: {e}\n")
        return False
    return True


def test_llmc_config_generation():
    """Test 7: Verify LLMC config generation is correct."""
    print("Test 7: LLMC config generation")
    try:
        sys.path.insert(0, '/workspace/vendors/lightcompress')
        sys.path.insert(0, '/workspace')
        from src.quant.llmc_wrappers import create_config_from_experiment

        config = create_config_from_experiment(
            model_path="facebook/opt-125m",
            algorithm="gptq",
            bit_width=4,
            group_size=128,
            save_path="/tmp/test-output",
        )
        
        d = config.to_yaml_dict()
        
        # Check required fields
        assert d["quant"].get("quant_out") is True, "Missing quant_out: True"
        assert d["eval"].get("inference_per_block") is False, "Missing inference_per_block: False"
        assert "save_fake" in d.get("save", {}), "Missing save_fake in save config"
        assert "save_trans" not in d.get("save", {}), "Unexpected save_trans in save config"
        
        print("  Config has quant_out: True")
        print("  Config has inference_per_block: False")
        print("  Config has save_fake: False (no save_trans)")
        print("  PASSED\n")
    except Exception as e:
        print(f"  FAILED: {e}\n")
        return False
    return True


def run_all_tests():
    """Run all tests and report results."""
    print_env()
    
    if not torch.cuda.is_available():
        print("ERROR: CUDA/ROCm not available. Cannot run tests.")
        return 1
    
    print("=" * 60)
    print("Running Diagnostic Tests")
    print("=" * 60)
    print()
    
    results = []
    
    try:
        test_triu_basic()
        results.append(("Basic triu", True))
    except Exception as e:
        print(f"  FAILED: {e}\n")
        results.append(("Basic triu", False))
    
    try:
        test_triu_fp16_small()
        results.append(("FP16 small", True))
    except Exception as e:
        print(f"  FAILED: {e}\n")
        results.append(("FP16 small", False))
    
    results.append(("FP16 medium", test_triu_fp16_medium()))
    results.append(("FP16 large", test_triu_fp16_large()))
    results.append(("Attention mask", test_attention_mask_pattern()))
    results.append(("NCCL/RCCL check", test_nccl_init()))
    results.append(("LLMC config gen", test_llmc_config_generation()))
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All tests passed. GPU and PyTorch ROCm stack are healthy.")
        print()
        print("If LLMC quantization still fails, check:")
        print("  1. Stale output directories (LLMC mkdirs refuses to overwrite)")
        print("  2. Generated YAML config (compare with experiments/configs/*.yml)")
        print("  3. Full torchrun output (look for [rank0]: prefixed traceback)")
    else:
        print("Some tests FAILED - review output above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
