/**
 * generation-strategy.ts
 *
 * 生成戦略の抽象基底クラス。
 * 各生成クライアント（Veo, NanoBanana/Imagen）を統一的に扱うための
 * ストラテジーパターンのインターフェースを定義する。
 */

export type GenerationInputType = "text" | "image" | "text+image";

export interface GenerationContext {
  prompt: string;
  inputType: GenerationInputType;
  imageBytes?: string;
  imageMimeType?: string;
  aspectRatio?: string;
  negativePrompt?: string;
  additionalOptions?: Record<string, unknown>;
}

export interface GenerationResult {
  success: boolean;
  outputType: "video" | "image";
  videoUri?: string;
  videoFile?: unknown;
  imageBytes?: string;
  imageMimeType?: string;
  error?: string;
  strategyName: string;
}

export abstract class GenerationStrategy {
  abstract readonly name: string;
  abstract readonly description: string;
  abstract readonly supportedInputTypes: readonly GenerationInputType[];

  abstract execute(context: GenerationContext): Promise<GenerationResult>;

  abstract canHandle(context: GenerationContext): boolean;

  validateContext(context: GenerationContext): void {
    if (!context.prompt || context.prompt.trim().length === 0) {
      throw new Error(
        `[${this.name}] prompt は必須です。空のプロンプトは指定できません。`
      );
    }

    if (
      (context.inputType === "image" ||
        context.inputType === "text+image") &&
      !context.imageBytes
    ) {
      throw new Error(
        `[${this.name}] inputType が "${context.inputType}" の場合、imageBytes は必須です。`
      );
    }

    if (!this.supportedInputTypes.includes(context.inputType)) {
      throw new Error(
        `[${this.name}] inputType "${context.inputType}" はサポートされていません。` +
          `対応: ${this.supportedInputTypes.join(", ")}`
      );
    }
  }
}
