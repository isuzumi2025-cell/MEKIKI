/**
 * artmotion-forge.ts
 *
 * ArtMotion Forge — イラスト生成 → アニメーション化パイプライン
 *
 * Imagen 3 / Gemini Flash でイラストを生成し、
 * Veo 3.1 で高品質アニメーション動画に変換する統合パイプライン。
 *
 * 機能:
 * - エラーリカバリ (フォールバックモデル)
 * - LRU キャッシュ (同一リクエスト最適化)
 * - バッチ生成 (複数シーン一括処理)
 * - 進捗コールバック (onProgress)
 * - AbortSignal 対応
 *
 * @see docs/flowforge_artmotion_spec.md
 *
 * FlowForge SDK — ArtMotion Layer
 */

import { z } from "zod";
import {
  ImageGenClient,
  type GeneratedImage,
  type ImageModel,
  type ImageAspectRatio,
} from "./image-gen-client.js";
import {
  VeoClient,
  type VeoGenerationResult,
  type VeoModel,
  type VeoAspectRatio,
  type VeoReferenceImage,
} from "./veo-client.js";
import { LRUCache } from "./resilience.js";
import { createLogger } from "./logger.js";

const logger = createLogger("artmotion-forge");

// ============================================================
// Zod スキーマ & 型定義
// ============================================================

const ArtMotionStyleSchema = z.enum([
  "illustration",
  "watercolor",
  "anime",
  "photorealistic",
  "flat_design",
  "custom",
]);
export type ArtMotionStyle = z.infer<typeof ArtMotionStyleSchema>;

const ArtMotionStatusSchema = z.enum(["completed", "partial", "failed"]);
export type ArtMotionStatus = z.infer<typeof ArtMotionStatusSchema>;

const ArtMotionGenerateOptionsSchema = z.object({
  prompt: z.string().min(1, "プロンプトは必須です"),
  style: ArtMotionStyleSchema.optional(),
  aspectRatio: z.string().optional(),
  resolution: z.enum(["720p", "1080p", "4k"]).optional(),
  imageModel: z
    .enum(["gemini-2.5-flash-image", "imagen-3.0-generate-002"])
    .optional(),
  videoModel: z
    .enum([
      "veo-3.1-generate-preview",
      "veo-3.1-fast-generate-preview",
      "veo-2-generate-001",
    ])
    .optional(),
  negativePrompt: z.string().optional(),
  skipAnimation: z.boolean().optional(),
  stylePromptOverride: z.string().optional(),
});

export interface ArtMotionGenerateOptions {
  prompt: string;
  style?: ArtMotionStyle;
  aspectRatio?: string;
  resolution?: "720p" | "1080p" | "4k";
  imageModel?: ImageModel;
  videoModel?: VeoModel;
  negativePrompt?: string;
  referenceImages?: VeoReferenceImage[];
  skipAnimation?: boolean;
  signal?: AbortSignal;
  onProgress?: ArtMotionProgressCallback;
  stylePromptOverride?: string;
}

export interface ArtMotionResult {
  status: ArtMotionStatus;
  illustration: GeneratedImage | null;
  animation: VeoGenerationResult | null;
  prompt: string;
  cached: boolean;
  durationMs: number;
  error?: string;
}

export type ArtMotionProgressStep =
  | "started"
  | "generating_illustration"
  | "illustration_complete"
  | "illustration_fallback"
  | "generating_animation"
  | "animation_complete"
  | "cache_hit"
  | "completed"
  | "failed";

export type ArtMotionProgressCallback = (
  step: ArtMotionProgressStep,
  message: string,
  progress?: number
) => void;

export interface ArtMotionForgeOptions {
  apiKey?: string;
  defaultImageModel?: ImageModel;
  defaultVideoModel?: VeoModel;
  cacheCapacity?: number;
}

export interface ArtMotionBatchOptions {
  concurrency?: number;
  signal?: AbortSignal;
  onProgress?: (
    index: number,
    total: number,
    step: ArtMotionProgressStep,
    message: string
  ) => void;
}

export interface ArtMotionBatchResult {
  results: ArtMotionResult[];
  totalDurationMs: number;
  successCount: number;
  partialCount: number;
  failureCount: number;
}

// ============================================================
// スタイルプロンプト変換マッピング
// ============================================================

const STYLE_PROMPT_MAP: Record<ArtMotionStyle, string> = {
  illustration:
    "detailed digital illustration, clean lines, vibrant colors",
  watercolor:
    "watercolor painting, soft edges, translucent color washes, paper texture",
  anime:
    "anime style, cel-shaded, large expressive eyes, dynamic composition",
  photorealistic:
    "photorealistic, high detail, natural lighting, 8K quality",
  flat_design:
    "flat design, geometric shapes, bold solid colors, minimal shadows",
  custom: "",
};

// ============================================================
// Draft / Production モード定義
// ============================================================

interface ModeConfig {
  imageModel: ImageModel;
  videoModel: VeoModel;
}

const DRAFT_MODE: ModeConfig = {
  imageModel: "gemini-2.5-flash-image",
  videoModel: "veo-3.1-fast-generate-preview",
};

const PRODUCTION_MODE: ModeConfig = {
  imageModel: "imagen-3.0-generate-002",
  videoModel: "veo-3.1-generate-preview",
};

// ============================================================
// ArtMotionForge 本体
// ============================================================

export class ArtMotionForge {
  private imageClient: ImageGenClient;
  private veoClient: VeoClient;
  private cache: LRUCache<string, ArtMotionResult>;
  private defaultImageModel: ImageModel;
  private defaultVideoModel: VeoModel;

  constructor(options?: ArtMotionForgeOptions) {
    this.imageClient = new ImageGenClient({ apiKey: options?.apiKey });
    this.veoClient = new VeoClient({ apiKey: options?.apiKey });
    this.cache = new LRUCache<string, ArtMotionResult>(
      options?.cacheCapacity ?? 50
    );
    this.defaultImageModel =
      options?.defaultImageModel ?? PRODUCTION_MODE.imageModel;
    this.defaultVideoModel =
      options?.defaultVideoModel ?? PRODUCTION_MODE.videoModel;
  }

  // ============================================================
  // 単一生成
  // ============================================================

  async generate(options: ArtMotionGenerateOptions): Promise<ArtMotionResult> {
    const startTime = Date.now();

    const validation = ArtMotionGenerateOptionsSchema.safeParse(options);
    if (!validation.success) {
      return {
        status: "failed",
        illustration: null,
        animation: null,
        prompt: options.prompt ?? "",
        cached: false,
        durationMs: Date.now() - startTime,
        error: `バリデーションエラー: ${validation.error.message}`,
      };
    }

    if (options.signal?.aborted) {
      return {
        status: "failed",
        illustration: null,
        animation: null,
        prompt: options.prompt,
        cached: false,
        durationMs: Date.now() - startTime,
        error: "リクエストがキャンセルされました",
      };
    }

    const cacheKey = this.buildCacheKey(options);
    const cached = this.cache.get(cacheKey);
    if (cached) {
      options.onProgress?.("cache_hit", "キャッシュヒット");
      return {
        ...cached,
        cached: true,
        durationMs: Date.now() - startTime,
      };
    }

    options.onProgress?.("started", "生成を開始します");

    const fullPrompt = this.buildFullPrompt(options);

    const illustration = await this.generateIllustrationWithFallback(
      fullPrompt,
      options
    );

    if (!illustration) {
      const result: ArtMotionResult = {
        status: "failed",
        illustration: null,
        animation: null,
        prompt: fullPrompt,
        cached: false,
        durationMs: Date.now() - startTime,
        error: "イラスト生成に失敗しました (フォールバック含む全モデルで失敗)",
      };
      options.onProgress?.("failed", result.error!);
      return result;
    }

    options.onProgress?.("illustration_complete", "イラスト生成完了");

    if (options.skipAnimation) {
      const result: ArtMotionResult = {
        status: "completed",
        illustration,
        animation: null,
        prompt: fullPrompt,
        cached: false,
        durationMs: Date.now() - startTime,
      };
      this.cache.set(cacheKey, result);
      options.onProgress?.("completed", "完了 (アニメーションスキップ)");
      return result;
    }

    if (options.signal?.aborted) {
      return {
        status: "partial",
        illustration,
        animation: null,
        prompt: fullPrompt,
        cached: false,
        durationMs: Date.now() - startTime,
        error: "アニメーション生成前にキャンセルされました",
      };
    }

    options.onProgress?.("generating_animation", "アニメーション生成中...");

    const animation = await this.generateAnimation(
      illustration,
      fullPrompt,
      options
    );

    if (!animation || animation.status === "failed") {
      const result: ArtMotionResult = {
        status: "partial",
        illustration,
        animation,
        prompt: fullPrompt,
        cached: false,
        durationMs: Date.now() - startTime,
        error: `アニメーション生成に失敗: ${animation?.error ?? "不明なエラー"}`,
      };
      this.cache.set(cacheKey, result);
      options.onProgress?.("failed", result.error!);
      return result;
    }

    const result: ArtMotionResult = {
      status: "completed",
      illustration,
      animation,
      prompt: fullPrompt,
      cached: false,
      durationMs: Date.now() - startTime,
    };

    this.cache.set(cacheKey, result);
    options.onProgress?.("completed", "生成完了");
    return result;
  }

  // ============================================================
  // バッチ生成
  // ============================================================

  async generateBatch(
    requests: ArtMotionGenerateOptions[],
    batchOptions?: ArtMotionBatchOptions
  ): Promise<ArtMotionBatchResult> {
    const startTime = Date.now();
    const concurrency = Math.max(1, batchOptions?.concurrency ?? 1);
    const results: ArtMotionResult[] = [];
    const chunks = chunkArray(requests, concurrency);
    let processedCount = 0;

    for (const chunk of chunks) {
      if (batchOptions?.signal?.aborted) {
        for (let i = 0; i < chunk.length; i++) {
          results.push({
            status: "failed",
            illustration: null,
            animation: null,
            prompt: chunk[i].prompt,
            cached: false,
            durationMs: 0,
            error: "バッチ処理がキャンセルされました",
          });
        }
        processedCount += chunk.length;
        continue;
      }

      const chunkPromises = chunk.map((request, chunkIdx) => {
        const index = processedCount + chunkIdx;

        const wrappedOnProgress: ArtMotionProgressCallback = (
          step,
          message
        ) => {
          batchOptions?.onProgress?.(index, requests.length, step, message);
          request.onProgress?.(step, message);
        };

        return this.generate({
          ...request,
          signal: batchOptions?.signal ?? request.signal,
          onProgress: wrappedOnProgress,
        });
      });

      const chunkResults = await Promise.allSettled(chunkPromises);

      for (let i = 0; i < chunkResults.length; i++) {
        const settled = chunkResults[i];
        if (settled.status === "fulfilled") {
          results.push(settled.value);
        } else {
          results.push({
            status: "failed",
            illustration: null,
            animation: null,
            prompt: chunk[i].prompt,
            cached: false,
            durationMs: 0,
            error:
              settled.reason instanceof Error
                ? settled.reason.message
                : String(settled.reason),
          });
        }
      }

      processedCount += chunk.length;
    }

    return {
      results,
      totalDurationMs: Date.now() - startTime,
      successCount: results.filter((r) => r.status === "completed").length,
      partialCount: results.filter((r) => r.status === "partial").length,
      failureCount: results.filter((r) => r.status === "failed").length,
    };
  }

  // ============================================================
  // Draft / Production ヘルパー
  // ============================================================

  async generateDraft(
    options: Omit<
      ArtMotionGenerateOptions,
      "imageModel" | "videoModel" | "resolution"
    >
  ): Promise<ArtMotionResult> {
    return this.generate({
      ...options,
      imageModel: DRAFT_MODE.imageModel,
      videoModel: DRAFT_MODE.videoModel,
      resolution: "720p",
    });
  }

  async generateProduction(
    options: Omit<
      ArtMotionGenerateOptions,
      "imageModel" | "videoModel" | "resolution"
    >
  ): Promise<ArtMotionResult> {
    return this.generate({
      ...options,
      imageModel: PRODUCTION_MODE.imageModel,
      videoModel: PRODUCTION_MODE.videoModel,
      resolution: "1080p",
    });
  }

  // ============================================================
  // キャッシュ管理
  // ============================================================

  clearCache(): void {
    this.cache.clear();
  }

  get cacheSize(): number {
    return this.cache.size;
  }

  // ============================================================
  // 内部メソッド
  // ============================================================

  private async generateIllustrationWithFallback(
    prompt: string,
    options: ArtMotionGenerateOptions
  ): Promise<GeneratedImage | null> {
    const primaryModel = options.imageModel ?? this.defaultImageModel;
    const aspectRatio = (options.aspectRatio ?? "16:9") as ImageAspectRatio;

    options.onProgress?.(
      "generating_illustration",
      `イラスト生成中 (${primaryModel})...`
    );

    const primaryResult = await this.imageClient.generateImage({
      prompt,
      model: primaryModel,
      aspectRatio,
      negativePrompt: options.negativePrompt,
    });

    if (primaryResult.success && primaryResult.images.length > 0) {
      return primaryResult.images[0];
    }

    const fallbackModel: ImageModel =
      primaryModel === "imagen-3.0-generate-002"
        ? "gemini-2.5-flash-image"
        : "imagen-3.0-generate-002";

    logger.warn(
      { primaryModel, fallbackModel, error: primaryResult.error },
      "プライマリモデルでの生成失敗、フォールバック"
    );

    options.onProgress?.(
      "illustration_fallback",
      `フォールバック: ${fallbackModel} で再試行中...`
    );

    const fallbackResult = await this.imageClient.generateImage({
      prompt,
      model: fallbackModel,
      aspectRatio,
      negativePrompt: options.negativePrompt,
    });

    if (fallbackResult.success && fallbackResult.images.length > 0) {
      return fallbackResult.images[0];
    }

    logger.error(
      { primaryModel, fallbackModel, error: fallbackResult.error },
      "フォールバックモデルでも生成失敗"
    );

    return null;
  }

  private async generateAnimation(
    illustration: GeneratedImage,
    prompt: string,
    options: ArtMotionGenerateOptions
  ): Promise<VeoGenerationResult> {
    const videoModel = options.videoModel ?? this.defaultVideoModel;
    const aspectRatio = (options.aspectRatio ?? "16:9") as VeoAspectRatio;

    try {
      const result = await this.veoClient.generateVideoFromImage(
        illustration.imageBytes,
        illustration.mimeType,
        prompt,
        {
          model: videoModel,
          aspectRatio,
          negativePrompt: options.negativePrompt,
          referenceImages: options.referenceImages,
          signal: options.signal,
        },
        (status, message) => {
          if (status === "polling") {
            options.onProgress?.("generating_animation", message);
          } else if (status === "completed") {
            options.onProgress?.("animation_complete", message);
          }
        }
      );

      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      logger.error({ error: message }, "アニメーション生成中にエラー");
      return {
        status: "failed",
        error: message,
      };
    }
  }

  private buildFullPrompt(options: ArtMotionGenerateOptions): string {
    const parts: string[] = [];

    if (options.style && options.style !== "custom") {
      const stylePrompt = STYLE_PROMPT_MAP[options.style];
      if (stylePrompt) {
        parts.push(stylePrompt);
      }
    }

    if (options.stylePromptOverride) {
      parts.push(options.stylePromptOverride);
    }

    parts.push(options.prompt);

    return parts.join(". ");
  }

  private buildCacheKey(options: ArtMotionGenerateOptions): string {
    const keyParts = [
      options.prompt,
      options.style ?? "",
      options.aspectRatio ?? "",
      options.resolution ?? "",
      options.imageModel ?? "",
      options.videoModel ?? "",
      options.negativePrompt ?? "",
      options.skipAnimation ? "skip" : "animate",
      options.stylePromptOverride ?? "",
    ];
    return keyParts.join("|");
  }
}

// ============================================================
// ユーティリティ
// ============================================================

function chunkArray<T>(arr: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}
