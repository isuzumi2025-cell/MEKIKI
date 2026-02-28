import Anthropic from "@anthropic-ai/sdk";
import type { LLMClient, LLMResponse, LLMClientOptions } from "./types.js";

export class AnthropicClient implements LLMClient {
  readonly provider = "anthropic";
  readonly model: string;
  private client: Anthropic | null = null;

  constructor(model = "claude-sonnet-4-6") {
    this.model = model;
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      console.warn("⚠️ ANTHROPIC_API_KEY not set");
      return;
    }
    this.client = new Anthropic({ apiKey });
  }

  async generate(
    prompt: string,
    options: LLMClientOptions = {}
  ): Promise<LLMResponse> {
    if (!this.client) {
      return { text: "", model: this.model, tokensUsed: 0, latencyMs: 0, error: "Client not initialized — check ANTHROPIC_API_KEY" };
    }
    const start = Date.now();
    try {
      const message = await this.client.messages.create({
        model: this.model,
        max_tokens: options.maxTokens ?? 4096,
        ...(options.systemPrompt ? { system: options.systemPrompt } : {}),
        messages: [{ role: "user", content: prompt }],
      });
      const text =
        message.content[0]?.type === "text" ? message.content[0].text : "";
      return {
        text,
        model: this.model,
        tokensUsed: (message.usage.input_tokens ?? 0) + (message.usage.output_tokens ?? 0),
        latencyMs: Date.now() - start,
        error: null,
      };
    } catch (e) {
      return { text: "", model: this.model, tokensUsed: 0, latencyMs: Date.now() - start, error: String(e) };
    }
  }

  async analyze(text: string, instruction: string): Promise<LLMResponse> {
    return this.generate(`${instruction}\n\n${text}`);
  }
}
