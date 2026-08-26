"""End-to-end quantize -> export -> serve -> benchmark pipeline via vLLM.

Orchestrates:
1. Quantize a model via LightCompress
2. Export the quantized model in a vLLM-compatible format
3. Spin up a vLLM server (local process or Docker container)
4. Run inference benchmarks with standardised protocols
5. Collect TTFT, TBT, throughput, and latency metrics
"""

from __future__ import annotations

import json
import logging
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


class VLLMConfig(BaseModel):
    """Configuration for the vLLM benchmark pipeline."""

    # Model
    model_path: str = Field(..., description="Path to quantised model or HF model ID")
    dtype: str = Field("auto", description="Model dtype (auto, float16, bfloat16)")
    quantization: str | None = Field(None, description="vLLM quantization method (awq, gptq, ...)")
    max_model_len: int | None = Field(None, description="Max context length")

    # Server
    host: str = "localhost"
    port: int = 8000
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.90

    # Benchmark protocol
    warmup_requests: int = 5
    batch_sizes: list[int] = Field(default_factory=lambda: [1, 4, 8, 16, 32])
    input_lengths: list[int] = Field(default_factory=lambda: [128, 512, 2048])
    output_length: int = 128
    num_requests_per_config: int = 10

    # Prompts
    prompt_template: str = "Write a detailed explanation of {topic}."
    topics: list[str] = Field(
        default_factory=lambda: [
            "quantum computing",
            "machine learning optimisation",
            "distributed systems architecture",
            "neural network quantization",
            "transformer attention mechanisms",
        ]
    )


# ============================================================================
# Results
# ============================================================================


@dataclass
class InferenceResult:
    """Structured result from a single inference benchmark configuration."""

    batch_size: int = 1
    input_length: int = 128
    output_length: int = 128

    # Time-to-first-token (seconds)
    ttft_mean: float = 0.0
    ttft_p50: float = 0.0
    ttft_p95: float = 0.0
    ttft_p99: float = 0.0

    # Time-between-tokens (seconds) — measured per-token from SSE timestamps
    tbt_mean: float = 0.0
    tbt_p50: float = 0.0
    tbt_p95: float = 0.0
    tbt_p99: float = 0.0

    # Throughput
    tokens_per_second: float = 0.0
    requests_per_second: float = 0.0

    # End-to-end
    e2e_latency_mean: float = 0.0
    e2e_latency_p50: float = 0.0
    e2e_latency_p95: float = 0.0

    # Raw data
    raw_ttfts: list[float] = field(default_factory=list)
    raw_e2e: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_size": self.batch_size,
            "input_length": self.input_length,
            "output_length": self.output_length,
            "ttft_mean_s": self.ttft_mean,
            "ttft_p50_s": self.ttft_p50,
            "ttft_p95_s": self.ttft_p95,
            "ttft_p99_s": self.ttft_p99,
            "tbt_mean_s": self.tbt_mean,
            "tbt_p50_s": self.tbt_p50,
            "tbt_p95_s": self.tbt_p95,
            "tbt_p99_s": self.tbt_p99,
            "tokens_per_second": self.tokens_per_second,
            "requests_per_second": self.requests_per_second,
            "e2e_latency_mean_s": self.e2e_latency_mean,
            "e2e_latency_p50_s": self.e2e_latency_p50,
            "e2e_latency_p95_s": self.e2e_latency_p95,
        }


# ============================================================================
# VLLMBenchmark
# ============================================================================


class VLLMBenchmark:
    """End-to-end vLLM inference benchmarking."""

    def __init__(self, config: VLLMConfig):
        self.config = config
        self.base_url = f"http://{config.host}:{config.port}"
        self._server_process: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def start_server(self, wait_timeout: int = 120) -> None:
        """Start a local vLLM server process."""
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", self.config.model_path,
            "--host", "0.0.0.0",
            "--port", str(self.config.port),
            "--dtype", self.config.dtype,
            "--tensor-parallel-size", str(self.config.tensor_parallel_size),
            "--gpu-memory-utilization", str(self.config.gpu_memory_utilization),
        ]
        if self.config.quantization:
            cmd.extend(["--quantization", self.config.quantization])
        if self.config.max_model_len:
            cmd.extend(["--max-model-len", str(self.config.max_model_len)])

        logger.info(f"Starting vLLM server: {' '.join(cmd)}")
        self._server_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Wait for health check
        self._wait_for_server(wait_timeout)

    def stop_server(self) -> None:
        """Stop the local vLLM server process."""
        if self._server_process:
            self._server_process.terminate()
            try:
                self._server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._server_process.kill()
            self._server_process = None
            logger.info("vLLM server stopped")

    def _wait_for_server(self, timeout: int) -> None:
        """Block until the vLLM server responds to /health."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = httpx.get(f"{self.base_url}/health", timeout=2)
                if r.status_code == 200:
                    logger.info("vLLM server is ready")
                    return
            except Exception as e:
                logger.debug(f"vLLM health check not ready yet: {e}")
            time.sleep(2)
        raise TimeoutError(f"vLLM server did not start within {timeout}s")

    # ------------------------------------------------------------------
    # Benchmarking
    # ------------------------------------------------------------------

    def run_benchmarks(self) -> list[InferenceResult]:
        """Run the full benchmark protocol across all configurations.

        Returns:
            List of InferenceResult for each (batch_size, input_length) combo.
        """
        results: list[InferenceResult] = []

        # Warmup
        logger.info(f"Warming up with {self.config.warmup_requests} requests...")
        for _ in range(self.config.warmup_requests):
            self._send_completion("Hello", max_tokens=16)

        for input_len in self.config.input_lengths:
            for batch_size in self.config.batch_sizes:
                logger.info(
                    f"Benchmarking: batch_size={batch_size}, "
                    f"input_len={input_len}, output_len={self.config.output_length}"
                )
                result = self._benchmark_config(
                    batch_size=batch_size,
                    input_length=input_len,
                    output_length=self.config.output_length,
                    num_requests=self.config.num_requests_per_config,
                )
                results.append(result)

        return results

    def _benchmark_config(
        self,
        batch_size: int,
        input_length: int,
        output_length: int,
        num_requests: int,
    ) -> InferenceResult:
        """Benchmark a single configuration with concurrent batch requests.

        Sends ``batch_size`` concurrent streaming requests using asyncio,
        repeating for ``num_requests`` rounds. Per-request TTFT and per-token
        TBT are measured from SSE timestamps.
        """
        import asyncio

        prompt = self._generate_prompt(input_length)

        all_ttfts: list[float] = []
        all_e2e: list[float] = []
        all_token_timestamps: list[list[float]] = []
        total_output_tokens = 0

        async def _single_streaming_request(
            client: httpx.AsyncClient,
        ) -> tuple[float | None, float, int, list[float]]:
            """Send one streaming request and return (ttft, e2e, tokens, token_times)."""
            start = time.perf_counter()
            first_token_time: float | None = None
            tokens_received = 0
            token_times: list[float] = []

            async with client.stream(
                "POST",
                f"{self.base_url}/v1/completions",
                json={
                    "model": self.config.model_path,
                    "prompt": prompt,
                    "max_tokens": output_length,
                    "stream": True,
                    "temperature": 0.0,
                },
                timeout=120,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        now = time.perf_counter()
                        if first_token_time is None:
                            first_token_time = now
                        token_times.append(now)
                        tokens_received += 1

            end = time.perf_counter()
            ttft = (first_token_time - start) if first_token_time is not None else None
            e2e = end - start
            return ttft, e2e, tokens_received, token_times

        async def _run_batch(client: httpx.AsyncClient) -> None:
            """Send batch_size concurrent requests."""
            tasks = [_single_streaming_request(client) for _ in range(batch_size)]
            results = await asyncio.gather(*tasks, return_exceptions=False)
            for ttft, e2e, tokens, token_times in results:
                if ttft is not None:
                    all_ttfts.append(ttft)
                all_e2e.append(e2e)
                nonlocal total_output_tokens
                total_output_tokens += tokens
                if token_times:
                    all_token_timestamps.append(token_times)

        async def _run_all() -> None:
            async with httpx.AsyncClient() as client:
                for round_idx in range(num_requests):
                    try:
                        await _run_batch(client)
                    except Exception as e:
                        raise RuntimeError(
                            f"Benchmark request failed in round {round_idx} "
                            f"(batch_size={batch_size}): {e}. "
                            f"Benchmark results would be incomplete."
                        ) from e

        asyncio.run(_run_all())

        # ── Compute statistics ────────────────────────────────────────
        result = InferenceResult(
            batch_size=batch_size,
            input_length=input_length,
            output_length=output_length,
            raw_ttfts=all_ttfts,
            raw_e2e=all_e2e,
        )

        if all_ttfts:
            sorted_ttfts = sorted(all_ttfts)
            result.ttft_mean = statistics.mean(all_ttfts)
            result.ttft_p50 = self._percentile(sorted_ttfts, 50)
            result.ttft_p95 = self._percentile(sorted_ttfts, 95)
            result.ttft_p99 = self._percentile(sorted_ttfts, 99)

        if all_e2e:
            sorted_e2e = sorted(all_e2e)
            result.e2e_latency_mean = statistics.mean(all_e2e)
            result.e2e_latency_p50 = self._percentile(sorted_e2e, 50)
            result.e2e_latency_p95 = self._percentile(sorted_e2e, 95)

            total_time = sum(all_e2e)
            if total_time > 0:
                result.tokens_per_second = total_output_tokens / total_time
                result.requests_per_second = len(all_e2e) / total_time

        # ── Per-token TBT from recorded timestamps ────────────────────
        # Collect inter-token intervals from every request that produced ≥2 tokens
        inter_token_intervals: list[float] = []
        for token_times in all_token_timestamps:
            if len(token_times) >= 2:
                for i in range(1, len(token_times)):
                    inter_token_intervals.append(token_times[i] - token_times[i - 1])

        if not inter_token_intervals and total_output_tokens > 0:
            # Every request produced at most 1 token — cannot compute TBT
            raise RuntimeError(
                f"Cannot compute per-token TBT: all {len(all_token_timestamps)} "
                f"streaming responses returned fewer than 2 tokens. "
                f"Increase output_length (currently {output_length}) or "
                f"verify the model is generating correctly."
            )

        if inter_token_intervals:
            sorted_iti = sorted(inter_token_intervals)
            result.tbt_mean = statistics.mean(inter_token_intervals)
            result.tbt_p50 = self._percentile(sorted_iti, 50)
            result.tbt_p95 = self._percentile(sorted_iti, 95)
            result.tbt_p99 = self._percentile(sorted_iti, 99)

        return result

    def _send_completion(
        self, prompt: str, max_tokens: int = 64
    ) -> dict[str, Any]:
        """Send a non-streaming completion request."""
        try:
            r = httpx.post(
                f"{self.base_url}/v1/completions",
                json={
                    "model": self.config.model_path,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                },
                timeout=60,
            )
            return r.json()
        except Exception as e:
            raise RuntimeError(
                f"vLLM completion request failed: {e}."
            ) from e

    def _generate_prompt(self, target_length: int) -> str:
        """Generate a prompt of approximately target_length tokens."""
        # Rough heuristic: 1 token ~ 4 chars
        topics = self.config.topics
        base = self.config.prompt_template.format(topic=topics[0])
        char_target = target_length * 4
        while len(base) < char_target:
            for topic in topics:
                base += f" Also discuss {topic} in detail."
                if len(base) >= char_target:
                    break
        return base[:char_target]

    @staticmethod
    def _percentile(sorted_values: list[float], pct: int) -> float:
        if not sorted_values:
            return 0.0
        idx = int(len(sorted_values) * pct / 100)
        idx = min(idx, len(sorted_values) - 1)
        return sorted_values[idx]
