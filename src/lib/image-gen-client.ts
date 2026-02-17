/**
 * image-gen-client.ts
 *
 * Gemini Imagen 3 画像生成クライアント SDK
 * テキストから画像を生成、または既存画像を編集する。
 * Midjourney の代替として Google エコシステム内で完結。
 *
 * @see https://ai.google.dev/gemini-api/docs/image-generation
 */

import { GoogleGenAI, type Part } from "@google/genai";
import { hasInlineImageData } from "./types/google-genai-extended.js";
import { withRetry } from "./utils/retry.js";

export type ImageModel =
  | "gemini-2.5-flash-image"
  | "imagen-3.0-generate-002";

export type ImageAspectRatio = "1:1" | "16:9" | "9:16" | "4:3" | "3:4";

export interface GenerateImageOptions {
  prompt: string;
  model?: ImageModel;
  aspectRatio?: ImageAspectRatio;
  negativePrompt?: string;
  numberOfImages?: number;
}

export interface GeneratedImage {
  imageBytes: string;
  mimeType: string;
}

export interface ImageGenerationResult {
  success: boolean;
  images: GeneratedImage[];
  error?: string;
}

export class ImageGenClient {
  private ai: GoogleGenAI;
  private defaultModel: ImageModel;

  constructor(options?: { apiKey?: string; defaultModel?: ImageModel }) {
    const apiKey =
      options?.apiKey ??
      (typeof process !== "undefined"
        ? process.env.GEMINI_API_KEY ?? ""
        : "");

    if (!apiKey) {
      throw new Error(
        "[ImageGenClient] GEMINI_API_KEY が設定されていません。" +
          ".env に GEMINI_API_KEY を追加してください。"
      );
    }

    this.ai = new GoogleGenAI({ apiKey });
    this.defaultModel = options?.defaultModel ?? "gemini-2.5-flash-image";
  }

  async generateImage(
    options: GenerateImageOptions
  ): Promise<ImageGenerationResult> {
    this.validateOptions(options);

    const model = options.model ?? this.defaultModel;

    try {
      if (model === "imagen-3.0-generate-002") {
        return await this.generateWithImagen(options);
      }
      return await this.generateWithGemini(options, model);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return {
        success: false,
        images: [],
        error: message,
      };
    }
  }

  private async generateWithGemini(
    options: GenerateImageOptions,
    model: string
  ): Promise<ImageGenerationResult> {
    try {
      const response = await withRetry(() =>
        this.ai.models.generateContent({
          model,
          contents: options.prompt,
          config: {
            responseModalities: ["IMAGE"],
          },
        })
      );

      const images: GeneratedImage[] = [];

      if (response.candidates?.[0]?.content?.parts) {
        for (const part of response.candidates[0].content.parts) {
          if (hasInlineImageData(part as Part)) {
            const typedPart = part as Part & {
              inlineData: { data: string; mimeType: string };
            };
            images.push({
              imageBytes: typedPart.inlineData.data,
              mimeType: typedPart.inlineData.mimeType,
            });
          }
        }
      }

      if (images.length === 0) {
        return {
          success: false,
          images: [],
          error: "画像が生成されませんでした",
        };
      }

      return { success: true, images };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { success: false, images: [], error: message };
    }
  }

  private async generateWithImagen(
    options: GenerateImageOptions
  ): Promise<ImageGenerationResult> {
    try {
      if (typeof this.ai.models.generateImages !== "function") {
        throw new Error(
          "[ImageGenClient] models.generateImages メソッドが利用できません。SDK バージョンを確認してください。"
        );
      }

      const response = await withRetry(() =>
        this.ai.models.generateImages({
          model: options.model ?? "imagen-3.0-generate-002",
          prompt: options.prompt,
          config: {
            numberOfImages: options.numberOfImages ?? 1,
            aspectRatio: options.aspectRatio,
            negativePrompt: options.negativePrompt,
          },
        })
      );

      const images: GeneratedImage[] = [];

      if (response.generatedImages) {
        for (const img of response.generatedImages) {
          if (img.image?.imageBytes) {
            images.push({
              imageBytes: img.image.imageBytes,
              mimeType: img.image.mimeType ?? "image/png",
            });
          }
        }
      }

      if (images.length === 0) {
        return {
          success: false,
          images: [],
          error: "Imagen で画像が生成されませんでした",
        };
      }

      return { success: true, images };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { success: false, images: [], error: message };
    }
  }

  async generateStartFrame(
    prompt: string,
    aspectRatio: ImageAspectRatio = "16:9"
  ): Promise<GeneratedImage | null> {
    const result = await this.generateImage({
      prompt,
      aspectRatio,
      model: "gemini-2.5-flash-image",
    });

    return result.success && result.images.length > 0
      ? result.images[0]
      : null;
  }

  private validateOptions(options: GenerateImageOptions): void {
    if (!options.prompt || options.prompt.trim().length === 0) {
      throw new Error(
        "[ImageGenClient] prompt は必須です。空のプロンプトは指定できません。"
      );
    }
  }
}
