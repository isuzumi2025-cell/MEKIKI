import { GeminiClient, GeminiEmbeddingClient } from "./gemini.js";
import { AnthropicClient } from "./anthropic.js";
import { OpenAIClient } from "./openai.js";
import { GrokClient } from "./grok.js";
import type { LLMClient, EmbeddingClient, ProviderType } from "./types.js";

export function getLLMClient(
  provider: ProviderType = "gemini",
  model?: string
): LLMClient {
  switch (provider) {
    case "anthropic":
      return new AnthropicClient(model ?? "claude-sonnet-4-6");
    case "openai":
      return new OpenAIClient(model ?? "gpt-4o");
    case "grok":
      return new GrokClient(model ?? "grok-2");
    case "gemini":
    default:
      return new GeminiClient(model ?? "gemini-2.0-flash");
  }
}

export function getEmbeddingClient(
  provider: "gemini" = "gemini"
): EmbeddingClient {
  switch (provider) {
    case "gemini":
    default:
      return new GeminiEmbeddingClient();
  }
}
