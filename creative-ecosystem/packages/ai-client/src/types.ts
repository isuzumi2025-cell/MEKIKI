import { z } from "zod";

export const LLMResponseSchema = z.object({
  text: z.string(),
  model: z.string(),
  tokensUsed: z.number().default(0),
  latencyMs: z.number().default(0),
  error: z.string().nullable().default(null),
});
export type LLMResponse = z.infer<typeof LLMResponseSchema>;

export interface LLMMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface LLMClientOptions {
  model?: string;
  maxTokens?: number;
  temperature?: number;
  systemPrompt?: string;
}

export interface ImageInput {
  data: string; // base64
  mimeType: "image/png" | "image/jpeg" | "image/webp";
}

export interface LLMClient {
  readonly provider: string;
  readonly model: string;
  generate(
    prompt: string,
    options?: LLMClientOptions & { images?: ImageInput[] }
  ): Promise<LLMResponse>;
  analyze(text: string, instruction: string): Promise<LLMResponse>;
}

export interface EmbeddingClient {
  readonly provider: string;
  embed(text: string): Promise<number[]>;
  embedBatch(texts: string[]): Promise<number[][]>;
}

export type ProviderType = "gemini" | "anthropic" | "openai" | "grok";
