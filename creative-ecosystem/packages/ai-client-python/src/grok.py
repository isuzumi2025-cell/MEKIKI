"""
ICC AI Client - xAI Grok implementation

Uses the OpenAI-compatible API at https://api.x.ai/v1.

Supported models:
  grok-2   (default)
  grok-3

Environment variables:
  GROK_API_KEY   Required.
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

_XAI_BASE_URL = "https://api.x.ai/v1"


def _load_api_key() -> Optional[str]:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return os.environ.get("GROK_API_KEY")


# ---------------------------------------------------------------------------
# GrokClient
# ---------------------------------------------------------------------------


class GrokClient(LLMClient):
    """
    xAI Grok client using the OpenAI-compatible REST API.

    Args:
        model: Grok model identifier.  Defaults to "grok-2".

    Example::

        client = GrokClient()
        resp = client.generate("Describe the ICC monorepo in one sentence.")
        print(resp.text)
    """

    DEFAULT_MODEL = "grok-2"
    SUPPORTED_MODELS = [
        "grok-2",
        "grok-3",
    ]

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model_name = model
        self._client = None
        self._init_error: Optional[str] = None

        api_key = _load_api_key()
        if not api_key:
            self._init_error = "GROK_API_KEY is not set"
            return

        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, base_url=_XAI_BASE_URL)
        except Exception as exc:
            self._init_error = f"Grok init failed: {exc}"

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
        Generate a completion via the xAI API.

        Args:
            prompt: User text prompt.
            images: Accepted for interface compatibility but currently ignored
                    (Grok vision support may be added in a future version).
            **kwargs: Unused; accepted for interface compatibility.

        Returns:
            LLMResponse.  On failure, text="" and error is set.
        """
        if self._init_error or self._client is None:
            return LLMResponse(
                text="",
                model=self.model_name,
                error=self._init_error or "Client not initialised",
            )

        try:
            return self._generate_with_retry(prompt)
        except Exception as exc:
            return LLMResponse(
                text="",
                model=self.model_name,
                error=str(exc),
            )

    def analyze(self, text: str, instruction: str) -> LLMResponse:
        """Apply *instruction* to *text* via a combined prompt."""
        combined = f"{instruction}\n\n{text}"
        return self.generate(combined)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @_RETRY_DECORATOR
    def _generate_with_retry(self, prompt: str) -> LLMResponse:
        t0 = time.monotonic()
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = (time.monotonic() - t0) * 1000

        text = response.choices[0].message.content or ""

        tokens_used = 0
        try:
            tokens_used = response.usage.total_tokens or 0
        except Exception:
            pass

        return LLMResponse(
            text=text,
            model=self.model_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
