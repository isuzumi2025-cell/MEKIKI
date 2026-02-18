/**
 * nano-banana-strategy.ts
 *
 * Nano Banana (Gemini Flash Image) / Imagen 画像生成ストラテジー。
 * ImageGenClient をラップし、GenerationStrategy インターフェースで統一的にアクセス可能にする。
 */

import {
  GenerationStrategy,
  type GenerationContext,
  type GenerationResult,
  type GenerationInputType,
} from "./generation-strategy.js";
import {
  ImageGenClient,
  type ImageModel,
  type ImageAspectRatio,
} from "../image-gen-client.js";

export class NanoBananaStrategy extends GenerationStrategy {
  readonly name = "NanoBananaStrategy";
  readonly description =
    "Gemini Flash Image (Nano Banana) / Imagen 3 による画像生成";
  readonly supportedInputTypes: readonly GenerationInputType[] = [
    "text",
  ] as const;

  private client: ImageGenClient;

  constructor(options?: { apiKey?: string; defaultModel?: ImageModel }) {
    super();
    this.client = new ImageGenClient(options);
  }

  canHandle(context: GenerationContext): boolean {
    return context.inputType === "text";
  }

  async execute(context: GenerationContext): Promise<GenerationResult> {
    this.validateContext(context);

    const aspectRatio = this.resolveAspectRatio(context.aspectRatio);

    const result = await this.client.generateImage({
      prompt: context.prompt,
      aspectRatio,
      negativePrompt: context.negativePrompt,
    });

    if (!result.success || result.images.length === 0) {
      return {
        success: false,
        outputType: "image",
        error: result.error ?? "画像が生成されませんでした",
        strategyName: this.name,
      };
    }

    const firstImage = result.images[0];

    return {
      success: true,
      outputType: "image",
      imageBytes: firstImage.imageBytes,
      imageMimeType: firstImage.mimeType,
      strategyName: this.name,
    };
  }

  private resolveAspectRatio(
    ratio?: string
  ): ImageAspectRatio | undefined {
    const validRatios: ImageAspectRatio[] = [
      "1:1",
      "16:9",
      "9:16",
      "4:3",
      "3:4",
    ];
    if (ratio && validRatios.includes(ratio as ImageAspectRatio)) {
      return ratio as ImageAspectRatio;
    }
    return undefined;
  }
}
