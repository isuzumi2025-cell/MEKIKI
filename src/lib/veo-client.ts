/**
 * veo-client.ts
 *
 * Google Veo 3.1 動画生成クライアント SDK
 * Gemini API 経由で Veo 3.1 にアクセスし、テキスト/画像から動画を生成する。
 *
 * @see https://ai.google.dev/gemini-api/docs/video
 */

import {
  GoogleGenAI,
  VideoGenerationReferenceType,
  type GenerateVideosOperation,
  type GenerateVideosParameters,
  type Video,
  type VideoGenerationReferenceImage,
} from "@google/genai";
import { withRetry } from "./utils/retry.js";

export type VeoAspectRatio = "16:9" | "9:16";

export type VeoResolution = "720p" | "1080p" | "4k";

export type VeoModel =
  | "veo-3.1-generate-preview"
  | "veo-3.1-fast-generate-preview"
  | "veo-2-generate-001";

export type ReferenceImageType = "asset" | "style" | "subject";

export interface VeoReferenceImage {
  imageBytes: string;
  mimeType: "image/png" | "image/jpeg" | "image/webp";
  referenceType: ReferenceImageType;
}

export interface GenerateVideoOptions {
  prompt: string;
  model?: VeoModel;
  aspectRatio?: VeoAspectRatio;
  resolution?: VeoResolution;
  negativePrompt?: string;
  image?: {
    imageBytes: string;
    mimeType: string;
  };
  referenceImages?: VeoReferenceImage[];
  personGeneration?: "allow_adult" | "dont_allow";
  signal?: AbortSignal;
}

export type VeoGenerationStatus =
  | "pending"
  | "polling"
  | "completed"
  | "failed"
  | "timeout";

export interface VeoGenerationResult {
  status: VeoGenerationStatus;
  videoUri?: string;
  videoFile?: Video;
  savedPath?: string;
  error?: string;
}

export type VeoProgressCallback = (
  status: VeoGenerationStatus,
  message: string
) => void;

const MAX_REFERENCE_IMAGES = 3;

export class VeoClient {
  private ai: GoogleGenAI;
  private defaultModel: VeoModel;

  constructor(options?: { apiKey?: string; defaultModel?: VeoModel }) {
    const apiKey =
      options?.apiKey ??
      (typeof process !== "undefined"
        ? process.env.GEMINI_API_KEY ?? ""
        : "");

    if (!apiKey) {
      throw new Error(
        "[VeoClient] GEMINI_API_KEY が設定されていません。" +
          ".env に GEMINI_API_KEY を追加してください。"
      );
    }

    this.ai = new GoogleGenAI({ apiKey });
    this.defaultModel = options?.defaultModel ?? "veo-3.1-generate-preview";

    if (typeof this.ai.models.generateVideos !== "function") {
      throw new Error(
        "[VeoClient] models.generateVideos メソッドが利用できません。SDK バージョンを確認してください。"
      );
    }
    if (typeof this.ai.operations.getVideosOperation !== "function") {
      throw new Error(
        "[VeoClient] operations.getVideosOperation メソッドが利用できません。SDK バージョンを確認してください。"
      );
    }
  }

  async generateVideo(
    options: GenerateVideoOptions,
    onProgress?: VeoProgressCallback
  ): Promise<VeoGenerationResult> {
    this.validateGenerateVideoOptions(options);

    const model = options.model ?? this.defaultModel;

    try {
      onProgress?.("pending", "動画生成リクエストを送信中...");

      const requestParams: GenerateVideosParameters = {
        model,
        prompt: options.prompt,
      };

      if (options.image) {
        requestParams.image = {
          imageBytes: options.image.imageBytes,
          mimeType: options.image.mimeType,
        };
      }

      const configEntries: GenerateVideosParameters["config"] = {};

      if (options.referenceImages?.length) {
        configEntries.referenceImages = options.referenceImages.map(
          (ref): VideoGenerationReferenceImage => ({
            image: {
              imageBytes: ref.imageBytes,
              mimeType: ref.mimeType,
            },
            referenceType: this.toVideoGenerationReferenceType(ref.referenceType),
          })
        );
      }

      if (options.aspectRatio) {
        configEntries.aspectRatio = options.aspectRatio;
      }
      if (options.negativePrompt) {
        configEntries.negativePrompt = options.negativePrompt;
      }
      if (options.personGeneration) {
        configEntries.personGeneration = options.personGeneration;
      }

      if (Object.keys(configEntries).length > 0) {
        requestParams.config = configEntries;
      }

      let operation: GenerateVideosOperation = await withRetry(
        () => this.ai.models.generateVideos(requestParams),
        { maxAttempts: 3, baseDelayMs: 2000 },
        options.signal
      );

      onProgress?.(
        "polling",
        "動画を生成中... (通常 30秒〜6分かかります)"
      );

      const maxAttempts = 60;
      let attempts = 0;
      const basePollingIntervalMs = 10000;
      const pollingBackoffMultiplier = 1.5;
      const maxPollingIntervalMs = 60000;

      while (!operation.done && attempts < maxAttempts) {
        if (options.signal?.aborted) {
          return {
            status: "failed",
            error: "リクエストがキャンセルされました",
          };
        }

        const pollingInterval = Math.min(
          basePollingIntervalMs *
            Math.pow(pollingBackoffMultiplier, Math.min(attempts, 10)),
          maxPollingIntervalMs
        );

        await this.sleep(pollingInterval, options.signal);
        attempts++;

        operation = await withRetry(
          () =>
            this.ai.operations.getVideosOperation({
              operation,
            }),
          { maxAttempts: 2, baseDelayMs: 1000 },
          options.signal
        );

        onProgress?.(
          "polling",
          `動画生成中... (${Math.round((attempts * pollingInterval) / 1000)}秒経過)`
        );
      }

      if (!operation.done) {
        return {
          status: "timeout",
          error: "動画生成がタイムアウトしました（10 分）",
        };
      }

      const generatedVideos = operation.response?.generatedVideos;
      if (!generatedVideos?.length) {
        return {
          status: "failed",
          error: "動画が生成されませんでした（安全フィルター等の可能性）",
        };
      }

      const video: Video | undefined = generatedVideos[0].video;

      onProgress?.("completed", "動画生成が完了しました！");

      return {
        status: "completed",
        videoFile: video,
        videoUri: video?.uri ?? undefined,
      };
    } catch (err) {
      if (
        err instanceof DOMException &&
        err.name === "AbortError"
      ) {
        onProgress?.("failed", "リクエストがキャンセルされました");
        return {
          status: "failed",
          error: "リクエストがキャンセルされました",
        };
      }
      const message = err instanceof Error ? err.message : String(err);
      onProgress?.("failed", `生成エラー: ${message}`);
      return {
        status: "failed",
        error: message,
      };
    }
  }

  async generateVideoFromImage(
    imageBytes: string,
    mimeType: string,
    prompt: string,
    additionalOptions?: Partial<GenerateVideoOptions>,
    onProgress?: VeoProgressCallback
  ): Promise<VeoGenerationResult> {
    return this.generateVideo(
      {
        prompt,
        image: { imageBytes, mimeType },
        ...additionalOptions,
      },
      onProgress
    );
  }

  async downloadVideo(
    result: VeoGenerationResult,
    downloadPath: string
  ): Promise<string> {
    if (!result.videoFile) {
      throw new Error("[VeoClient] ダウンロードする動画がありません");
    }

    if (typeof this.ai.files.download !== "function") {
      throw new Error(
        "[VeoClient] files.download メソッドが利用できません。SDK バージョンを確認してください。"
      );
    }

    await withRetry(
      () =>
        this.ai.files.download({
          file: result.videoFile!,
          downloadPath,
        }),
      { maxAttempts: 3, baseDelayMs: 2000 }
    );

    return downloadPath;
  }

  private validateGenerateVideoOptions(options: GenerateVideoOptions): void {
    if (!options.prompt || options.prompt.trim().length === 0) {
      throw new Error(
        "[VeoClient] prompt は必須です。空のプロンプトは指定できません。"
      );
    }

    if (
      options.referenceImages &&
      options.referenceImages.length > MAX_REFERENCE_IMAGES
    ) {
      throw new Error(
        `[VeoClient] referenceImages は最大 ${MAX_REFERENCE_IMAGES} 枚までです。` +
          `（指定: ${options.referenceImages.length} 枚）`
      );
    }
  }

  private toVideoGenerationReferenceType(
    type: ReferenceImageType
  ): VideoGenerationReferenceType {
    const mapping: Record<ReferenceImageType, VideoGenerationReferenceType> = {
      asset: VideoGenerationReferenceType.ASSET,
      style: VideoGenerationReferenceType.STYLE,
      subject: VideoGenerationReferenceType.ASSET,
    };
    return mapping[type];
  }

  private sleep(ms: number, signal?: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) {
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      const timer = setTimeout(resolve, ms);
      signal?.addEventListener(
        "abort",
        () => {
          clearTimeout(timer);
          reject(new DOMException("Aborted", "AbortError"));
        },
        { once: true }
      );
    });
  }
}
