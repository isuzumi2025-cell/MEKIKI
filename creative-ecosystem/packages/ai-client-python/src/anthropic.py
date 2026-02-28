"""
ICC AI Client - Anthropic Claude implementation

Supported models:
  claude-sonnet-4-6   (default, fast & capable)
  claude-opus-4-6     (highest accuracy, higher cost)

Environment variables:
  ANTHROPIC_API_KEY   Required.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import LLMClient, LLMResponse

# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

_RETRY_DECORATOR = retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)


def _load_api_key() -> Optional[str]:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# AnthropicClient
# ---------------------------------------------------------------------------


class AnthropicClient(LLMClient):
    """
    Anthropic Claude LLM client.

    Args:
        model:      Claude model identifier.  Defaults to "claude-sonnet-4-6".
        max_tokens: Maximum tokens to generate.  Defaults to 4096.

    Kwargs accepted by generate():
        system (str): System prompt text prepended to the conversation.

    Example::

        client = AnthropicClient()
        resp = client.generate(
            "What is the capital of France?",
            system="You are a helpful geography assistant.",
        )
        print(resp.text)
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"
    SUPPORTED_MODELS = [
        "claude-sonnet-4-6",
        "claude-opus-4-6",
    ]

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
    ) -> None:
        self.model_name = model
        self.max_tokens = max_tokens
        self._client = None
        self._init_error: Optional[str] = None

        api_key = _load_api_key()
        if not api_key:
            self._init_error = "ANTHROPIC_API_KEY is not set"
            return

        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)
        except Exception as exc:
            self._init_error = f"Anthropic init failed: {exc}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        images: Optional[list[Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a completion using the Messages API.

        Args:
            prompt:  The user turn content.
            images:  Ignored (Claude vision via messages API is not wired here;
                     extend as needed for multimodal use-cases).
            **kwargs:
                system (str): Optional system prompt.

        Returns:
            LLMResponse.  On failure, text="" and error describes the problem.
        """
        if self._init_error or self._client is None:
            return LLMResponse(
                text="",
                model=self.model_name,
                error=self._init_error or "Client not initialised",
            )

        system_prompt: Optional[str] = kwargs.get("system")

        try:
            return self._generate_with_retry(prompt, system_prompt)
        except Exception as exc:
            return LLMResponse(
                text="",
                model=self.model_name,
                error=str(exc),
            )

    def analyze(self, text: str, instruction: str) -> LLMResponse:
        """Apply *instruction* to *text* via a combined prompt."""
        combined = f"{instruction}\n\nText:\n{text}"
        return self.generate(combined)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @_RETRY_DECORATOR
    def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> LLMResponse:
        create_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        t0 = time.monotonic()
        message = self._client.messages.create(**create_kwargs)
        latency_ms = (time.monotonic() - t0) * 1000

        text = ""
        for block in message.content:
            if hasattr(block, "text"):
                text += block.text

        tokens_used = 0
        try:
            tokens_used = (message.usage.input_tokens or 0) + (
                message.usage.output_tokens or 0
            )
        except Exception:
            pass

        return LLMResponse(
            text=text,
            model=self.model_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
