"""
ICC AI Client - Abstract Base Classes

Defines the shared contract for all LLM and embedding clients in the ICC monorepo.
All concrete implementations must conform to these interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    """
    Unified response object returned by all LLM clients.

    Fields:
        text:        Generated / returned text. Empty string on error.
        model:       The model identifier that produced the response (e.g. "gemini-2.0-flash").
        tokens_used: Total token count (input + output) when available; 0 if not reported.
        error:       Human-readable error message when the call failed; None on success.
        latency_ms:  Wall-clock time for the API call in milliseconds; -1 if not measured.
    """

    text: str
    model: str
    tokens_used: int = 0
    error: Optional[str] = None
    latency_ms: float = -1.0

    @property
    def ok(self) -> bool:
        """True when the response contains usable text and no error."""
        return self.error is None and bool(self.text)


class LLMClient(ABC):
    """
    Abstract base class for all large-language-model clients.

    Concrete implementations must:
    - Never raise exceptions from generate() / analyze(); instead return an
      LLMResponse with the error field populated.
    - Accept optional PIL Images or base64 strings in the images parameter
      (or silently ignore them when the underlying model does not support vision).
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        images: Optional[list[Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a text completion for *prompt*.

        Args:
            prompt: The user / instruction text to send to the model.
            images: Optional list of visual inputs.  Each element may be a
                    PIL.Image.Image instance or a base64-encoded PNG/JPEG string.
            **kwargs: Provider-specific overrides (e.g. ``system``, ``temperature``).

        Returns:
            LLMResponse with text and metadata.  On failure, text is empty and
            error describes the problem.
        """

    @abstractmethod
    def analyze(self, text: str, instruction: str) -> LLMResponse:
        """
        Convenience wrapper: apply *instruction* to *text*.

        Implementations typically build a combined prompt and delegate to generate().

        Args:
            text:        The source material to analyse.
            instruction: What the model should do with the text.

        Returns:
            LLMResponse as described in generate().
        """


class EmbeddingClient(ABC):
    """
    Abstract base class for text embedding clients.

    Concrete implementations must:
    - Never raise exceptions; return an empty list on error and log the problem.
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Compute a dense vector representation of *text*.

        Args:
            text: The input string to embed.

        Returns:
            A list of floats (the embedding vector).  Returns an empty list on
            failure.
        """
