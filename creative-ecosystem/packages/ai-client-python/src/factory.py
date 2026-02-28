"""
ICC AI Client - Factory functions

Provides a single, stable entry-point for obtaining LLM and embedding clients
without coupling callers to concrete implementation modules.

Usage::

    from icc_ai_client import get_llm_client, get_embedding_client

    llm = get_llm_client("anthropic")
    resp = llm.generate("Hello, world!")

    embedder = get_embedding_client()
    vector = embedder.embed("Some text to embed")
"""

from __future__ import annotations

from typing import Literal, Optional

from .base import EmbeddingClient, LLMClient

ProviderType = Literal["gemini", "anthropic", "openai", "grok"]
EmbeddingProviderType = Literal["gemini"]


def get_llm_client(
    provider: ProviderType = "gemini",
    model: Optional[str] = None,
) -> LLMClient:
    """
    Return a fully-initialised LLM client for the requested *provider*.

    The client is returned even if the underlying API key is missing; in that
    case, every call to generate() / analyze() will return an LLMResponse with
    the error field set rather than raising an exception.

    Args:
        provider: One of ``"gemini"``, ``"anthropic"``, ``"openai"``, ``"grok"``.
                  Defaults to ``"gemini"``.
        model:    Optional model identifier override.  When omitted, the
                  provider's DEFAULT_MODEL is used.

    Returns:
        An LLMClient instance for the requested provider.

    Raises:
        ValueError: When *provider* is not one of the recognised values.

    Example::

        client = get_llm_client("anthropic", model="claude-opus-4-6")
        resp = client.generate("Summarise the ICC roadmap.")
    """
    if provider == "gemini":
        from .gemini import GeminiClient

        return GeminiClient(model=model or GeminiClient.DEFAULT_MODEL)

    if provider == "anthropic":
        from .anthropic import AnthropicClient

        return AnthropicClient(model=model or AnthropicClient.DEFAULT_MODEL)

    if provider == "openai":
        from .openai import OpenAIClient

        return OpenAIClient(model=model or OpenAIClient.DEFAULT_MODEL)

    if provider == "grok":
        from .grok import GrokClient

        return GrokClient(model=model or GrokClient.DEFAULT_MODEL)

    raise ValueError(
        f"Unknown provider {provider!r}. "
        f"Valid choices: 'gemini', 'anthropic', 'openai', 'grok'."
    )


def get_embedding_client(
    provider: EmbeddingProviderType = "gemini",
) -> EmbeddingClient:
    """
    Return a fully-initialised embedding client for the requested *provider*.

    Currently only ``"gemini"`` is supported (``models/text-embedding-004``).
    Additional providers can be added here without changing the public interface.

    Args:
        provider: Embedding provider name.  Currently only ``"gemini"``.

    Returns:
        An EmbeddingClient instance.

    Raises:
        ValueError: When *provider* is not one of the recognised values.

    Example::

        embedder = get_embedding_client()
        vector = embedder.embed("ICC creative ecosystem")
        print(len(vector))  # 768
    """
    if provider == "gemini":
        from .gemini import GeminiEmbeddingClient

        return GeminiEmbeddingClient()

    raise ValueError(
        f"Unknown embedding provider {provider!r}. Valid choices: 'gemini'."
    )
