"""
Unit tests for icc-ai-client.

All external API calls are mocked so these tests run without real credentials
or network access.

Test groups:
  - LLMResponse dataclass behaviour
  - GeminiClient (generate, analyze, image support, error path)
  - GeminiEmbeddingClient
  - AnthropicClient (generate, system prompt, error path)
  - OpenAIClient (generate, vision, error path)
  - GrokClient (generate, error path)
  - Factory (get_llm_client, get_embedding_client, invalid provider)
  - Missing API key handling
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the package src directory is importable when running from repo root.
# ---------------------------------------------------------------------------

_SRC = str(
    __import__("pathlib").Path(__file__).parent.parent / "src"
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from base import EmbeddingClient, LLMClient, LLMResponse  # noqa: E402
from factory import get_embedding_client, get_llm_client  # noqa: E402


# ===========================================================================
# Helpers
# ===========================================================================


def _fake_genai_model(text: str = "Gemini reply") -> MagicMock:
    """Return a mock that behaves like a google.generativeai.GenerativeModel."""
    model = MagicMock()
    response = MagicMock()
    response.text = text
    response.usage_metadata.prompt_token_count = 10
    response.usage_metadata.candidates_token_count = 20
    model.generate_content.return_value = response
    return model


def _fake_openai_completion(text: str, total_tokens: int = 30) -> MagicMock:
    """Return a mock resembling openai.types.chat.ChatCompletion."""
    completion = MagicMock()
    completion.choices[0].message.content = text
    completion.usage.total_tokens = total_tokens
    return completion


def _fake_anthropic_message(text: str, input_tok: int = 5, output_tok: int = 15) -> MagicMock:
    """Return a mock resembling anthropic.types.Message."""
    block = SimpleNamespace(text=text)
    msg = MagicMock()
    msg.content = [block]
    msg.usage.input_tokens = input_tok
    msg.usage.output_tokens = output_tok
    return msg


# ===========================================================================
# LLMResponse
# ===========================================================================


class TestLLMResponse:
    def test_ok_true_when_text_and_no_error(self):
        r = LLMResponse(text="hello", model="test-model")
        assert r.ok is True

    def test_ok_false_when_error_set(self):
        r = LLMResponse(text="hello", model="test-model", error="something failed")
        assert r.ok is False

    def test_ok_false_when_text_empty(self):
        r = LLMResponse(text="", model="test-model")
        assert r.ok is False

    def test_defaults(self):
        r = LLMResponse(text="x", model="m")
        assert r.tokens_used == 0
        assert r.error is None
        assert r.latency_ms == -1.0

    def test_latency_ms_stored(self):
        r = LLMResponse(text="x", model="m", latency_ms=123.4)
        assert r.latency_ms == pytest.approx(123.4)


# ===========================================================================
# GeminiClient
# ===========================================================================


class TestGeminiClient:
    """Tests for GeminiClient using mocked google.generativeai."""

    def _make_client(self, model_mock: MagicMock) -> Any:
        """Patch genai and env, return an initialised GeminiClient."""
        from gemini import GeminiClient

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}),
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel", return_value=model_mock),
        ):
            client = GeminiClient()

        # Inject the mock model directly so generate() can use it.
        client._model = model_mock
        client._init_error = None
        return client

    def test_generate_returns_llmresponse(self):
        model_mock = _fake_genai_model("Hello from Gemini")
        client = self._make_client(model_mock)
        resp = client.generate("Say hello")
        assert isinstance(resp, LLMResponse)
        assert resp.text == "Hello from Gemini"
        assert resp.model == "gemini-2.0-flash"
        assert resp.error is None
        assert resp.latency_ms >= 0

    def test_generate_tokens_used(self):
        model_mock = _fake_genai_model()
        client = self._make_client(model_mock)
        resp = client.generate("Count tokens")
        assert resp.tokens_used == 30  # 10 + 20

    def test_analyze_delegates_to_generate(self):
        model_mock = _fake_genai_model("Analysis result")
        client = self._make_client(model_mock)
        resp = client.analyze("some text", "summarise this")
        assert resp.text == "Analysis result"
        # Verify the combined prompt was passed to the model
        call_args = model_mock.generate_content.call_args[0][0]
        assert "summarise this" in call_args[0]
        assert "some text" in call_args[0]

    def test_generate_with_images(self):
        model_mock = _fake_genai_model("Vision reply")
        client = self._make_client(model_mock)
        # Pass a dummy base64 string (1x1 white PNG)
        import base64
        tiny_png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        resp = client.generate("Describe this image", images=[tiny_png_b64])
        assert resp.text == "Vision reply"

    def test_generate_error_when_no_api_key(self):
        from gemini import GeminiClient

        with patch.dict(os.environ, {}, clear=True):
            # Ensure the env var is absent
            os.environ.pop("GEMINI_API_KEY", None)
            client = GeminiClient()

        resp = client.generate("Hello")
        assert resp.error is not None
        assert resp.text == ""
        assert resp.ok is False

    def test_generate_error_on_api_failure(self):
        model_mock = MagicMock()
        model_mock.generate_content.side_effect = RuntimeError("API timeout")
        client = self._make_client(model_mock)
        resp = client.generate("Trigger error")
        assert resp.error is not None
        assert "API timeout" in resp.error
        assert resp.text == ""


# ===========================================================================
# GeminiEmbeddingClient
# ===========================================================================


class TestGeminiEmbeddingClient:
    def test_embed_returns_floats(self):
        from gemini import GeminiEmbeddingClient

        fake_genai = MagicMock()
        fake_genai.embed_content.return_value = {"embedding": [0.1, 0.2, 0.3]}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}):
            client = GeminiEmbeddingClient()
        client._genai = fake_genai
        client._init_error = None

        result = client.embed("hello world")
        assert result == [0.1, 0.2, 0.3]

    def test_embed_returns_empty_list_on_missing_key(self):
        from gemini import GeminiEmbeddingClient

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GEMINI_API_KEY", None)
            client = GeminiEmbeddingClient()

        result = client.embed("hello")
        assert result == []

    def test_embed_returns_empty_list_on_api_error(self):
        from gemini import GeminiEmbeddingClient

        fake_genai = MagicMock()
        fake_genai.embed_content.side_effect = RuntimeError("network error")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}):
            client = GeminiEmbeddingClient()
        client._genai = fake_genai
        client._init_error = None

        result = client.embed("hello")
        assert result == []


# ===========================================================================
# AnthropicClient
# ===========================================================================


class TestAnthropicClient:
    def _make_client(self) -> Any:
        from anthropic import AnthropicClient

        mock_anthropic_sdk = MagicMock()
        mock_client = MagicMock()
        mock_anthropic_sdk.Anthropic.return_value = mock_client

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key"}),
            patch.dict("sys.modules", {"anthropic": mock_anthropic_sdk}),
        ):
            client = AnthropicClient()

        client._client = mock_client
        client._init_error = None
        return client, mock_client

    def test_generate_returns_llmresponse(self):
        client, mock_sdk_client = self._make_client()
        mock_sdk_client.messages.create.return_value = _fake_anthropic_message(
            "Claude reply"
        )
        resp = client.generate("Hello Claude")
        assert isinstance(resp, LLMResponse)
        assert resp.text == "Claude reply"
        assert resp.error is None
        assert resp.latency_ms >= 0

    def test_generate_tokens_used(self):
        client, mock_sdk_client = self._make_client()
        mock_sdk_client.messages.create.return_value = _fake_anthropic_message(
            "reply", input_tok=10, output_tok=20
        )
        resp = client.generate("Count tokens")
        assert resp.tokens_used == 30

    def test_generate_with_system_prompt(self):
        client, mock_sdk_client = self._make_client()
        mock_sdk_client.messages.create.return_value = _fake_anthropic_message("ok")
        client.generate("Hello", system="You are helpful")
        create_call = mock_sdk_client.messages.create.call_args
        assert create_call.kwargs.get("system") == "You are helpful"

    def test_generate_no_system_when_not_provided(self):
        client, mock_sdk_client = self._make_client()
        mock_sdk_client.messages.create.return_value = _fake_anthropic_message("ok")
        client.generate("Hello")
        create_call = mock_sdk_client.messages.create.call_args
        assert "system" not in create_call.kwargs

    def test_analyze_builds_combined_prompt(self):
        client, mock_sdk_client = self._make_client()
        mock_sdk_client.messages.create.return_value = _fake_anthropic_message("result")
        resp = client.analyze("my text", "summarise it")
        assert resp.text == "result"
        msg_content = mock_sdk_client.messages.create.call_args.kwargs["messages"][0][
            "content"
        ]
        assert "summarise it" in msg_content
        assert "my text" in msg_content

    def test_error_when_api_key_missing(self):
        from anthropic import AnthropicClient

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            client = AnthropicClient()

        resp = client.generate("hi")
        assert resp.error is not None
        assert resp.ok is False

    def test_error_on_api_failure(self):
        client, mock_sdk_client = self._make_client()
        mock_sdk_client.messages.create.side_effect = RuntimeError("overloaded")
        resp = client.generate("hi")
        assert "overloaded" in resp.error
        assert resp.text == ""


# ===========================================================================
# OpenAIClient
# ===========================================================================


class TestOpenAIClient:
    def _make_client(self) -> Any:
        from openai import OpenAIClient

        mock_openai_sdk = MagicMock()
        mock_sdk_client = MagicMock()
        mock_openai_sdk.OpenAI.return_value = mock_sdk_client

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}),
            patch.dict("sys.modules", {"openai": mock_openai_sdk}),
        ):
            client = OpenAIClient()

        client._client = mock_sdk_client
        client._init_error = None
        return client, mock_sdk_client

    def test_generate_returns_llmresponse(self):
        client, mock_sdk = self._make_client()
        mock_sdk.chat.completions.create.return_value = _fake_openai_completion(
            "OpenAI reply"
        )
        resp = client.generate("Hello GPT")
        assert isinstance(resp, LLMResponse)
        assert resp.text == "OpenAI reply"
        assert resp.error is None

    def test_generate_tokens_used(self):
        client, mock_sdk = self._make_client()
        mock_sdk.chat.completions.create.return_value = _fake_openai_completion(
            "reply", total_tokens=42
        )
        resp = client.generate("tokens?")
        assert resp.tokens_used == 42

    def test_generate_with_images_builds_vision_payload(self):
        client, mock_sdk = self._make_client()
        mock_sdk.chat.completions.create.return_value = _fake_openai_completion(
            "vision reply"
        )
        resp = client.generate("Describe", images=["base64data=="])
        assert resp.text == "vision reply"
        call_kwargs = mock_sdk.chat.completions.create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        # Should be a list with text + image_url parts
        assert isinstance(content, list)
        types = [item["type"] for item in content]
        assert "text" in types
        assert "image_url" in types

    def test_error_when_api_key_missing(self):
        from openai import OpenAIClient

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            client = OpenAIClient()

        resp = client.generate("hi")
        assert resp.error is not None
        assert resp.ok is False

    def test_error_on_api_failure(self):
        client, mock_sdk = self._make_client()
        mock_sdk.chat.completions.create.side_effect = RuntimeError("rate limited")
        resp = client.generate("hi")
        assert "rate limited" in resp.error


# ===========================================================================
# GrokClient
# ===========================================================================


class TestGrokClient:
    def _make_client(self) -> Any:
        from grok import GrokClient

        mock_openai_sdk = MagicMock()
        mock_sdk_client = MagicMock()
        mock_openai_sdk.OpenAI.return_value = mock_sdk_client

        with (
            patch.dict(os.environ, {"GROK_API_KEY": "fake-key"}),
            patch.dict("sys.modules", {"openai": mock_openai_sdk}),
        ):
            client = GrokClient()

        client._client = mock_sdk_client
        client._init_error = None
        return client, mock_sdk_client

    def test_generate_returns_llmresponse(self):
        client, mock_sdk = self._make_client()
        mock_sdk.chat.completions.create.return_value = _fake_openai_completion(
            "Grok reply"
        )
        resp = client.generate("Hello Grok")
        assert isinstance(resp, LLMResponse)
        assert resp.text == "Grok reply"
        assert resp.error is None

    def test_xai_base_url_is_used(self):
        from grok import GrokClient, _XAI_BASE_URL

        mock_openai_sdk = MagicMock()
        mock_openai_sdk.OpenAI.return_value = MagicMock()

        with (
            patch.dict(os.environ, {"GROK_API_KEY": "fake-key"}),
            patch.dict("sys.modules", {"openai": mock_openai_sdk}),
        ):
            GrokClient()

        call_kwargs = mock_openai_sdk.OpenAI.call_args.kwargs
        assert call_kwargs["base_url"] == _XAI_BASE_URL

    def test_analyze_builds_combined_prompt(self):
        client, mock_sdk = self._make_client()
        mock_sdk.chat.completions.create.return_value = _fake_openai_completion("done")
        client.analyze("source text", "rewrite this")
        msg_content = mock_sdk.chat.completions.create.call_args.kwargs["messages"][0][
            "content"
        ]
        assert "rewrite this" in msg_content
        assert "source text" in msg_content

    def test_error_when_api_key_missing(self):
        from grok import GrokClient

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GROK_API_KEY", None)
            client = GrokClient()

        resp = client.generate("hi")
        assert resp.error is not None
        assert resp.ok is False

    def test_error_on_api_failure(self):
        client, mock_sdk = self._make_client()
        mock_sdk.chat.completions.create.side_effect = RuntimeError("network error")
        resp = client.generate("hi")
        assert "network error" in resp.error


# ===========================================================================
# Factory
# ===========================================================================


class TestFactory:
    """Tests for get_llm_client and get_embedding_client."""

    def _patch_all_sdks(self):
        """Context manager that stubs all third-party SDK imports."""
        return patch.dict(
            "sys.modules",
            {
                "google": MagicMock(),
                "google.generativeai": MagicMock(),
                "anthropic": MagicMock(),
                "openai": MagicMock(),
            },
        )

    def test_get_llm_client_gemini(self):
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "k"}),
            self._patch_all_sdks(),
        ):
            client = get_llm_client("gemini")
        from gemini import GeminiClient

        assert isinstance(client, GeminiClient)

    def test_get_llm_client_anthropic(self):
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}),
            self._patch_all_sdks(),
        ):
            client = get_llm_client("anthropic")
        from anthropic import AnthropicClient

        assert isinstance(client, AnthropicClient)

    def test_get_llm_client_openai(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "k"}),
            self._patch_all_sdks(),
        ):
            client = get_llm_client("openai")
        from openai import OpenAIClient

        assert isinstance(client, OpenAIClient)

    def test_get_llm_client_grok(self):
        with (
            patch.dict(os.environ, {"GROK_API_KEY": "k"}),
            self._patch_all_sdks(),
        ):
            client = get_llm_client("grok")
        from grok import GrokClient

        assert isinstance(client, GrokClient)

    def test_get_llm_client_model_override(self):
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "k"}),
            self._patch_all_sdks(),
        ):
            client = get_llm_client("gemini", model="gemini-2.5-pro")
        assert client.model_name == "gemini-2.5-pro"

    def test_get_llm_client_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_llm_client("nonexistent")  # type: ignore[arg-type]

    def test_get_embedding_client_gemini(self):
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "k"}),
            self._patch_all_sdks(),
        ):
            client = get_embedding_client("gemini")
        from gemini import GeminiEmbeddingClient

        assert isinstance(client, GeminiEmbeddingClient)

    def test_get_embedding_client_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_client("openai")  # type: ignore[arg-type]

    def test_factory_default_provider_is_gemini(self):
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "k"}),
            self._patch_all_sdks(),
        ):
            client = get_llm_client()  # no provider arg
        from gemini import GeminiClient

        assert isinstance(client, GeminiClient)


# ===========================================================================
# LLMClient / EmbeddingClient abstract contract
# ===========================================================================


class TestAbstractClasses:
    """Verify that concrete implementations actually satisfy the ABCs."""

    def test_gemini_client_is_llm_client(self):
        from gemini import GeminiClient

        assert issubclass(GeminiClient, LLMClient)

    def test_anthropic_client_is_llm_client(self):
        from anthropic import AnthropicClient

        assert issubclass(AnthropicClient, LLMClient)

    def test_openai_client_is_llm_client(self):
        from openai import OpenAIClient

        assert issubclass(OpenAIClient, LLMClient)

    def test_grok_client_is_llm_client(self):
        from grok import GrokClient

        assert issubclass(GrokClient, LLMClient)

    def test_gemini_embedding_client_is_embedding_client(self):
        from gemini import GeminiEmbeddingClient

        assert issubclass(GeminiEmbeddingClient, EmbeddingClient)
