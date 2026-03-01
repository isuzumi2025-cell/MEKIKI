import OpenAI from "openai";
import type { LLMClient, LLMResponse, LLMClientOptions, ImageInput } from "./types.js";

export class OpenAIClient implements LLMClient {
  readonly provider = "openai";
  readonly model: string;
  private client: OpenAI | null = null;

  constructor(model = "gpt-4o") {
    this.model = model;
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      console.warn("⚠️ OPENAI_API_KEY not set");
      return;
    }
    this.client = new OpenAI({ apiKey });
  }

  async generate(
    prompt: string,
    options: LLMClientOptions & { images?: ImageInput[] } = {}
  ): Promise<LLMResponse> {
    if (!this.client) {
      return { text: "", model: this.model, tokensUsed: 0, latencyMs: 0, error: "Client not initialized — check OPENAI_API_KEY" };
    }
    const start = Date.now();
    try {
      type ContentPart =
        | { type: "text"; text: string }
        | { type: "image_url"; image_url: { url: string } };

      const content: ContentPart[] = [{ type: "text", text: prompt }];
      if (options.images) {
        for (const img of options.images) {
          content.push({
            type: "image_url",
            image_url: { url: `data:${img.mimeType};base64,${img.data}` },
          });
        }
      }

      const response = await this.client.chat.completions.create({
        model: this.model,
        max_tokens: options.maxTokens ?? 4096,
        messages: [
          ...(options.systemPrompt
            ? [{ role: "system" as const, content: options.systemPrompt }]
            : []),
          { role: "user" as const, content: options.images ? content : prompt },
        ],
      });

      const text = response.choices[0]?.message?.content ?? "";
      return {
        text,
        model: this.model,
        tokensUsed: response.usage?.total_tokens ?? 0,
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
