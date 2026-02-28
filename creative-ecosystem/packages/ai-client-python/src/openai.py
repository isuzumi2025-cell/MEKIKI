"""
ICC AI Client - OpenAI implementation

Supported models:
  gpt-4o       (default, fast, multimodal)
  gpt-4-turbo  (128k context, vision capable)

Environment variables:
  OPENAI_API_KEY   Required.
"""

from __future__ import annotations

import base64
import io
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
    return os.environ.get("OPENAI_API_KEY")


def _image_to_b64(image: Any) -> Optional[str]:
    """
    Convert an image argument to a base64-encoded PNG string.

    Accepts PIL.Image.Image, raw bytes, or an existing base64 string.
    Returns None if conversion fails.
    """
    try:
        from PIL import Image

        if isinstance(image, Image.Image):
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        pass

    if isinstance(image, bytes):
        return base64.b64encode(image).decode()

    if isinstance(image, str):
        # Assume already base64
        return image

    return None


# ---------------------------------------------------------------------------
# OpenAIClient
# ---------------------------------------------------------------------------


class OpenAIClient(LLMClient):
    """
    OpenAI ChatCompletion client with vision support.

    Args:
        model: OpenAI model identifier.  Defaults to "gpt-4o".

    Example::

        client = OpenAIClient()
        resp = client.generate("Explain the ICC project briefly.")
        print(resp.text)
    """

    DEFAULT_MODEL = "gpt-4o"
    SUPPORTED_MODELS = [
        "gpt-4o",
        "gpt-4-turbo",
    ]

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model_name = model
        self._client = None
        self._init_error: Optional[str] = None

        api_key = _load_api_key()
        if not api_key:
            self._init_error = "OPENAI_API_KEY is not set"
            return

        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
        except Exception as exc:
            self._init_error = f"OpenAI init failed: {exc}"

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
        Generate a completion, optionally with vision inputs.

        Args:
            prompt: User text.
            images: Optional list of PIL Images, bytes, or base64 strings.
                    Passed as image_url content parts when provided.
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
            return self._generate_with_retry(prompt, images)
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
        images: Optional[list[Any]],
    ) -> LLMResponse:
        if images:
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for img in images:
                b64 = _image_to_b64(img)
                if b64:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        }
                    )
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": prompt}]

        t0 = time.monotonic()
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
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
