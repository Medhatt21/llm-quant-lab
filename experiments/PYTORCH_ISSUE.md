# triu_tril_kernel causes HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION on AMD MI210/MI300X with FP16 tensors

## 🐛 Describe the bug

The `triu_tril_kernel` causes an illegal memory access (`HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION`) on AMD Instinct MI210 and MI300X GPUs when computing triangular operations on FP16 tensors. This commonly manifests when running transformer models that create causal attention masks.

## Environment

- **PyTorch version**: 2.11.0.dev20260118+rocm7.1
- **ROCm version**: 7.1.52802
- **GPUs tested**: 
  - AMD Instinct MI210 (gfx90a) - 2x 64GB configuration
  - AMD Instinct MI300X (gfx942)
- **OS**: Linux (Ubuntu)
- **Python**: 3.12
- **How PyTorch was installed**: pip (ROCm nightly wheels)

## Error Message

```
:0:rocdevice.cpp            :3587: 13177094081 us:  Callback: Queue 0x7f9100c00000 aborting with error : HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION: The agent attempted to access memory beyond the largest legal address. code: 0x29

UserWarning: HIP warning: an illegal memory access was encountered (Triggered internally at /pytorch/aten/src/ATen/hip/impl/HIPGuardImplMasqueradingAsCUDA.h:83.)

Kernel Name: _ZN2at6native16triu_tril_kernelIN3c104HalfEiLb1ELi4ELb0EEEvNS_4cuda6detail10TensorInfoIT_T0_EENS6_IKS7_S8_EEllS8_
VGPU=0x28031be0 SWq=0x7f941369f000, HWq=0x7f9100c00000, id=1
	Dispatch Header =0xb02 (type=2, barrier=1, acquire=1, release=1), setup=0
	grid=[1048576, 1, 1],
```

## Minimal Reproducer (Pure PyTorch)

```python
import torch

print(f"PyTorch: {torch.__version__}")
print(f"ROCm/HIP: {torch.version.hip}")
print(f"GPU: {torch.cuda.get_device_name(0)}")

# Test: triu on large FP16 tensor (simulates attention mask creation)
seq_len = 2048
device = 'cuda'

# Create causal mask pattern - this triggers the bug
causal_mask = torch.triu(
    torch.ones(seq_len, seq_len, device=device, dtype=torch.float16),
    diagonal=1
)
torch.cuda.synchronize()  # Force kernel completion

print(f"Causal mask shape: {causal_mask.shape}")
```

## Reproducer with HuggingFace (Real-World Use Case)

The bug was originally discovered when running the OPT model for perplexity evaluation:

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "facebook/opt-125m"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    attn_implementation="eager",  # Using eager to avoid SDPA issues
).to("cuda")

# Create sample input
text = "The quick brown fox jumps over the lazy dog"
inputs = tokenizer(text, return_tensors="pt").to("cuda")

# This triggers the triu_tril_kernel and causes the memory violation
with torch.no_grad():
    outputs = model(**inputs)
```

## Analysis

The demangled kernel name is:
```
at::native::triu_tril_kernel<c10::Half, int, true, 4, false>
```

This indicates:
- **Data type**: `c10::Half` (FP16)
- **Index type**: `int`
- **Operation**: `triu` (template param = true)
- **Vector width**: 4
- **Unknown param**: false

The issue appears to be in the HIP implementation of the triangular kernel when:
1. Using FP16 dtype
2. Operating on larger tensors (2048x2048 in the attention mask case)
3. The grid size `[1048576, 1, 1]` suggests a 1D kernel launch for the flattened tensor

## Expected Behavior

The `torch.triu` operation should complete without memory access violations, producing a valid upper triangular matrix.

## Additional Context

- The issue does **not** occur on NVIDIA GPUs with the same code and similar PyTorch versions
- Using `attn_implementation="eager"` instead of SDPA does not help
- The error happens early in inference (during the first few forward passes)
- Both MI210 (gfx90a) and MI300X (gfx942) architectures are affected
- The issue was discovered during GPTQ paper reproduction experiments on AMD hardware

## Potential Causes

1. Out-of-bounds memory access in the HIP kernel when computing thread indices
2. Incorrect grid/block dimension calculations for the HIP backend
3. Memory alignment issues specific to the gfx90a/gfx942 architectures
4. Issue with the vectorized FP16 path (vector width = 4)

## Workaround Attempts

1. Using `attn_implementation="eager"` - did not help
2. Reducing sequence length - may help in some cases but not a real solution
3. Using FP32 instead of FP16 - untested, would defeat the purpose of quantization experiments

## Related

This may be related to other ROCm memory issues but I could not find an existing issue tracking this specific kernel crash.

cc @jeffdaily @ptrblck (ROCm maintainers)

---

**Labels suggestion**: module: rocm, module: cuda, triaged
