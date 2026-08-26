"""Seed data for the Quantization Knowledge Graph.

Populates knowledge_nodes and knowledge_edges from:
- papers/quantization_algorithms_table.md (algorithms)
- papers/notes/*.yaml (algorithm details)
- Hardware spec sheets
- Quantization scheme definitions

The hardcoded base data below is always loaded. Dynamic parsing from
the markdown table and YAML notes enriches and extends it.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Node definitions (hardcoded base)
# ============================================================================

DATA_TYPE_NODES: list[dict[str, Any]] = [
    # Traditional
    {"id": "dt_fp32", "label": "FP32", "category": "traditional", "metadata_json": {"bits": 32, "format": "IEEE 754"}},
    {"id": "dt_fp16", "label": "FP16", "category": "traditional", "metadata_json": {"bits": 16, "format": "IEEE 754"}},
    {"id": "dt_bf16", "label": "BF16", "category": "traditional", "metadata_json": {"bits": 16, "format": "Brain Float"}},
    {"id": "dt_tf32", "label": "TF32", "category": "traditional", "metadata_json": {"bits": 19, "format": "TensorFloat-32", "note": "NVIDIA 19-bit internal"}},
    {"id": "dt_int8", "label": "INT8", "category": "traditional", "metadata_json": {"bits": 8, "format": "integer"}},
    {"id": "dt_int4", "label": "INT4", "category": "traditional", "metadata_json": {"bits": 4, "format": "integer"}},
    {"id": "dt_int3", "label": "INT3", "category": "traditional", "metadata_json": {"bits": 3, "format": "integer"}},
    {"id": "dt_int2", "label": "INT2", "category": "traditional", "metadata_json": {"bits": 2, "format": "integer"}},
    # FP8 variants
    {"id": "dt_fp8_e4m3", "label": "FP8 E4M3", "category": "fp8", "metadata_json": {"bits": 8, "format": "FP8", "exponent": 4, "mantissa": 3}},
    {"id": "dt_fp8_e5m2", "label": "FP8 E5M2", "category": "fp8", "metadata_json": {"bits": 8, "format": "FP8", "exponent": 5, "mantissa": 2}},
    {"id": "dt_fp8_e4m3fn", "label": "FP8 E4M3FN", "category": "fp8", "metadata_json": {"bits": 8, "format": "FP8 (no inf)", "note": "NVIDIA variant"}},
    # FP4/FP6
    {"id": "dt_fp4_e2m1", "label": "FP4 E2M1", "category": "low_precision", "metadata_json": {"bits": 4, "format": "FP4", "note": "Blackwell native"}},
    {"id": "dt_fp6_e2m3", "label": "FP6 E2M3", "category": "low_precision", "metadata_json": {"bits": 6, "format": "FP6"}},
    {"id": "dt_fp6_e3m2", "label": "FP6 E3M2", "category": "low_precision", "metadata_json": {"bits": 6, "format": "FP6"}},
    # Special
    {"id": "dt_nf4", "label": "NF4", "category": "special", "metadata_json": {"bits": 4, "format": "Normal Float", "note": "QLoRA format"}},
    {"id": "dt_ternary", "label": "Ternary (1.58-bit)", "category": "special", "metadata_json": {"bits": 1.58, "format": "ternary", "values": "{-1, 0, 1}"}},
    {"id": "dt_binary", "label": "Binary (1-bit)", "category": "special", "metadata_json": {"bits": 1, "format": "binary", "values": "{-1, 1}"}},
    # MX formats (OCP Microscaling)
    {"id": "dt_mxfp8", "label": "MXFP8", "category": "mx", "metadata_json": {"bits": 8, "format": "Microscaling", "block_size": 32}},
    {"id": "dt_mxfp6", "label": "MXFP6", "category": "mx", "metadata_json": {"bits": 6, "format": "Microscaling", "block_size": 32}},
    {"id": "dt_mxfp4", "label": "MXFP4", "category": "mx", "metadata_json": {"bits": 4, "format": "Microscaling", "block_size": 32}},
    {"id": "dt_mxint8", "label": "MXINT8", "category": "mx", "metadata_json": {"bits": 8, "format": "Microscaling", "block_size": 32}},
    {"id": "dt_mxint4", "label": "MXINT4", "category": "mx", "metadata_json": {"bits": 4, "format": "Microscaling", "block_size": 32}},
]

HARDWARE_NODES: list[dict[str, Any]] = [
    # AMD Datacenter (CDNA)
    {"id": "hw_mi300x", "label": "AMD MI300X", "category": "amd_dc", "metadata_json": {"vendor": "AMD", "arch": "CDNA3", "family": "Instinct", "memory_gb": 192, "tflops_fp16": 1307, "hbm_bandwidth_tb": 5.3, "compute_capability": "CDNA3", "matrix_core_types": "FP64,FP32,TF32,FP16,BF16,FP8(E4M3/E5M2-FNUZ),INT8", "int4_native": False, "note": "INT4 not a native matrix core type; used as storage format dequantized to FP16/INT8 for compute"}},
    {"id": "hw_mi325x", "label": "AMD MI325X", "category": "amd_dc", "metadata_json": {"vendor": "AMD", "arch": "CDNA3", "family": "Instinct", "memory_gb": 256, "hbm_bandwidth_tb": 6.0, "compute_capability": "CDNA3", "matrix_core_types": "FP64,FP32,TF32,FP16,BF16,FP8(E4M3/E5M2-FNUZ),INT8", "int4_native": False}},
    {"id": "hw_mi350", "label": "AMD MI350", "category": "amd_dc", "metadata_json": {"vendor": "AMD", "arch": "CDNA4", "family": "Instinct", "note": "2025", "matrix_core_types": "FP16,BF16,FP8,FP6(E2M3/E3M2),FP4(E2M1),INT8,MXFP8,MXFP6,MXFP4"}},
    # AMD Consumer (RDNA)
    {"id": "hw_rx7900xtx", "label": "AMD RX 7900 XTX", "category": "amd_consumer", "metadata_json": {"vendor": "AMD", "arch": "RDNA3", "family": "Radeon", "memory_gb": 24, "type": "consumer", "wmma_types": "FP16,BF16,INT8,IU4(unsigned INT4)"}},
    # NVIDIA Datacenter — Blackwell
    {"id": "hw_b200", "label": "NVIDIA B200 Blackwell", "category": "nvidia_dc", "metadata_json": {"vendor": "NVIDIA", "arch": "Blackwell", "family": "Datacenter", "memory_gb": 192, "tflops_fp16": 2250, "fp4_tflops": 9000, "compute_capability": "10.0", "tensor_core_gen": 5, "tensor_types": "FP64,TF32,BF16,FP16,FP8,FP6,FP4,INT8", "int4_native": False, "note": "Blackwell dropped INT4 tensor cores; uses FP4 E2M1 (NVFP4) instead"}},
    {"id": "hw_gb200", "label": "NVIDIA GB200 Grace-Blackwell", "category": "nvidia_dc", "metadata_json": {"vendor": "NVIDIA", "arch": "Blackwell", "family": "Datacenter", "memory_gb": 384, "note": "NVLink 1.8TB/s", "compute_capability": "10.0", "tensor_types": "FP64,TF32,BF16,FP16,FP8,FP6,FP4,INT8", "int4_native": False}},
    # NVIDIA Datacenter — Hopper
    {"id": "hw_h100", "label": "NVIDIA H100 Hopper", "category": "nvidia_dc", "metadata_json": {"vendor": "NVIDIA", "arch": "Hopper", "family": "Datacenter", "memory_gb": 80, "tflops_fp16": 989, "compute_capability": "9.0", "tensor_core_gen": 4, "tensor_types": "FP64,TF32,BF16,FP16,FP8,INT8", "int4_native": False, "note": "Hopper dropped INT4 tensor cores from Ampere; FP8 added"}},
    {"id": "hw_h200", "label": "NVIDIA H200", "category": "nvidia_dc", "metadata_json": {"vendor": "NVIDIA", "arch": "Hopper", "family": "Datacenter", "memory_gb": 141, "hbm_bandwidth_tb": 4.8, "compute_capability": "9.0", "tensor_types": "FP64,TF32,BF16,FP16,FP8,INT8", "int4_native": False}},
    # NVIDIA Datacenter — Ampere
    {"id": "hw_a100", "label": "NVIDIA A100 Ampere", "category": "nvidia_dc", "metadata_json": {"vendor": "NVIDIA", "arch": "Ampere", "family": "Datacenter", "memory_gb": 80, "tflops_fp16": 312, "compute_capability": "8.0", "tensor_core_gen": 3, "tensor_types": "FP64,TF32,BF16,FP16,INT8,INT4", "int4_native": True, "note": "Last NVIDIA DC GPU with native INT4 tensor cores; no FP8"}},
    # NVIDIA Datacenter — Ada Lovelace
    {"id": "hw_l40s", "label": "NVIDIA L40S", "category": "nvidia_dc", "metadata_json": {"vendor": "NVIDIA", "arch": "Ada Lovelace", "family": "Datacenter", "memory_gb": 48, "compute_capability": "8.9", "tensor_core_gen": 4, "tensor_types": "TF32,BF16,FP16,FP8,INT8,INT4", "int4_native": True}},
    # NVIDIA Consumer — Ada Lovelace
    {"id": "hw_rtx4090", "label": "NVIDIA RTX 4090", "category": "nvidia_consumer", "metadata_json": {"vendor": "NVIDIA", "arch": "Ada Lovelace", "family": "GeForce", "memory_gb": 24, "type": "consumer", "compute_capability": "8.9", "tensor_core_gen": 4, "tensor_types": "TF32,BF16,FP16,FP8,INT8,INT4", "int4_native": True}},
    # NVIDIA Consumer — Blackwell
    {"id": "hw_rtx5090", "label": "NVIDIA RTX 5090", "category": "nvidia_consumer", "metadata_json": {"vendor": "NVIDIA", "arch": "Blackwell", "family": "GeForce", "memory_gb": 32, "type": "consumer", "compute_capability": "10.3", "tensor_core_gen": 5, "tensor_types": "TF32,BF16,FP16,FP8,FP6,FP4,INT8", "int4_native": False}},
    # NPU / Edge
    {"id": "hw_npu_qualcomm", "label": "Qualcomm Hexagon NPU", "category": "npu", "metadata_json": {"vendor": "Qualcomm", "arch": "Hexagon", "family": "NPU", "type": "NPU", "target": "mobile"}},
    {"id": "hw_npu_intel", "label": "Intel Meteor Lake NPU", "category": "npu", "metadata_json": {"vendor": "Intel", "arch": "Meteor Lake", "family": "NPU", "type": "NPU", "target": "laptop"}},
    {"id": "hw_npu_mediatek", "label": "MediaTek APU", "category": "npu", "metadata_json": {"vendor": "MediaTek", "arch": "APU", "family": "NPU", "type": "NPU", "target": "mobile"}},
    # Apple
    {"id": "hw_apple_m4", "label": "Apple M4 (MPS)", "category": "apple", "metadata_json": {"vendor": "Apple", "arch": "M4", "family": "Apple Silicon", "memory_gb": 32}},
    {"id": "hw_apple_m4_ultra", "label": "Apple M4 Ultra", "category": "apple", "metadata_json": {"vendor": "Apple", "arch": "M4", "family": "Apple Silicon", "memory_gb": 192}},
    # Inference accelerators
    {"id": "hw_tpu_v5e", "label": "Google TPU v5e", "category": "tpu", "metadata_json": {"vendor": "Google", "arch": "TPU v5e", "family": "TPU", "type": "TPU", "memory_gb": 16}},
    {"id": "hw_gaudi3", "label": "Intel Gaudi 3", "category": "intel_dc", "metadata_json": {"vendor": "Intel", "arch": "Gaudi 3", "family": "Gaudi", "memory_gb": 128}},
]

SCHEME_NODES: list[dict[str, Any]] = [
    # Weight-only schemes
    {"id": "sch_a16w8", "label": "A16W8 (weight-only 8b)", "category": "weight_only", "metadata_json": {"weight_bits": 8, "act_bits": 16, "dynamic": False}},
    {"id": "sch_w4", "label": "W4 (weight-only 4-bit)", "category": "weight_only", "metadata_json": {"weight_bits": 4, "act_bits": 16}},
    {"id": "sch_w3", "label": "W3 (weight-only 3-bit)", "category": "weight_only", "metadata_json": {"weight_bits": 3, "act_bits": 16}},
    {"id": "sch_w2", "label": "W2 (weight-only 2-bit)", "category": "weight_only", "metadata_json": {"weight_bits": 2, "act_bits": 16}},
    {"id": "sch_w4_g128", "label": "W4G128 (grouped 4-bit)", "category": "weight_only", "metadata_json": {"weight_bits": 4, "act_bits": 16, "group_size": 128}},
    # Weight + Activation schemes
    {"id": "sch_dyn_a8w8", "label": "Dynamic A8W8", "category": "w_a", "metadata_json": {"weight_bits": 8, "act_bits": 8, "dynamic": True}},
    {"id": "sch_stat_a8w8", "label": "Static A8W8", "category": "w_a", "metadata_json": {"weight_bits": 8, "act_bits": 8, "dynamic": False}},
    {"id": "sch_dyn_a8w4", "label": "Dynamic A8W4", "category": "w_a", "metadata_json": {"weight_bits": 4, "act_bits": 8, "dynamic": True}},
    {"id": "sch_dyn_a6w6", "label": "Dynamic A6W6", "category": "w_a", "metadata_json": {"weight_bits": 6, "act_bits": 6, "dynamic": True}},
    {"id": "sch_dyn_a6w4", "label": "Dynamic A6W4", "category": "w_a", "metadata_json": {"weight_bits": 4, "act_bits": 6, "dynamic": True}},
    {"id": "sch_dyn_a4w4", "label": "Dynamic A4W4", "category": "w_a", "metadata_json": {"weight_bits": 4, "act_bits": 4, "dynamic": True}},
    # FP8 schemes
    {"id": "sch_fp8_a8w8", "label": "FP8 W8A8", "category": "fp8_scheme", "metadata_json": {"weight_bits": 8, "act_bits": 8, "format": "FP8"}},
    {"id": "sch_fp8_kvcache", "label": "FP8 KV-Cache", "category": "fp8_scheme", "metadata_json": {"cache_bits": 8, "format": "FP8", "note": "KV cache compression"}},
    # Mixed precision
    {"id": "sch_mixed_2_4", "label": "Mixed 2:4 Sparsity", "category": "mixed", "metadata_json": {"sparsity": "2:4", "note": "Structural sparsity"}},
    {"id": "sch_qlora", "label": "QLoRA (NF4+FP16)", "category": "mixed", "metadata_json": {"weight_bits": 4, "adapter_bits": 16, "format": "NF4", "note": "Efficient fine-tuning"}},
]

ALGORITHM_NODES: list[dict[str, Any]] = [
    # PTQ Weight-only
    {"id": "algo_gptq", "label": "GPTQ", "category": "ptq_weight", "metadata_json": {"paper": "arXiv:2210.17323", "year": 2022, "type": "PTQ", "scope": "weight-only", "calibration": "yes"}},
    {"id": "algo_awq", "label": "AWQ", "category": "ptq_weight", "metadata_json": {"paper": "arXiv:2306.00978", "year": 2023, "type": "PTQ", "scope": "weight-only", "calibration": "yes"}},
    {"id": "algo_hqq", "label": "HQQ", "category": "ptq_weight", "metadata_json": {"year": 2023, "type": "PTQ", "scope": "weight-only", "calibration": "no"}},
    {"id": "algo_rtn", "label": "RTN", "category": "ptq_weight", "metadata_json": {"year": 2020, "type": "PTQ", "scope": "weight-only", "note": "Round-to-Nearest baseline"}},
    {"id": "algo_spqr", "label": "SpQR", "category": "ptq_weight", "metadata_json": {"year": 2023, "type": "PTQ", "scope": "weight-only"}},
    {"id": "algo_owq", "label": "OWQ", "category": "ptq_weight", "metadata_json": {"year": 2023, "type": "PTQ", "scope": "weight-only"}},
    {"id": "algo_qlora", "label": "QLoRA", "category": "ptq_weight", "metadata_json": {"paper": "arXiv:2305.14314", "year": 2023, "type": "PTQ+FT", "scope": "weight-only", "note": "NF4 quantized fine-tuning"}},
    {"id": "algo_squeezellm", "label": "SqueezeLLM", "category": "ptq_weight", "metadata_json": {"year": 2023, "type": "PTQ", "scope": "weight-only", "note": "Dense-and-sparse quantization"}},
    # PTQ W+A
    {"id": "algo_smoothquant", "label": "SmoothQuant", "category": "ptq_wa", "metadata_json": {"paper": "arXiv:2211.10438", "year": 2022, "type": "PTQ", "scope": "W+A"}},
    {"id": "algo_quarot", "label": "QuaRot", "category": "ptq_wa", "metadata_json": {"paper": "arXiv:2404.00456", "year": 2024, "venue": "NeurIPS 2024", "type": "PTQ", "scope": "W+A", "note": "Hadamard rotation eliminates outliers; uniform 4-bit for weights, activations, and KV cache"}},
    {"id": "algo_llmint8", "label": "LLM.int8()", "category": "ptq_wa", "metadata_json": {"paper": "arXiv:2208.07339", "year": 2022, "type": "PTQ", "scope": "W+A"}},
    {"id": "algo_zeroquant", "label": "ZeroQuant", "category": "ptq_wa", "metadata_json": {"paper": "arXiv:2206.01861", "year": 2022, "type": "PTQ", "scope": "W+A"}},
    {"id": "algo_atom", "label": "ATOM", "category": "ptq_wa", "metadata_json": {"paper": "arXiv:2310.19102", "year": 2023, "venue": "MLSys 2024", "type": "PTQ", "scope": "W+A", "note": "Mixed-precision W4A4 with fine-grained quantization; uses INT4 for both weights and activations"}},
    {"id": "algo_quik", "label": "QuiK", "category": "ptq_wa", "metadata_json": {"paper": "arXiv:2310.09259", "year": 2023, "venue": "EMNLP 2024", "type": "PTQ", "scope": "W+A", "note": "INT4 weight + INT4 activation (W4A4) with outlier columns kept in higher precision"}},
    # PTQ Mixed / Advanced
    {"id": "algo_omniquant", "label": "OmniQuant", "category": "ptq_mixed", "metadata_json": {"year": 2023, "type": "PTQ", "scope": "mixed"}},
    {"id": "algo_paretoq", "label": "ParetoQ", "category": "qat", "metadata_json": {"paper": "arXiv:2502.02631", "year": 2025, "type": "QAT", "scope": "mixed-precision", "note": "Unified framework for 1-bit to 4-bit QAT; ternary/2b/3b use Stretched Elastic Quant (SEQ)"}},
    {"id": "algo_fp8quant", "label": "FP8 Quantization", "category": "ptq_wa", "metadata_json": {"year": 2023, "type": "PTQ", "scope": "W+A", "note": "vLLM/TensorRT FP8 flow"}},
    {"id": "algo_kvcache_quant", "label": "KV-Cache Quantization", "category": "ptq_mixed", "metadata_json": {"year": 2024, "type": "PTQ", "scope": "kv-cache", "note": "Compress KV cache to FP8/INT8"}},
    # QAT
    {"id": "algo_bitnet", "label": "BitNet", "category": "qat", "metadata_json": {"paper": "arXiv:2310.11453", "year": 2023, "type": "QAT", "scope": "1-bit"}},
    {"id": "algo_qat_generic", "label": "QAT (generic)", "category": "qat", "metadata_json": {"year": 2020, "type": "QAT", "scope": "configurable", "note": "Quantization-Aware Training"}},
]


# ============================================================================
# Edge definitions (hardcoded base)
# ============================================================================

EDGES: list[dict[str, Any]] = [
    # ═══════════════════════════════════════════════════════════════
    # Algorithm -> Scheme (implements)
    # ═══════════════════════════════════════════════════════════════
    {"source_id": "algo_gptq", "target_id": "sch_w4", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_gptq", "target_id": "sch_w4_g128", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_gptq", "target_id": "sch_w3", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_gptq", "target_id": "sch_w2", "edge_type": "implements", "strength": 0.6},
    {"source_id": "algo_awq", "target_id": "sch_w4", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_awq", "target_id": "sch_w4_g128", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_awq", "target_id": "sch_w3", "edge_type": "implements", "strength": 0.7},
    {"source_id": "algo_smoothquant", "target_id": "sch_stat_a8w8", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_smoothquant", "target_id": "sch_dyn_a8w8", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_hqq", "target_id": "sch_w4", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_hqq", "target_id": "sch_w2", "edge_type": "implements", "strength": 0.7},
    {"source_id": "algo_hqq", "target_id": "sch_w3", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_rtn", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_rtn", "target_id": "sch_a16w8", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_quarot", "target_id": "sch_dyn_a4w4", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_quarot", "target_id": "sch_dyn_a8w4", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_llmint8", "target_id": "sch_dyn_a8w8", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_zeroquant", "target_id": "sch_dyn_a8w8", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_zeroquant", "target_id": "sch_stat_a8w8", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_bitnet", "target_id": "sch_w2", "edge_type": "implements", "strength": 0.5},
    {"source_id": "algo_paretoq", "target_id": "sch_w2", "edge_type": "implements", "strength": 1.0, "metadata_json": {"note": "QAT 2-bit via Stretched Elastic Quant (SEQ)"}},
    {"source_id": "algo_paretoq", "target_id": "sch_w3", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_paretoq", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_omniquant", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_omniquant", "target_id": "sch_dyn_a8w4", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_spqr", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_spqr", "target_id": "sch_w3", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_owq", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_qlora", "target_id": "sch_qlora", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_qlora", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.7},
    {"source_id": "algo_fp8quant", "target_id": "sch_fp8_a8w8", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_fp8quant", "target_id": "sch_fp8_kvcache", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_kvcache_quant", "target_id": "sch_fp8_kvcache", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_atom", "target_id": "sch_dyn_a4w4", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_atom", "target_id": "sch_dyn_a8w4", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_quik", "target_id": "sch_dyn_a4w4", "edge_type": "implements", "strength": 1.0},
    {"source_id": "algo_quik", "target_id": "sch_dyn_a8w4", "edge_type": "implements", "strength": 0.7},
    {"source_id": "algo_squeezellm", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.9},
    {"source_id": "algo_squeezellm", "target_id": "sch_w3", "edge_type": "implements", "strength": 0.8},
    {"source_id": "algo_qat_generic", "target_id": "sch_dyn_a8w8", "edge_type": "implements", "strength": 0.7},
    {"source_id": "algo_qat_generic", "target_id": "sch_w4", "edge_type": "implements", "strength": 0.7},

    # ═══════════════════════════════════════════════════════════════
    # Algorithm -> Data Type (produces/uses)
    # ═══════════════════════════════════════════════════════════════
    {"source_id": "algo_gptq", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_gptq", "target_id": "dt_int3", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_gptq", "target_id": "dt_int2", "edge_type": "uses", "strength": 0.5},
    {"source_id": "algo_gptq", "target_id": "dt_int8", "edge_type": "uses", "strength": 0.7},
    {"source_id": "algo_awq", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_awq", "target_id": "dt_int3", "edge_type": "uses", "strength": 0.6},
    {"source_id": "algo_smoothquant", "target_id": "dt_int8", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_hqq", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_hqq", "target_id": "dt_int2", "edge_type": "uses", "strength": 0.7},
    {"source_id": "algo_hqq", "target_id": "dt_int3", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_rtn", "target_id": "dt_int4", "edge_type": "uses", "strength": 0.9},
    {"source_id": "algo_rtn", "target_id": "dt_int8", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_quarot", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_llmint8", "target_id": "dt_int8", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_zeroquant", "target_id": "dt_int8", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_zeroquant", "target_id": "dt_int4", "edge_type": "uses", "strength": 0.6},
    {"source_id": "algo_bitnet", "target_id": "dt_ternary", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_bitnet", "target_id": "dt_binary", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_paretoq", "target_id": "dt_binary", "edge_type": "uses", "strength": 0.7, "metadata_json": {"note": "1-bit binary quantization"}},
    {"source_id": "algo_paretoq", "target_id": "dt_ternary", "edge_type": "uses", "strength": 1.0, "metadata_json": {"note": "1.58-bit ternary via SEQ; best size-accuracy tradeoff per paper"}},
    {"source_id": "algo_paretoq", "target_id": "dt_int2", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_paretoq", "target_id": "dt_int3", "edge_type": "uses", "strength": 0.9},
    {"source_id": "algo_paretoq", "target_id": "dt_int4", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_omniquant", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_omniquant", "target_id": "dt_int8", "edge_type": "uses", "strength": 0.7},
    {"source_id": "algo_spqr", "target_id": "dt_int4", "edge_type": "uses", "strength": 0.9},
    {"source_id": "algo_spqr", "target_id": "dt_int3", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_owq", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_qlora", "target_id": "dt_nf4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_qlora", "target_id": "dt_fp16", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_fp8quant", "target_id": "dt_fp8_e4m3", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_fp8quant", "target_id": "dt_fp8_e5m2", "edge_type": "uses", "strength": 0.9},
    {"source_id": "algo_fp8quant", "target_id": "dt_fp8_e4m3fn", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_kvcache_quant", "target_id": "dt_fp8_e4m3", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_kvcache_quant", "target_id": "dt_int8", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_atom", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_quik", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_quik", "target_id": "dt_fp16", "edge_type": "uses", "strength": 0.6, "metadata_json": {"note": "outlier columns kept in FP16"}},
    {"source_id": "algo_squeezellm", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "algo_squeezellm", "target_id": "dt_int3", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_qat_generic", "target_id": "dt_int8", "edge_type": "uses", "strength": 0.8},
    {"source_id": "algo_qat_generic", "target_id": "dt_int4", "edge_type": "uses", "strength": 0.7},

    # ═══════════════════════════════════════════════════════════════
    # Scheme -> Data Type (uses)
    # ═══════════════════════════════════════════════════════════════
    {"source_id": "sch_w4", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_w4_g128", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_w3", "target_id": "dt_int3", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_w2", "target_id": "dt_int2", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_a16w8", "target_id": "dt_int8", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_a16w8", "target_id": "dt_fp16", "edge_type": "uses", "strength": 0.8},
    {"source_id": "sch_dyn_a8w8", "target_id": "dt_int8", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_stat_a8w8", "target_id": "dt_int8", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_dyn_a8w4", "target_id": "dt_int4", "edge_type": "uses", "strength": 0.8},
    {"source_id": "sch_dyn_a8w4", "target_id": "dt_int8", "edge_type": "uses", "strength": 0.8},
    {"source_id": "sch_dyn_a6w6", "target_id": "dt_fp6_e2m3", "edge_type": "uses", "strength": 0.7},
    {"source_id": "sch_dyn_a6w4", "target_id": "dt_int4", "edge_type": "uses", "strength": 0.8},
    {"source_id": "sch_dyn_a4w4", "target_id": "dt_int4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_dyn_a4w4", "target_id": "dt_fp4_e2m1", "edge_type": "uses", "strength": 0.6},
    {"source_id": "sch_fp8_a8w8", "target_id": "dt_fp8_e4m3", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_fp8_a8w8", "target_id": "dt_fp8_e5m2", "edge_type": "uses", "strength": 0.8},
    {"source_id": "sch_fp8_kvcache", "target_id": "dt_fp8_e4m3", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_qlora", "target_id": "dt_nf4", "edge_type": "uses", "strength": 1.0},
    {"source_id": "sch_qlora", "target_id": "dt_fp16", "edge_type": "uses", "strength": 0.8},
    {"source_id": "sch_mixed_2_4", "target_id": "dt_int8", "edge_type": "uses", "strength": 0.7},
    {"source_id": "sch_mixed_2_4", "target_id": "dt_fp16", "edge_type": "uses", "strength": 0.8},

    # ═══════════════════════════════════════════════════════════════
    # Hardware -> Data Type (NATIVE hardware-accelerated support)
    # Only edges where the silicon has dedicated compute units.
    # "via software dequant" = the GPU has no native INT4/etc
    # instruction, but inference frameworks (vLLM, GPTQ kernels)
    # can still run the workload by dequanting to FP16/INT8 on-the-fly.
    # ═══════════════════════════════════════════════════════════════

    # ── AMD MI300X  (CDNA3 Matrix Cores) ──
    # Native per ROCm precision-support.html: FP64, FP32, TF32, FP16, BF16,
    #   FP8 E4M3-FNUZ, FP8 E5M2-FNUZ, INT8
    # NOT native: INT4, INT3, INT2, FP4, FP6 (no CDNA3 sub-8-bit matrix instruction)
    # Note: FP8 on MI300 uses FNUZ encoding, different from NVIDIA's FP8 (E4M3FN/E5M2)
    {"source_id": "hw_mi300x", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "dt_fp8_e5m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ── AMD MI325X  (CDNA3 — same Matrix Core ISA as MI300X; no INT4/FP4/FP6) ──
    {"source_id": "hw_mi325x", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "dt_fp8_e5m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ── AMD MI350  (CDNA4 — adds FP4 E2M1, FP6 E2M3/E3M2, MXFP formats; no INT4 matrix core) ──
    {"source_id": "hw_mi350", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "dt_fp4_e2m1", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native CDNA4 FP4"}},
    {"source_id": "hw_mi350", "target_id": "dt_fp6_e2m3", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native CDNA4 FP6"}},
    {"source_id": "hw_mi350", "target_id": "dt_fp6_e3m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "dt_mxfp8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "dt_mxfp6", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "dt_mxfp4", "edge_type": "supports", "strength": 1.0},

    # ── AMD RX 7900 XTX  (RDNA3 WMMA: FP16, BF16, INT8, IU4) ──
    # Per GPUOpen WMMA docs: RDNA3 supports IU4 (unsigned INT4) via WMMA at 1024 FLOPS/clock/CU
    {"source_id": "hw_rx7900xtx", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rx7900xtx", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rx7900xtx", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rx7900xtx", "target_id": "dt_int4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "WMMA IU4 (unsigned INT4 only); not full signed INT4"}},

    # ── NVIDIA B200 Blackwell  (5th-gen Tensor Cores CC 10.0: FP64,TF32,BF16,FP16,FP8,FP6,FP4,INT8 — NO INT4) ──
    # Per CUDA Programming Guide Table 33: CC 10.0 does NOT have INT4 tensor cores.
    # Blackwell uses FP4 (NVFP4 E2M1) instead of INT4 for 4-bit compute.
    {"source_id": "hw_b200", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_fp8_e5m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_fp8_e4m3fn", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_fp4_e2m1", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native NVFP4 tensor cores"}},
    {"source_id": "hw_b200", "target_id": "dt_fp6_e2m3", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native FP6 tensor cores"}},
    {"source_id": "hw_b200", "target_id": "dt_fp6_e3m2", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native FP6 tensor cores"}},
    {"source_id": "hw_b200", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "dt_mxfp8", "edge_type": "supports", "strength": 0.8},
    {"source_id": "hw_b200", "target_id": "dt_mxfp4", "edge_type": "supports", "strength": 0.8},

    # ── NVIDIA GB200 Grace-Blackwell  (CC 10.0 — same tensor cores as B200; no INT4) ──
    {"source_id": "hw_gb200", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_fp8_e5m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_fp4_e2m1", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_fp6_e2m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_fp6_e3m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ── NVIDIA H100 Hopper  (4th-gen Tensor Cores CC 9.0: FP64,TF32,BF16,FP16,FP8,INT8) ──
    # Per CUDA Programming Guide Table 33: CC 9.0 does NOT have INT4 tensor cores.
    # Hopper DROPPED INT4 from Ampere; added FP8 instead.
    {"source_id": "hw_h100", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "dt_fp8_e5m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "dt_fp8_e4m3fn", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    # NOTE: H100 does NOT support INT4 natively. INT4 weight-only quantization
    # (GPTQ/AWQ) works via software dequant to FP16/INT8 before tensor core GEMM.

    # ── NVIDIA H200  (Hopper die CC 9.0 — same tensor cores as H100; no INT4) ──
    {"source_id": "hw_h200", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "dt_fp8_e5m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "dt_fp8_e4m3fn", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ── NVIDIA A100 Ampere  (3rd-gen Tensor Cores CC 8.0: FP64,TF32,BF16,FP16,INT8,INT4 — no FP8) ──
    # Per CUDA Programming Guide Table 33: CC 8.0 has native INT4 tensor core support.
    # A100 is the last NVIDIA datacenter GPU with INT4 tensor cores (dropped in Hopper CC 9.0).
    {"source_id": "hw_a100", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_a100", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_a100", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_a100", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_a100", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_a100", "target_id": "dt_int4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native INT4 tensor core (CC 8.0); last NVIDIA DC GPU with INT4 TC"}},

    # ── NVIDIA L40S  (Ada CC 8.9 — 4th-gen Tensor Cores: TF32,BF16,FP16,FP8,INT8,INT4 native) ──
    {"source_id": "hw_l40s", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "dt_int4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native Ada INT4 tensor core"}},

    # ── NVIDIA RTX 4090  (Ada CC 8.9 — TF32,BF16,FP16,FP8,INT8,INT4 native tensor core) ──
    {"source_id": "hw_rtx4090", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx4090", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx4090", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx4090", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "tensor core GEMM only"}},
    {"source_id": "hw_rtx4090", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx4090", "target_id": "dt_int4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native Ada INT4 tensor core"}},

    # ── NVIDIA RTX 5090  (Blackwell consumer CC 10.3 — TF32,BF16,FP16,FP8,FP6,FP4,INT8; NO INT4) ──
    {"source_id": "hw_rtx5090", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx5090", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx5090", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx5090", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx5090", "target_id": "dt_fp8_e5m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx5090", "target_id": "dt_fp4_e2m1", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native Blackwell FP4 (NVFP4)"}},
    {"source_id": "hw_rtx5090", "target_id": "dt_fp6_e2m3", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native Blackwell FP6"}},
    {"source_id": "hw_rtx5090", "target_id": "dt_fp6_e3m2", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx5090", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ── NPU / Edge ──
    # Qualcomm Hexagon: INT8, INT4 (weight), FP16
    {"source_id": "hw_npu_qualcomm", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_npu_qualcomm", "target_id": "dt_int4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "weight INT4 via HTP"}},
    {"source_id": "hw_npu_qualcomm", "target_id": "dt_fp16", "edge_type": "supports", "strength": 0.8},
    # Intel Meteor Lake NPU: INT8
    {"source_id": "hw_npu_intel", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    # MediaTek APU: INT8, INT4
    {"source_id": "hw_npu_mediatek", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_npu_mediatek", "target_id": "dt_int4", "edge_type": "supports", "strength": 0.7},

    # ── Apple M4 ──
    # Neural Engine: INT8 (W8A8 optimised), weight INT4 via CoreML
    {"source_id": "hw_apple_m4", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_apple_m4", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "W8A8 optimised on Neural Engine"}},
    {"source_id": "hw_apple_m4_ultra", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_apple_m4_ultra", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ── Google TPU v5e ──
    # Native: BF16 (197 TFLOPS), INT8 (393 TOPS)
    {"source_id": "hw_tpu_v5e", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_tpu_v5e", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ── Intel Gaudi 3 ──
    # Native: FP32, TF32, BF16, FP16, FP8 (E4M3/E5M2), INT8
    {"source_id": "hw_gaudi3", "target_id": "dt_fp32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gaudi3", "target_id": "dt_tf32", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gaudi3", "target_id": "dt_bf16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gaudi3", "target_id": "dt_fp16", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gaudi3", "target_id": "dt_fp8_e4m3", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gaudi3", "target_id": "dt_int8", "edge_type": "supports", "strength": 1.0},

    # ═══════════════════════════════════════════════════════════════
    # Hardware -> Scheme (which quantization schemes can run on this HW)
    # ═══════════════════════════════════════════════════════════════
    # -- Schemes requiring INT8 tensor cores (W8A8, SmoothQuant, etc.) --
    # Everyone with INT8 can run A8W8
    {"source_id": "hw_mi300x", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "sch_stat_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "sch_a16w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "sch_stat_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_a100", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_a100", "target_id": "sch_stat_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gaudi3", "target_id": "sch_dyn_a8w8", "edge_type": "supports", "strength": 1.0},

    # -- FP8 schemes (require FP8 tensor cores: H100+, MI300X+, Gaudi3, Ada+) --
    {"source_id": "hw_mi300x", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi300x", "target_id": "sch_fp8_kvcache", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi325x", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h100", "target_id": "sch_fp8_kvcache", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_h200", "target_id": "sch_fp8_kvcache", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "sch_fp8_kvcache", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gb200", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_l40s", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_rtx4090", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "GEMM only"}},
    {"source_id": "hw_rtx5090", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_mi350", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_gaudi3", "target_id": "sch_fp8_a8w8", "edge_type": "supports", "strength": 1.0},

    # -- 2:4 Sparsity (Ampere+, Hopper+, Blackwell) --
    {"source_id": "hw_a100", "target_id": "sch_mixed_2_4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native 2:4 structured sparsity"}},
    {"source_id": "hw_h100", "target_id": "sch_mixed_2_4", "edge_type": "supports", "strength": 1.0},
    {"source_id": "hw_b200", "target_id": "sch_mixed_2_4", "edge_type": "supports", "strength": 1.0},

    # -- W4 (weight-only 4-bit via GPTQ/AWQ kernels) --
    # GPUs with native INT4 tensor cores (Ada CC 8.9, Ampere CC 8.0) can run W4 natively.
    # GPUs without INT4 TC (Hopper, Blackwell, CDNA3) use software dequant to FP16/INT8.
    # Strength reflects native vs software dequant performance.
    {"source_id": "hw_mi300x", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4; dequant to FP16/INT8 via vLLM/AutoGPTQ ROCm kernels"}},
    {"source_id": "hw_mi325x", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4; dequant to FP16/INT8 via vLLM ROCm kernels"}},
    {"source_id": "hw_h100", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "no native INT4 TC (CC 9.0); dequant to FP16 via Marlin/vLLM CUDA kernels"}},
    {"source_id": "hw_h200", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "no native INT4 TC (CC 9.0); dequant to FP16 via Marlin/vLLM"}},
    {"source_id": "hw_a100", "target_id": "sch_w4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native INT4 tensor core (CC 8.0); direct INT4 GEMM"}},
    {"source_id": "hw_b200", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4 TC (CC 10.0); dequant to FP16 or use FP4 path instead"}},
    {"source_id": "hw_gb200", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4 TC; dequant to FP16 or use FP4 path"}},
    {"source_id": "hw_l40s", "target_id": "sch_w4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native INT4 tensor core (CC 8.9)"}},
    {"source_id": "hw_rtx4090", "target_id": "sch_w4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native INT4 tensor core (CC 8.9)"}},
    {"source_id": "hw_rtx5090", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4 TC (CC 10.3); dequant to FP16 or use FP4 path"}},
    {"source_id": "hw_rx7900xtx", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "WMMA IU4 (unsigned only) + ROCm GPTQ dequant kernels"}},
    {"source_id": "hw_mi350", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4; can use FP4 path or dequant to FP16"}},
    {"source_id": "hw_apple_m4", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.7, "metadata_json": {"note": "via llama.cpp / CoreML dequant"}},
    {"source_id": "hw_apple_m4_ultra", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8},
    {"source_id": "hw_npu_qualcomm", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "HTP INT4 weight quantization"}},
    {"source_id": "hw_npu_mediatek", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.5},
    {"source_id": "hw_gaudi3", "target_id": "sch_w4", "edge_type": "supports", "strength": 0.6, "metadata_json": {"note": "no native INT4; via Intel Neural Compressor dequant"}},

    # -- W4G128 (grouped 4-bit — same native/dequant split as W4) --
    {"source_id": "hw_mi300x", "target_id": "sch_w4_g128", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4; dequant path"}},
    {"source_id": "hw_h100", "target_id": "sch_w4_g128", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "no native INT4; dequant to FP16"}},
    {"source_id": "hw_b200", "target_id": "sch_w4_g128", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4; dequant path"}},
    {"source_id": "hw_a100", "target_id": "sch_w4_g128", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native INT4 tensor core (CC 8.0)"}},
    {"source_id": "hw_l40s", "target_id": "sch_w4_g128", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native INT4 tensor core (CC 8.9)"}},
    {"source_id": "hw_rtx4090", "target_id": "sch_w4_g128", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "native INT4 tensor core (CC 8.9)"}},
    {"source_id": "hw_rtx5090", "target_id": "sch_w4_g128", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "no native INT4; dequant path"}},

    # -- QLoRA (NF4 base weights + FP16 adapters — GPU memory is main constraint) --
    {"source_id": "hw_mi300x", "target_id": "sch_qlora", "edge_type": "supports", "strength": 0.9},
    {"source_id": "hw_h100", "target_id": "sch_qlora", "edge_type": "supports", "strength": 0.9},
    {"source_id": "hw_a100", "target_id": "sch_qlora", "edge_type": "supports", "strength": 0.8},
    {"source_id": "hw_rtx4090", "target_id": "sch_qlora", "edge_type": "supports", "strength": 0.9},
    {"source_id": "hw_rtx5090", "target_id": "sch_qlora", "edge_type": "supports", "strength": 1.0},

    # -- A4W4 (native 4-bit compute: FP4 on Blackwell/CDNA4, INT4 on Ada/Ampere) --
    {"source_id": "hw_b200", "target_id": "sch_dyn_a4w4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "via native NVFP4 tensor cores (FP4 E2M1)"}},
    {"source_id": "hw_gb200", "target_id": "sch_dyn_a4w4", "edge_type": "supports", "strength": 1.0, "metadata_json": {"note": "via native NVFP4 tensor cores"}},
    {"source_id": "hw_rtx5090", "target_id": "sch_dyn_a4w4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "via native NVFP4 tensor cores"}},
    {"source_id": "hw_mi350", "target_id": "sch_dyn_a4w4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "via native CDNA4 FP4 (E2M1)"}},
    {"source_id": "hw_a100", "target_id": "sch_dyn_a4w4", "edge_type": "supports", "strength": 0.8, "metadata_json": {"note": "via native INT4 tensor cores (CC 8.0); ATOM/QuiK target this"}},
    {"source_id": "hw_l40s", "target_id": "sch_dyn_a4w4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "via native INT4 tensor cores (CC 8.9)"}},
    {"source_id": "hw_rtx4090", "target_id": "sch_dyn_a4w4", "edge_type": "supports", "strength": 0.9, "metadata_json": {"note": "via native INT4 tensor cores (CC 8.9)"}},
]


# ============================================================================
# Dynamic parsing from papers/ directory
# ============================================================================

# Mapping from algorithm name variants to canonical node IDs
_ALGO_NAME_TO_ID: dict[str, str] = {
    "awq": "algo_awq",
    "gptq": "algo_gptq",
    "rtn": "algo_rtn",
    "hqq": "algo_hqq",
    "smoothquant": "algo_smoothquant",
    "omniquant": "algo_omniquant",
    "quarot": "algo_quarot",
    "spqr": "algo_spqr",
    "owq": "algo_owq",
    "llm.int8()": "algo_llmint8",
    "llm.int8": "algo_llmint8",
    "zeroquant": "algo_zeroquant",
    "bitnet": "algo_bitnet",
    "bitnet b1.58": "algo_bitnet",
    "paretoq": "algo_paretoq",
    "pareto-q": "algo_paretoq",
    "qlora": "algo_qlora",
    "squeezellm": "algo_squeezellm",
    "atom": "algo_atom",
    "quik": "algo_quik",
    "fp8 quantization": "algo_fp8quant",
    "kv-cache quantization": "algo_kvcache_quant",
    "qat": "algo_qat_generic",
}

# Mapping from scope descriptions to category codes
_SCOPE_TO_CATEGORY: dict[str, str] = {
    "weight-only": "ptq_weight",
    "w+a": "ptq_wa",
    "w+a (mixed-precision)": "ptq_wa",
    "weight-only / w+a": "ptq_mixed",
    "1-bit": "qat",
    "mixed": "ptq_mixed",
    "mixed-precision": "ptq_mixed",
}


def _parse_algorithms_table(workspace_root: str) -> tuple[list[dict], list[dict]]:
    """Parse papers/quantization_algorithms_table.md for algorithm data.

    Returns (extra_nodes, extra_edges) to merge with hardcoded base.
    """
    table_path = os.path.join(workspace_root, "papers", "quantization_algorithms_table.md")
    if not os.path.isfile(table_path):
        logger.debug(f"Algorithms table not found at {table_path}")
        return [], []

    extra_nodes: list[dict[str, Any]] = []
    extra_edges: list[dict[str, Any]] = []

    try:
        with open(table_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse the main table (lines starting with | ** or | that have algorithm names)
        # Format: | Algorithm | Quant Type | Scope | Bits | Calibration | Description | Datasets | Paper |
        table_pattern = re.compile(
            r"^\|\s*\*\*(\w[\w.() /]*?)\*\*\s*\|"  # Algorithm name in bold
            r"\s*(.*?)\s*\|"  # Quant Type
            r"\s*(.*?)\s*\|"  # Scope
            r"\s*(.*?)\s*\|"  # Bits
            r"\s*(.*?)\s*\|"  # Calibration
            r"\s*(.*?)\s*\|"  # Description
            r"\s*(.*?)\s*\|"  # Benchmarking Datasets
            r"\s*(.*?)\s*\|",  # Paper / Source
            re.MULTILINE,
        )

        for match in table_pattern.finditer(content):
            algo_name = match.group(1).strip()
            quant_type = match.group(2).strip()
            scope = match.group(3).strip().lower()
            bits_str = match.group(4).strip()
            calibration = match.group(5).strip().lower()
            description = match.group(6).strip()
            datasets = match.group(7).strip()
            paper_ref = match.group(8).strip()

            # Find canonical node ID
            algo_key = algo_name.lower()
            node_id = _ALGO_NAME_TO_ID.get(algo_key)

            if not node_id:
                # Unknown algorithm not in hardcoded set -- skip
                logger.debug(f"Skipping unknown algorithm from table: {algo_name}")
                continue

            # Check if node already exists in hardcoded data
            existing_ids = {n["id"] for n in ALGORITHM_NODES}
            if node_id not in existing_ids:
                # New algorithm -- create a node
                category = _SCOPE_TO_CATEGORY.get(scope, "ptq_weight")
                extra_nodes.append({
                    "id": node_id,
                    "label": algo_name,
                    "node_type": "algorithm",
                    "category": category,
                    "metadata_json": {
                        "type": quant_type,
                        "scope": scope,
                        "bits": bits_str,
                        "calibration": calibration,
                        "description": description,
                        "datasets": datasets,
                        "paper_ref": paper_ref,
                    },
                })

            # Extract arxiv ID from paper reference
            arxiv_match = re.search(r"arXiv:(\d{4}\.\d{4,5})", paper_ref)
            if arxiv_match:
                # Update metadata on existing node (will be merged later)
                for existing_node in ALGORITHM_NODES:
                    if existing_node["id"] == node_id:
                        existing_node["metadata_json"].setdefault("arxiv_id", arxiv_match.group(1))
                        existing_node["metadata_json"].setdefault("description", description)
                        existing_node["metadata_json"].setdefault("datasets", datasets)
                        existing_node["metadata_json"].setdefault(
                            "calibration", "yes" if calibration.startswith("yes") else "no"
                        )
                        break

            # Parse bit widths and create additional data type edges
            parsed_bits = _parse_bits(bits_str)
            for bit_val in parsed_bits:
                dt_id = _bit_to_datatype_id(bit_val)
                if dt_id:
                    edge = {
                        "source_id": node_id,
                        "target_id": dt_id,
                        "edge_type": "uses",
                        "strength": 1.0 if bit_val in (4, 8) else 0.7,
                    }
                    # Only add if not already in hardcoded edges
                    if not _edge_exists(edge, EDGES):
                        extra_edges.append(edge)

        logger.info(
            f"Parsed algorithms table: {len(extra_nodes)} new nodes, "
            f"{len(extra_edges)} new edges"
        )

    except Exception as e:
        logger.warning(f"Failed to parse algorithms table: {e}")

    return extra_nodes, extra_edges


def _parse_paper_notes(workspace_root: str) -> dict[str, dict[str, Any]]:
    """Parse papers/notes/*.yaml to enrich algorithm metadata.

    Returns a dict of {node_id: metadata_updates}.
    """
    notes_dir = os.path.join(workspace_root, "papers", "notes")
    if not os.path.isdir(notes_dir):
        logger.debug(f"Paper notes directory not found at {notes_dir}")
        return {}

    enrichments: dict[str, dict[str, Any]] = {}

    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed; cannot parse paper notes.")
        return {}

    for filename in os.listdir(notes_dir):
        if not filename.endswith((".yaml", ".yml")):
            continue

        filepath = os.path.join(notes_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                note = yaml.safe_load(f)

            if not isinstance(note, dict):
                continue

            # Map the note ID to a node ID
            note_id = note.get("id", filename.replace(".yaml", "").replace(".yml", ""))
            node_id = _ALGO_NAME_TO_ID.get(note_id.lower())

            if not node_id:
                logger.debug(f"No matching node for paper note: {note_id}")
                continue

            # Collect enrichment data
            enrichment: dict[str, Any] = {}
            for key in ("core_idea", "relevant_equations", "expected_behavior",
                        "known_limitations", "citation", "title", "authors",
                        "venue", "arxiv_id", "year"):
                value = note.get(key)
                if value:
                    enrichment[key] = value

            if note.get("tags"):
                enrichment["tags"] = note["tags"]

            if enrichment:
                enrichments[node_id] = enrichment
                logger.debug(f"Enriched {node_id} with {len(enrichment)} fields from {filename}")

        except Exception as e:
            logger.warning(f"Failed to parse paper note {filename}: {e}")

    logger.info(f"Parsed {len(enrichments)} paper note files")
    return enrichments


def _parse_bits(bits_str: str) -> list[int]:
    """Parse a bits string like '2, 3, 4, 8' or '2-8' into a list of ints."""
    result = []
    for part in bits_str.replace(" ", "").split(","):
        part = part.strip()
        if not part:
            continue
        range_match = re.match(r"(\d+)[–-](\d+)", part)
        if range_match:
            lo, hi = int(range_match.group(1)), int(range_match.group(2))
            result.extend(range(lo, hi + 1))
        else:
            try:
                val = float(part)
                if val == int(val):
                    result.append(int(val))
            except ValueError:
                pass
    return sorted(set(result))


def _bit_to_datatype_id(bits: int) -> str | None:
    """Map a bit width to the corresponding data type node ID."""
    mapping = {
        1: "dt_binary",
        2: "dt_int2",
        3: "dt_int3",
        4: "dt_int4",
        8: "dt_int8",
        16: "dt_fp16",
    }
    return mapping.get(bits)


def _edge_exists(edge: dict, edge_list: list[dict]) -> bool:
    """Check if an edge already exists in a list."""
    for existing in edge_list:
        if (existing["source_id"] == edge["source_id"]
                and existing["target_id"] == edge["target_id"]
                and existing["edge_type"] == edge["edge_type"]):
            return True
    return False


# ============================================================================
# Seeding function
# ============================================================================


def seed_knowledge_graph(db_url: str | None = None) -> int:
    """Insert all seed nodes and edges into Postgres.

    Combines hardcoded base data with dynamically parsed data from
    papers/quantization_algorithms_table.md and papers/notes/*.yaml.

    Returns the number of nodes created.
    """
    import json as _json

    from ..db.models import KnowledgeEdge, KnowledgeNode, get_session

    session = get_session(db_url)
    count = 0

    # Determine workspace root (navigate up from src/knowledge/)
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Parse dynamic data
    extra_nodes, extra_edges = _parse_algorithms_table(workspace_root)
    enrichments = _parse_paper_notes(workspace_root)

    try:
        # Build the full node list (hardcoded + dynamic)
        all_nodes = (
            [{"node_type": "data_type", **n} for n in DATA_TYPE_NODES]
            + [{"node_type": "hardware", **n} for n in HARDWARE_NODES]
            + [{"node_type": "scheme", **n} for n in SCHEME_NODES]
            + [{"node_type": "algorithm", **n} for n in ALGORITHM_NODES]
            + extra_nodes  # Already have node_type set
        )

        # Enrich algorithm nodes with paper note metadata
        for node in all_nodes:
            if node["id"] in enrichments:
                meta = node.get("metadata_json", {})
                meta.update(enrichments[node["id"]])
                node["metadata_json"] = meta

        # Build the full edge list (hardcoded + dynamic)
        all_edges = EDGES + extra_edges

        # Insert nodes
        for n in all_nodes:
            existing = session.query(KnowledgeNode).filter(KnowledgeNode.id == n["id"]).first()
            if existing:
                # Update metadata if we have enrichments
                if n["id"] in enrichments:
                    current_meta = existing.metadata_json or {}
                    current_meta.update(enrichments[n["id"]])
                    existing.metadata_json = current_meta
                continue
            node = KnowledgeNode(
                id=n["id"],
                label=n["label"],
                node_type=n["node_type"],
                category=n.get("category"),
                metadata_json=n.get("metadata_json", {}),
            )
            session.add(node)
            count += 1

        session.flush()

        # Insert edges
        for e in all_edges:
            existing = (
                session.query(KnowledgeEdge)
                .filter(
                    KnowledgeEdge.source_id == e["source_id"],
                    KnowledgeEdge.target_id == e["target_id"],
                    KnowledgeEdge.edge_type == e["edge_type"],
                )
                .first()
            )
            if existing:
                continue
            edge = KnowledgeEdge(
                source_id=e["source_id"],
                target_id=e["target_id"],
                edge_type=e["edge_type"],
                strength=e.get("strength", 0.5),
                metadata_json=e.get("metadata_json", {}),
            )
            session.add(edge)

        session.commit()
        logger.info(f"Seeded knowledge graph: {count} new nodes")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed knowledge graph: {e}")
        raise
    finally:
        session.close()

    return count
