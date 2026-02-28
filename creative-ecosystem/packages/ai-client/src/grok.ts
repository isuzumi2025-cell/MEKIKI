import OpenAI from "openai";
import type { LLMClient, LLMResponse, LLMClientOptions } from "./types.js";

const GROK_BASE_URL = "https://api.x.ai/v1";
const GROK_MODEL_CANDIDATES = ["grok-2", "grok-3", "grok-3-mini", "grok-beta"];

export class GrokClient implements LLMClient {
  readonly provider = "grok";
  readonly model: string;
  private client: OpenAI | null = null;

  constructor(model = "grok-2") {
    this.model = model;
    const apiKey = process.env.GROK_API_KEY;
    if (!apiKey) {
      console.warn("⚠️ GROK_API_KEY not set");
      return;
    }
    this.client = new OpenAI({ apiKey, baseURL: GROK_BASE_URL });
  }

  async generate(
    prompt: string,
    options: LLMClientOptions = {}
  ): Promise<LLMResponse> {
    if (!this.client) {
      return { text: "", model: this.model, tokensUsed: 0, latencyMs: 0, error: "Client not initialized — check GROK_API_KEY" };
    }
    const start = Date.now();

    const candidates = [this.model, ...GROK_MODEL_CANDIDATES.filter((m) => m !== this.model)];
    for (const candidate of candidates) {
      try {
        const response = await this.client.chat.completions.create({
          model: candidate,
          max_tokens: options.maxTokens ?? 4096,
          messages: [
            ...(options.systemPrompt
              ? [{ role: "system" as const, content: options.systemPrompt }]
              : []),
            { role: "user" as const, content: prompt },
          ],
        });
        const text = response.choices[0]?.message?.content ?? "";
        return {
          text,
          model: candidate,
          tokensUsed: response.usage?.total_tokens ?? 0,
          latencyMs: Date.now() - start,
          error: null,
        };
      } catch (e) {
        const msg = String(e).toLowerCase();
        if (msg.includes("model not found") || msg.includes("unknown model")) {
          continue;
        }
        return { text: "", model: candidate, tokensUsed: 0, latencyMs: Date.now() - start, error: String(e) };
      }
    }
    return { text: "", model: this.model, tokensUsed: 0, latencyMs: Date.now() - start, error: "No available Grok model found" };
  }

  async analyze(text: string, instruction: string): Promise<LLMResponse> {
    return this.generate(`${instruction}\n\n${text}`);
  }
}
