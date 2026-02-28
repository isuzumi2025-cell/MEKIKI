"""
ICC AI Client - Google Gemini implementation

Supported models:
  gemini-2.0-flash   (default, fast, multimodal)
  gemini-2.5-pro     (high accuracy, higher cost)

Embedding:
  models/text-embedding-004

Environment variables:
  GEMINI_API_KEY     Required for both LLM and embedding clients.
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

from .base import EmbeddingClient, LLMClient, LLMResponse

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (Exception,)

_RETRY_DECORATOR = retry(
    retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)


def _load_api_key() -> Optional[str]:
    """Return GEMINI_API_KEY from env, loading .env if present."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return os.environ.get("GEMINI_API_KEY")


def _pil_or_b64_to_pil(image: Any) -> Any:
    """
    Normalise an image argument to a PIL.Image.Image.

    Accepts:
    - PIL.Image.Image (returned as-is)
    - bytes (decoded as image)
    - str  (treated as base64-encoded image data)
    """
    try:
        from PIL import Image

        if isinstance(image, Image.Image):
            return image
        if isinstance(image, bytes):
            return Image.open(io.BytesIO(image))
        if isinstance(image, str):
            return Image.open(io.BytesIO(base64.b64decode(image)))
    except Exception:
        pass
    return image  # pass through and let the SDK complain if invalid


# ---------------------------------------------------------------------------
# GeminiClient
# ---------------------------------------------------------------------------


class GeminiClient(LLMClient):
    """
    Google Gemini LLM client with tenacity retry and graceful error handling.

    Args:
        model: Model ID string.  Defaults to "gemini-2.0-flash".

    Example::

        client = GeminiClient()
        resp = client.generate("Summarise the ICC project in one sentence.")
        print(resp.text)
    """

    DEFAULT_MODEL = "gemini-2.0-flash"
    SUPPORTED_MODELS = [
        "gemini-2.0-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash-lite",
    ]

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model_name = model
        self._model = None
        self._init_error: Optional[str] = None

        api_key = _load_api_key()
        if not api_key:
            self._init_error = "GEMINI_API_KEY is not set"
            return

        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(model)
        except Exception as exc:
            self._init_error = f"Gemini init failed: {exc}"

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
        Generate text, optionally including image inputs.

        Args:
            prompt: Instruction / question text.
            images: Optional list of PIL Images or base64 strings.
            **kwargs: Unused; accepted for interface compatibility.

        Returns:
            LLMResponse.  On failure, text="" and error is set.
        """
        if self._init_error or self._model is None:
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
        contents: list[Any] = [prompt]
        if images:
            for img in images:
                contents.append(_pil_or_b64_to_pil(img))

        t0 = time.monotonic()
        response = self._model.generate_content(
            contents,
            request_options={"timeout": 60},
        )
        latency_ms = (time.monotonic() - t0) * 1000

        text = response.text if (response and hasattr(response, "text")) else ""

        tokens_used = 0
        try:
            usage = response.usage_metadata
            tokens_used = (usage.prompt_token_count or 0) + (
                usage.candidates_token_count or 0
            )
        except Exception:
            pass

        return LLMResponse(
            text=text,
            model=self.model_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------------------
# GeminiEmbeddingClient
# ---------------------------------------------------------------------------


class GeminiEmbeddingClient(EmbeddingClient):
    """
    Text embedding via Google's ``models/text-embedding-004``.

    Args:
        model: Embedding model identifier.

    Example::

        client = GeminiEmbeddingClient()
        vector = client.embed("Hello, world!")
        print(len(vector))  # 768
    """

    DEFAULT_MODEL = "models/text-embedding-004"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model_name = model
        self._genai = None
        self._init_error: Optional[str] = None

        api_key = _load_api_key()
        if not api_key:
            self._init_error = "GEMINI_API_KEY is not set"
            return

        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self._genai = genai
        except Exception as exc:
            self._init_error = f"Gemini embedding init failed: {exc}"

    def embed(self, text: str) -> list[float]:
        """
        Return a dense embedding vector for *text*.

        Returns an empty list on any error.
        """
        if self._init_error or self._genai is None:
            return []

        try:
            return self._embed_with_retry(text)
        except Exception:
            return []

    @_RETRY_DECORATOR
    def _embed_with_retry(self, text: str) -> list[float]:
        result = self._genai.embed_content(
            model=self.model_name,
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]
