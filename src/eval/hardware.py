"""Hardware profiling and measurement utilities.

This module provides utilities for measuring latency, throughput,
memory usage, and power consumption during model inference.

IMPORTANT: This module enforces GPU-only execution. CPU fallback is not
supported for production quantization research. Use require_gpu() to
enforce this at the start of experiments.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import torch

logger = logging.getLogger(__name__)


# ============================================================================
# GPU Requirement Enforcement (Fail-Fast)
# ============================================================================


class GPUNotAvailableError(RuntimeError):
    """Raised when GPU is required but not available."""
    pass


def get_accelerator_device() -> str:
    """Get the available accelerator device (cuda or mps).
    
    This function checks for available GPU accelerators and returns
    the appropriate device string. It does NOT fall back to CPU.
    
    Returns:
        Device string: 'cuda' for NVIDIA/AMD GPUs, 'mps' for Apple Silicon
        
    Raises:
        GPUNotAvailableError: If no GPU accelerator is available
    """
    # Check CUDA (covers both NVIDIA and AMD ROCm)
    if torch.cuda.is_available():
        return "cuda"
    
    # Check Apple Silicon MPS
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    
    raise GPUNotAvailableError(
        "No GPU accelerator available. This project requires CUDA (NVIDIA/AMD ROCm) "
        "or MPS (Apple Silicon). CPU execution is not supported for production "
        "quantization research due to performance requirements.\n\n"
        "Solutions:\n"
        "  - For NVIDIA: Install CUDA toolkit and PyTorch with CUDA support\n"
        "  - For AMD: Install ROCm and PyTorch with ROCm support\n"
        "  - For Apple Silicon: Ensure PyTorch >= 1.12 with MPS support\n"
        "  - Use a cloud GPU instance (AWS, GCP, Lambda Labs, etc.)"
    )


def require_gpu() -> str:
    """Require GPU availability and return the device string.
    
    Call this at the start of any experiment or notebook to enforce
    GPU-only execution with a clear error message.
    
    Returns:
        Device string ('cuda' or 'mps')
        
    Raises:
        GPUNotAvailableError: If no GPU is available
        
    Example:
        >>> device = require_gpu()  # Fails fast if no GPU
        >>> model = model.to(device)
    """
    device = get_accelerator_device()
    
    # Log GPU info
    if device == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_count = torch.cuda.device_count()
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        logger.info(f"GPU available: {gpu_name} x{gpu_count} ({gpu_memory:.1f} GB)")
    elif device == "mps":
        logger.info("GPU available: Apple Silicon MPS")
    
    return device


def get_gpu_info() -> dict[str, Any]:
    """Get detailed GPU information.
    
    Returns:
        Dictionary with GPU details
        
    Raises:
        GPUNotAvailableError: If no GPU is available
    """
    device = get_accelerator_device()
    
    info = {
        "device": device,
        "available": True,
    }
    
    if device == "cuda":
        info.update({
            "name": torch.cuda.get_device_name(0),
            "count": torch.cuda.device_count(),
            "memory_gb": torch.cuda.get_device_properties(0).total_memory / (1024**3),
            "compute_capability": f"{torch.cuda.get_device_properties(0).major}.{torch.cuda.get_device_properties(0).minor}",
            "cuda_version": torch.version.cuda or "unknown",
        })
        
        # Check for ROCm (AMD)
        if hasattr(torch.version, "hip") and torch.version.hip:
            info["rocm_version"] = torch.version.hip
            info["is_rocm"] = True
        else:
            info["is_rocm"] = False
            
    elif device == "mps":
        info.update({
            "name": "Apple Silicon MPS",
            "count": 1,
            "is_mps": True,
        })
    
    return info


@dataclass
class HardwareProfile:
    """Hardware profile for a GPU."""
    gpu_type: str
    gpu_count: int = 1
    gpu_memory_gb: float = 0.0
    compute_capability: str = ""
    driver_version: str = ""
    cuda_version: str = ""
    rocm_version: str = ""
    
    # Measurement settings
    warmup_iterations: int = 3
    benchmark_iterations: int = 10
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "gpu_type": self.gpu_type,
            "gpu_count": self.gpu_count,
            "gpu_memory_gb": self.gpu_memory_gb,
            "compute_capability": self.compute_capability,
            "driver_version": self.driver_version,
            "cuda_version": self.cuda_version,
            "rocm_version": self.rocm_version,
        }


@dataclass
class LatencyStats:
    """Latency statistics from benchmarking."""
    p50: float = 0.0  # milliseconds
    p95: float = 0.0
    p99: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    
    # Throughput
    tokens_per_second: float = 0.0
    samples_per_second: float = 0.0
    
    # Test parameters
    batch_size: int = 1
    sequence_length: int = 0
    num_iterations: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "latency_p50_ms": self.p50,
            "latency_p95_ms": self.p95,
            "latency_p99_ms": self.p99,
            "latency_mean_ms": self.mean,
            "latency_std_ms": self.std,
            "latency_min_ms": self.min_val,
            "latency_max_ms": self.max_val,
            "tokens_per_second": self.tokens_per_second,
            "samples_per_second": self.samples_per_second,
            "batch_size": self.batch_size,
            "sequence_length": self.sequence_length,
            "num_iterations": self.num_iterations,
        }


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    allocated_gb: float = 0.0
    reserved_gb: float = 0.0
    peak_gb: float = 0.0
    
    # Model size
    model_size_mb: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_allocated_gb": self.allocated_gb,
            "memory_reserved_gb": self.reserved_gb,
            "memory_peak_gb": self.peak_gb,
            "model_size_mb": self.model_size_mb,
        }


@dataclass
class PowerStats:
    """Power consumption statistics."""
    avg_watts: float = 0.0
    peak_watts: float = 0.0
    energy_joules: float = 0.0
    duration_seconds: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "power_avg_watts": self.avg_watts,
            "power_peak_watts": self.peak_watts,
            "energy_joules": self.energy_joules,
            "duration_seconds": self.duration_seconds,
        }


# ============================================================================
# Hardware detection
# ============================================================================


def detect_hardware() -> HardwareProfile:
    """Detect available GPU hardware.
    
    Returns:
        HardwareProfile with detected information
    """
    profile = HardwareProfile(gpu_type="unknown")
    
    if torch.cuda.is_available():
        # NVIDIA GPU
        profile.gpu_count = torch.cuda.device_count()
        profile.gpu_type = torch.cuda.get_device_name(0)
        
        props = torch.cuda.get_device_properties(0)
        profile.gpu_memory_gb = props.total_memory / (1024 ** 3)
        profile.compute_capability = f"{props.major}.{props.minor}"
        
        # Get driver and CUDA version
        try:
            profile.cuda_version = torch.version.cuda or ""
        except Exception as e:
            logger.debug(f"Could not detect CUDA version: {e}")
        
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                profile.driver_version = result.stdout.strip().split("\n")[0]
        except Exception as e:
            logger.debug(f"nvidia-smi not available: {e}")
    
    elif hasattr(torch, "hip") and torch.hip.is_available():
        # AMD GPU (ROCm)
        profile.gpu_count = torch.cuda.device_count()  # ROCm uses CUDA API
        profile.gpu_type = torch.cuda.get_device_name(0)
        
        props = torch.cuda.get_device_properties(0)
        profile.gpu_memory_gb = props.total_memory / (1024 ** 3)
        
        # Get ROCm version
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                profile.rocm_version = "detected"
        except Exception as e:
            logger.debug(f"rocm-smi not available: {e}")
    
    logger.info(f"Detected hardware: {profile.gpu_type} x{profile.gpu_count}")
    
    return profile


# ============================================================================
# Latency measurement
# ============================================================================


def measure_latency(
    model: torch.nn.Module,
    input_fn: Callable[[], dict[str, torch.Tensor]],
    warmup_iterations: int = 3,
    benchmark_iterations: int = 10,
    device: str = "cuda",
) -> LatencyStats:
    """Measure inference latency.
    
    Args:
        model: Model to benchmark
        input_fn: Function that returns input tensors
        warmup_iterations: Number of warmup iterations
        benchmark_iterations: Number of benchmark iterations
        device: Device to run on
        
    Returns:
        LatencyStats with timing information
    """
    model.eval()
    
    # Get sample input for shape info
    sample_input = input_fn()
    batch_size = sample_input.get("input_ids", next(iter(sample_input.values()))).shape[0]
    seq_length = sample_input.get("input_ids", next(iter(sample_input.values()))).shape[1] if sample_input.get("input_ids") is not None else 0
    
    # Warmup
    logger.info(f"Running {warmup_iterations} warmup iterations")
    with torch.no_grad():
        for _ in range(warmup_iterations):
            inputs = input_fn()
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = model(**inputs)
    
    # Synchronize
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    
    # Benchmark
    logger.info(f"Running {benchmark_iterations} benchmark iterations")
    latencies = []
    
    with torch.no_grad():
        for _ in range(benchmark_iterations):
            inputs = input_fn()
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Time the forward pass
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            
            start = time.perf_counter()
            _ = model(**inputs)
            
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms
    
    # Compute statistics
    latencies_tensor = torch.tensor(latencies)
    sorted_latencies = latencies_tensor.sort()[0]
    
    stats = LatencyStats(
        p50=sorted_latencies[len(sorted_latencies) // 2].item(),
        p95=sorted_latencies[int(len(sorted_latencies) * 0.95)].item(),
        p99=sorted_latencies[int(len(sorted_latencies) * 0.99)].item(),
        mean=latencies_tensor.mean().item(),
        std=latencies_tensor.std().item(),
        min_val=latencies_tensor.min().item(),
        max_val=latencies_tensor.max().item(),
        batch_size=batch_size,
        sequence_length=seq_length,
        num_iterations=benchmark_iterations,
    )
    
    # Compute throughput
    if stats.mean > 0:
        stats.samples_per_second = 1000 / stats.mean * batch_size
        stats.tokens_per_second = stats.samples_per_second * seq_length
    
    logger.info(f"Latency: p50={stats.p50:.2f}ms, p95={stats.p95:.2f}ms, throughput={stats.tokens_per_second:.1f} tok/s")
    
    return stats


def measure_generation_latency(
    model: torch.nn.Module,
    tokenizer: Any,
    prompt: str,
    max_new_tokens: int = 50,
    warmup_iterations: int = 2,
    benchmark_iterations: int = 5,
    device: str = "cuda",
) -> LatencyStats:
    """Measure text generation latency.
    
    Args:
        model: Model to benchmark
        tokenizer: Tokenizer for encoding/decoding
        prompt: Input prompt
        max_new_tokens: Maximum tokens to generate
        warmup_iterations: Warmup iterations
        benchmark_iterations: Benchmark iterations
        device: Device to run on
        
    Returns:
        LatencyStats with generation timing
    """
    model.eval()
    
    # Encode prompt
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    prompt_length = inputs["input_ids"].shape[1]
    
    # Warmup
    with torch.no_grad():
        for _ in range(warmup_iterations):
            _ = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
    
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    
    # Benchmark
    latencies = []
    tokens_generated = []
    
    with torch.no_grad():
        for _ in range(benchmark_iterations):
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            
            start = time.perf_counter()
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
            
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            
            end = time.perf_counter()
            
            latencies.append((end - start) * 1000)
            tokens_generated.append(outputs.shape[1] - prompt_length)
    
    # Statistics
    latencies_tensor = torch.tensor(latencies)
    avg_tokens = sum(tokens_generated) / len(tokens_generated)
    
    stats = LatencyStats(
        p50=latencies_tensor.median().item(),
        mean=latencies_tensor.mean().item(),
        std=latencies_tensor.std().item(),
        min_val=latencies_tensor.min().item(),
        max_val=latencies_tensor.max().item(),
        batch_size=1,
        sequence_length=int(avg_tokens),
        num_iterations=benchmark_iterations,
    )
    
    # Tokens per second for generation
    if stats.mean > 0:
        stats.tokens_per_second = avg_tokens / (stats.mean / 1000)
    
    return stats


# ============================================================================
# Memory measurement
# ============================================================================


def measure_memory(
    model: torch.nn.Module | None = None,
    device: str = "cuda",
) -> MemoryStats:
    """Measure GPU memory usage.
    
    Args:
        model: Optional model to estimate size
        device: Device to measure
        
    Returns:
        MemoryStats with memory information
    """
    stats = MemoryStats()
    
    if not torch.cuda.is_available():
        return stats
    
    # Get current memory stats
    stats.allocated_gb = torch.cuda.memory_allocated() / (1024 ** 3)
    stats.reserved_gb = torch.cuda.memory_reserved() / (1024 ** 3)
    stats.peak_gb = torch.cuda.max_memory_allocated() / (1024 ** 3)
    
    # Estimate model size
    if model is not None:
        total_params = sum(p.numel() for p in model.parameters())
        param_size = sum(p.numel() * p.element_size() for p in model.parameters())
        stats.model_size_mb = param_size / (1024 ** 2)
    
    return stats


def reset_memory_stats() -> None:
    """Reset peak memory statistics."""
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.empty_cache()


# ============================================================================
# Power measurement
# ============================================================================


class PowerMonitor:
    """Monitor GPU power consumption.
    
    Uses nvidia-smi or rocm-smi to sample power draw.
    """
    
    def __init__(self, sample_interval: float = 0.1):
        """Initialize power monitor.
        
        Args:
            sample_interval: Sampling interval in seconds
        """
        self.sample_interval = sample_interval
        self._samples: list[float] = []
        self._monitoring = False
        self._start_time = 0.0
        self._end_time = 0.0
        
        # Detect available tool
        self._tool = self._detect_tool()
    
    def _detect_tool(self) -> str | None:
        """Detect available power monitoring tool."""
        # Try nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return "nvidia-smi"
        except Exception as e:
            logger.debug(f"nvidia-smi power query unavailable: {e}")
        
        # Try rocm-smi
        try:
            result = subprocess.run(
                ["rocm-smi", "--showpower"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return "rocm-smi"
        except Exception as e:
            logger.debug(f"rocm-smi power query unavailable: {e}")
        
        return None
    
    def _sample_power(self) -> float | None:
        """Sample current power draw in Watts."""
        if self._tool == "nvidia-smi":
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    power = float(result.stdout.strip().split("\n")[0])
                    return power
            except Exception as e:
                logger.debug(f"Power sampling via nvidia-smi failed: {e}")
        
        elif self._tool == "rocm-smi":
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showpower"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "Average" in line or "Power" in line:
                            parts = line.split()
                            for part in parts:
                                try:
                                    return float(part.replace("W", ""))
                                except ValueError:
                                    continue
            except Exception as e:
                logger.debug(f"Power sampling via rocm-smi failed: {e}")
        
        return None
    
    def start(self) -> None:
        """Start power monitoring."""
        self._samples = []
        self._start_time = time.time()
        self._monitoring = True
    
    def sample(self) -> None:
        """Take a power sample."""
        if not self._monitoring:
            return
        
        power = self._sample_power()
        if power is not None:
            self._samples.append(power)
    
    def stop(self) -> PowerStats:
        """Stop monitoring and return statistics."""
        self._end_time = time.time()
        self._monitoring = False
        
        if not self._samples:
            return PowerStats()
        
        samples_tensor = torch.tensor(self._samples)
        duration = self._end_time - self._start_time
        
        stats = PowerStats(
            avg_watts=samples_tensor.mean().item(),
            peak_watts=samples_tensor.max().item(),
            duration_seconds=duration,
            energy_joules=samples_tensor.mean().item() * duration,
        )
        
        return stats


def measure_power(
    func: Callable,
    sample_interval: float = 0.1,
) -> tuple[Any, PowerStats]:
    """Measure power consumption during function execution.
    
    Args:
        func: Function to execute
        sample_interval: Power sampling interval
        
    Returns:
        Tuple of (function result, PowerStats)
    """
    monitor = PowerMonitor(sample_interval)
    
    monitor.start()
    
    # Sample during execution
    import threading
    stop_event = threading.Event()
    
    def sample_loop():
        while not stop_event.is_set():
            monitor.sample()
            time.sleep(sample_interval)
    
    sample_thread = threading.Thread(target=sample_loop)
    sample_thread.start()
    
    try:
        result = func()
    finally:
        stop_event.set()
        sample_thread.join()
    
    stats = monitor.stop()
    
    return result, stats


# ============================================================================
# Combined profiling
# ============================================================================


@dataclass
class HardwareStats:
    """Combined hardware statistics."""
    profile: HardwareProfile
    latency: LatencyStats
    memory: MemoryStats
    power: PowerStats | None = None
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            **self.profile.to_dict(),
            **self.latency.to_dict(),
            **self.memory.to_dict(),
        }
        if self.power:
            result.update(self.power.to_dict())
        return result


def profile_model(
    model: torch.nn.Module,
    input_fn: Callable[[], dict[str, torch.Tensor]],
    warmup_iterations: int = 3,
    benchmark_iterations: int = 10,
    measure_power_consumption: bool = False,
    device: str = "cuda",
) -> HardwareStats:
    """Profile model performance comprehensively.
    
    Args:
        model: Model to profile
        input_fn: Function returning input tensors
        warmup_iterations: Warmup iterations
        benchmark_iterations: Benchmark iterations
        measure_power_consumption: Whether to measure power
        device: Device to run on
        
    Returns:
        HardwareStats with all measurements
    """
    # Detect hardware
    profile = detect_hardware()
    profile.warmup_iterations = warmup_iterations
    profile.benchmark_iterations = benchmark_iterations
    
    # Reset memory stats
    reset_memory_stats()
    
    # Measure latency (and optionally power)
    if measure_power_consumption:
        def run_benchmark():
            return measure_latency(
                model, input_fn, warmup_iterations, benchmark_iterations, device
            )
        
        latency, power = measure_power(run_benchmark)
    else:
        latency = measure_latency(
            model, input_fn, warmup_iterations, benchmark_iterations, device
        )
        power = None
    
    # Measure memory
    memory = measure_memory(model, device)
    
    return HardwareStats(
        profile=profile,
        latency=latency,
        memory=memory,
        power=power,
    )
