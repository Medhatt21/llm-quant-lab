"""Scientist LLM API client.

This module provides a client for calling OpenAI-compatible LLM APIs
to generate research reports from experiment data.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from the LLM API."""
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    
    # Raw response for debugging
    raw_response: dict[str, Any] | None = None


class ScientistLLMClient:
    """Client for calling scientist LLM API.
    
    Supports OpenAI-compatible APIs (OpenAI, Azure, Anthropic via proxy, etc.)
    
    Environment variables (all required — no silent defaults):
        SCIENTIST_LLM_BASE_URL: API base URL
        SCIENTIST_LLM_API_KEY: API key
        SCIENTIST_LLM_MODEL: Model name
        SCIENTIST_LLM_TIMEOUT: Request timeout in seconds
    """
    
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        """Initialize the client.
        
        Args:
            base_url: API base URL (overrides env var)
            api_key: API key (overrides env var)
            model: Model name (overrides env var)
            timeout: Request timeout in seconds (overrides env var)
        
        Raises:
            RuntimeError: If required configuration is missing.
        """
        self.base_url = base_url or os.getenv("SCIENTIST_LLM_BASE_URL", "")
        if not self.base_url:
            raise RuntimeError(
                "SCIENTIST_LLM_BASE_URL is not set.  "
                "Configure the scientist LLM endpoint in your .env file."
            )
        self.api_key = api_key or os.getenv("SCIENTIST_LLM_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "SCIENTIST_LLM_API_KEY is not set.  "
                "Configure the scientist LLM API key in your .env file."
            )
        self.model = model or os.getenv("SCIENTIST_LLM_MODEL", "")
        if not self.model:
            raise RuntimeError(
                "SCIENTIST_LLM_MODEL is not set.  "
                "Configure the scientist LLM model name in your .env file."
            )
        timeout_str = os.getenv("SCIENTIST_LLM_TIMEOUT", "")
        if timeout is not None:
            self.timeout = timeout
        elif timeout_str:
            self.timeout = int(timeout_str)
        else:
            raise RuntimeError(
                "SCIENTIST_LLM_TIMEOUT is not set.  "
                "Configure the scientist LLM timeout in your .env file."
            )
        
        # Remove trailing slash from base URL
        self.base_url = self.base_url.rstrip("/")
        
        # Create HTTP client
        self._client = httpx.Client(
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
    
    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()
    
    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the LLM API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0 = deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            LLMResponse with the generated content
            
        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If the response is invalid
        """
        # Build messages
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        messages.append({
            "role": "user",
            "content": prompt,
        })
        
        # Build request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        
        logger.info(f"Calling LLM API: {self.model}")
        logger.debug(f"Prompt length: {len(prompt)} chars")
        
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract response
            choice = data["choices"][0]
            content = choice["message"]["content"]
            
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=content,
                model=data.get("model", self.model),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                finish_reason=choice.get("finish_reason", "unknown"),
                raw_response=data,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise
    
    def call_with_retry(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the LLM API with retries.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            max_retries: Maximum number of retries
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with the generated content
        """
        import time
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return self.call(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                
                # Don't retry on client errors (except rate limits)
                if e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.warning(f"LLM API error, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt
                logger.warning(f"LLM API error, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
        
        raise last_error or Exception("Max retries exceeded")
    
    def health_check(self) -> bool:
        """Check if the API is accessible.
        
        Returns:
            True if the API is accessible
        """
        try:
            # Try a minimal request
            response = self._client.get(f"{self.base_url}/models")
            return response.status_code in [200, 401]  # 401 means API is up but key is wrong
        except Exception:
            return False


# ============================================================================
# Stub client for testing
# ============================================================================


class StubScientistLLMClient:
    """Stub client for testing without an actual LLM API.
    
    Returns predefined responses for testing the pipeline.
    """
    
    def __init__(self, **kwargs: Any):
        """Initialize stub client."""
        self.model = kwargs.get("model", "stub-model")
    
    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        **kwargs: Any,
    ) -> LLMResponse:
        """Return a stub response."""
        # Generate a simple stub report
        stub_content = f"""# Experiment Analysis Report

## Executive Summary

This is a stub report generated for testing purposes. The actual scientist LLM 
was not called.

## Methodology

The experiment applied quantization to a language model using the specified methods.

## Key Findings

1. **Quantization Applied**: The model was successfully quantized.
2. **Metrics Collected**: Perplexity and other metrics were measured.
3. **Performance**: Hardware benchmarks were collected.

## Comparison to Literature

Unable to compare without actual LLM analysis.

## Pass/Fail Judgment

**Status**: INCONCLUSIVE

This is a stub report and cannot make a real judgment.

## Suggested Next Experiments

1. Run with actual scientist LLM enabled
2. Compare multiple quantization methods
3. Test on larger models

---
*Generated by stub client for testing*
"""
        
        return LLMResponse(
            content=stub_content,
            model=self.model,
            prompt_tokens=len(prompt) // 4,  # Rough estimate
            completion_tokens=len(stub_content) // 4,
            total_tokens=(len(prompt) + len(stub_content)) // 4,
            finish_reason="stop",
            raw_response=None,
        )
    
    def call_with_retry(self, *args: Any, **kwargs: Any) -> LLMResponse:
        """Call without retry (stub always succeeds)."""
        return self.call(*args, **kwargs)
    
    def health_check(self) -> bool:
        """Stub is always healthy."""
        return True


def get_scientist_client() -> ScientistLLMClient | StubScientistLLMClient:
    """Get the appropriate scientist LLM client.
    
    Returns StubScientistLLMClient if no API key is configured.
    
    Returns:
        Client instance
    """
    api_key = os.getenv("SCIENTIST_LLM_API_KEY", "")
    
    if not api_key:
        logger.warning("No SCIENTIST_LLM_API_KEY configured, using stub client")
        return StubScientistLLMClient()
    
    return ScientistLLMClient()
