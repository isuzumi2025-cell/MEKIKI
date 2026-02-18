/**
 * veo-strategy.ts
 *
 * Veo 動画生成ストラテジー。
 * VeoClient をラップし、GenerationStrategy インターフェースで統一的にアクセス可能にする。
 */

import {
  GenerationStrategy,
  type GenerationContext,
  type GenerationResult,
  type GenerationInputType,
} from "./generation-strategy.js";
import {
  VeoClient,
  type VeoModel,
  type VeoAspectRatio,
  type VeoGenerationResult,
} from "../veo-client.js";

export class VeoStrategy extends GenerationStrategy {
  readonly name = "VeoStrategy";
  readonly description = "Google Veo 3.1 によるテキスト/画像→動画生成";
  readonly supportedInputTypes: readonly GenerationInputType[] = [
    "text",
    "text+image",
  ] as const;

  private client: VeoClient;

  constructor(options?: { apiKey?: string; defaultModel?: VeoModel }) {
    super();
    this.client = new VeoClient(options);
  }

  canHandle(context: GenerationContext): boolean {
    return this.supportedInputTypes.includes(context.inputType);
  }

  async execute(context: GenerationContext): Promise<GenerationResult> {
    this.validateContext(context);

    const aspectRatio = this.resolveAspectRatio(context.aspectRatio);

    let result: VeoGenerationResult;

    if (
      context.inputType === "text+image" &&
      context.imageBytes &&
      context.imageMimeType
    ) {
      result = await this.client.generateVideoFromImage(
        context.imageBytes,
        context.imageMimeType,
        context.prompt,
        {
          aspectRatio,
          negativePrompt: context.negativePrompt,
        }
      );
    } else {
      result = await this.client.generateVideo({
        prompt: context.prompt,
        aspectRatio,
        negativePrompt: context.negativePrompt,
      });
    }

    return {
      success: result.status === "completed",
      outputType: "video",
      videoUri: result.videoUri,
      videoFile: result.videoFile,
      error: result.error,
      strategyName: this.name,
    };
  }

  private resolveAspectRatio(
    ratio?: string
  ): VeoAspectRatio | undefined {
    if (ratio === "16:9" || ratio === "9:16") {
      return ratio;
    }
    return undefined;
  }
}
