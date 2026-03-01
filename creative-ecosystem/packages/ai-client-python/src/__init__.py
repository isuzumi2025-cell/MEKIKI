"""
icc-ai-client
=============

Shared AI client package for the ICC monorepo.

Provides a unified interface to Gemini, Claude (Anthropic), OpenAI, and Grok,
with tenacity retries and graceful error handling (errors are returned as
LLMResponse.error strings rather than raised exceptions).

Quick start::

    from icc_ai_client import get_llm_client, get_embedding_client

    # Use the factory (recommended)
    llm = get_llm_client("gemini")
    resp = llm.generate("Hello, ICC!")
    print(resp.text, resp.latency_ms)

    # Or instantiate directly
    from icc_ai_client import AnthropicClient
    client = AnthropicClient(model="claude-opus-4-6")
    resp = client.generate("Explain embeddings.", system="Be concise.")
"""

from .anthropic import AnthropicClient
from .base import EmbeddingClient, LLMClient, LLMResponse
from .factory import EmbeddingProviderType, ProviderType, get_embedding_client, get_llm_client
from .gemini import GeminiClient, GeminiEmbeddingClient
from .grok import GrokClient
from .openai import OpenAIClient

__version__ = "0.1.0"

__all__ = [
    # Base abstractions
    "LLMClient",
    "LLMResponse",
    "EmbeddingClient",
    # Concrete clients
    "GeminiClient",
    "GeminiEmbeddingClient",
    "AnthropicClient",
    "OpenAIClient",
    "GrokClient",
    # Factory helpers
    "get_llm_client",
    "get_embedding_client",
    # Type aliases
    "ProviderType",
    "EmbeddingProviderType",
    # Package metadata
    "__version__",
]
