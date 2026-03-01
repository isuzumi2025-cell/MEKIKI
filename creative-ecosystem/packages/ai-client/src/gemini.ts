import {
  GoogleGenerativeAI,
  GenerativeModel,
  Part,
} from "@google/generative-ai";
import type { LLMClient, LLMResponse, LLMClientOptions, ImageInput, EmbeddingClient } from "./types.js";

export class GeminiClient implements LLMClient {
  readonly provider = "gemini";
  readonly model: string;
  private client: GenerativeModel | null = null;
  private genAI: GoogleGenerativeAI | null = null;

  constructor(model = "gemini-2.0-flash") {
    this.model = model;
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      console.warn("⚠️ GEMINI_API_KEY not set");
      return;
    }
    this.genAI = new GoogleGenerativeAI(apiKey);
    this.client = this.genAI.getGenerativeModel({ model });
  }

  async generate(
    prompt: string,
    options: LLMClientOptions & { images?: ImageInput[] } = {}
  ): Promise<LLMResponse> {
    if (!this.client) {
      return { text: "", model: this.model, tokensUsed: 0, latencyMs: 0, error: "Client not initialized — check GEMINI_API_KEY" };
    }
    const start = Date.now();
    try {
      const parts: Part[] = [{ text: prompt }];
      if (options.images) {
        for (const img of options.images) {
          parts.push({ inlineData: { mimeType: img.mimeType, data: img.data } });
        }
      }
      const result = await this.client.generateContent(parts);
      const text = result.response.text();
      return {
        text,
        model: this.model,
        tokensUsed: result.response.usageMetadata?.totalTokenCount ?? 0,
        latencyMs: Date.now() - start,
        error: null,
      };
    } catch (e) {
      return { text: "", model: this.model, tokensUsed: 0, latencyMs: Date.now() - start, error: String(e) };
    }
  }

  async analyze(text: string, instruction: string): Promise<LLMResponse> {
    return this.generate(`${instruction}\n\nTarget Text:\n${text}`);
  }
}

export class GeminiEmbeddingClient implements EmbeddingClient {
  readonly provider = "gemini";
  private genAI: GoogleGenerativeAI | null = null;
  private static readonly EMBEDDING_MODEL = "models/text-embedding-004";

  constructor() {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      console.warn("⚠️ GEMINI_API_KEY not set — embedding unavailable");
      return;
    }
    this.genAI = new GoogleGenerativeAI(apiKey);
  }

  async embed(text: string): Promise<number[]> {
    if (!this.genAI) return [];
    const model = this.genAI.getGenerativeModel({ model: GeminiEmbeddingClient.EMBEDDING_MODEL });
    const result = await model.embedContent(text);
    return result.embedding.values;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    return Promise.all(texts.map((t) => this.embed(t)));
  }
}
