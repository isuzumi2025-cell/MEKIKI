/**
 * storyboard-pipeline.ts
 *
 * 複数ショットから一括でコンテ画像 → 動画を生成するオーケストレーター。
 * FlowStoryboardData を受け取り、各ショットを Nano Banana → Veo パイプラインで処理。
 *
 * @see image-gen-client.ts  — Nano Banana (gemini-2.5-flash-image) でコンテ画像生成
 * @see veo-client.ts        — Veo 3.1 で画像 → 動画変換
 * @see flow-prompt-builder.ts — ショット定義 + プロンプト構築
 *
 * FlowForge SDK — Orchestration Layer
 */

import {
    ImageGenClient,
    type GeneratedImage,
    type ImageAspectRatio,
} from "./image-gen-client";
import {
    VeoClient,
    type VeoGenerationResult,
    type VeoAspectRatio,
} from "./veo-client";
import {
    FlowPromptBuilder,
    type FlowShot,
} from "./flow-prompt-builder";

// ============================================================
// Types
// ============================================================

/**
 * ストーリーボード：複数ショットの配列 + メタ情報
 */
export interface FlowStoryboardData {
    /** ストーリーボードのタイトル */
    title: string;
    /** 全体のスタイルやトーン（各ショットに継承） */
    globalStyle?: string;
    /** ショットの配列 */
    shots: FlowShot[];
}

/**
 * パイプラインのオプション
 */
export interface StoryboardPipelineOptions {
    /** コンテ画像のみ生成（動画化スキップ） */
    imageOnly?: boolean;
    /** 並列生成ショット数 (default: 1 = 順次処理) */
    parallelShots?: number;
    /** アスペクト比 (default: "16:9") */
    aspectRatio?: string;
    /** 進捗コールバック */
    onProgress?: (shotIndex: number, total: number, step: string) => void;
    /** 動画ダウンロード先ディレクトリ */
    outputDir?: string;
}

/**
 * 各ショットの生成結果
 */
export interface ShotResult {
    shotIndex: number;
    prompt: string;
    image?: GeneratedImage;
    videoResult?: VeoGenerationResult;
    savedVideoPath?: string;
    durationMs: number;
    error?: string;
}

/**
 * ストーリーボード全体の生成結果
 */
export interface StoryboardResult {
    title: string;
    shots: ShotResult[];
    totalDurationMs: number;
    successCount: number;
    failureCount: number;
}

// ============================================================
// Pipeline
// ============================================================

export class StoryboardPipeline {
    private imageClient: ImageGenClient;
    private veoClient: VeoClient;

    constructor(options?: { apiKey?: string }) {
        this.imageClient = new ImageGenClient({ apiKey: options?.apiKey });
        this.veoClient = new VeoClient({ apiKey: options?.apiKey });
    }

    /**
     * ストーリーボードから一括生成
     *
     * 各ショットを以下のフローで処理:
     * 1. FlowPromptBuilder でプロンプト構築
     * 2. ImageGenClient.generateStartFrame() でコンテ画像生成
     * 3. (imageOnly でなければ) VeoClient.generateVideoFromImage() で動画変換
     *
     * エラーが発生しても他のショットは継続して処理。
     */
    async generateFromStoryboard(
        storyboard: FlowStoryboardData,
        options?: StoryboardPipelineOptions,
    ): Promise<StoryboardResult> {
        const startTime = Date.now();
        const parallelShots = Math.max(1, options?.parallelShots ?? 1);
        const aspectRatio = (options?.aspectRatio ?? "16:9") as ImageAspectRatio;

        const results: ShotResult[] = [];

        // チャンク分割で並列度を制御
        const chunks = chunkArray(storyboard.shots, parallelShots);
        let processedCount = 0;

        for (const chunk of chunks) {
            const chunkPromises = chunk.map(async (shot, chunkIdx) => {
                const shotIndex = processedCount + chunkIdx;
                return this.processShot(
                    shot,
                    shotIndex,
                    storyboard,
                    aspectRatio,
                    options,
                );
            });

            const chunkResults = await Promise.allSettled(chunkPromises);

            for (let i = 0; i < chunkResults.length; i++) {
                const settled = chunkResults[i];
                if (settled.status === "fulfilled") {
                    results.push(settled.value);
                } else {
                    results.push({
                        shotIndex: processedCount + i,
                        prompt: "",
                        durationMs: 0,
                        error: settled.reason?.message ?? String(settled.reason),
                    });
                }
            }

            processedCount += chunk.length;
        }

        const successCount = results.filter((r) => !r.error).length;
        const failureCount = results.filter((r) => !!r.error).length;

        return {
            title: storyboard.title,
            shots: results,
            totalDurationMs: Date.now() - startTime,
            successCount,
            failureCount,
        };
    }

    /**
     * 個別ショットを処理
     */
    private async processShot(
        shot: FlowShot,
        shotIndex: number,
        storyboard: FlowStoryboardData,
        aspectRatio: ImageAspectRatio,
        options?: StoryboardPipelineOptions,
    ): Promise<ShotResult> {
        const shotStart = Date.now();

        // Step 1: プロンプト構築
        const prompt = this.buildPromptForShot(shot, storyboard.globalStyle);
        options?.onProgress?.(shotIndex, storyboard.shots.length, "prompt_built");

        // Step 2: コンテ画像生成
        options?.onProgress?.(shotIndex, storyboard.shots.length, "generating_image");
        const image = await this.imageClient.generateStartFrame(prompt, aspectRatio);

        if (!image) {
            return {
                shotIndex,
                prompt,
                durationMs: Date.now() - shotStart,
                error: `Shot ${shotIndex}: コンテ画像の生成に失敗しました`,
            };
        }

        options?.onProgress?.(shotIndex, storyboard.shots.length, "image_generated");

        // imageOnly の場合はここで終了
        if (options?.imageOnly) {
            return {
                shotIndex,
                prompt,
                image,
                durationMs: Date.now() - shotStart,
            };
        }

        // Step 3: 動画生成
        options?.onProgress?.(shotIndex, storyboard.shots.length, "generating_video");
        try {
            const videoResult = await this.veoClient.generateVideoFromImage(
                image.imageBytes,
                image.mimeType,
                prompt,
                { aspectRatio: aspectRatio as VeoAspectRatio },
            );

            if (videoResult.status === "failed") {
                return {
                    shotIndex,
                    prompt,
                    image,
                    videoResult,
                    durationMs: Date.now() - shotStart,
                    error: `Shot ${shotIndex}: 動画生成に失敗 — ${videoResult.error}`,
                };
            }

            options?.onProgress?.(shotIndex, storyboard.shots.length, "video_generated");

            // Step 4: (オプション) 動画ダウンロード
            let savedVideoPath: string | undefined;
            if (options?.outputDir && videoResult.status === "completed") {
                try {
                    const { join } = await import("path");
                    const downloadPath = join(
                        options.outputDir,
                        `shot-${String(shotIndex).padStart(3, "0")}.mp4`,
                    );
                    savedVideoPath = await this.veoClient.downloadVideo(
                        videoResult,
                        downloadPath,
                    );
                    options?.onProgress?.(
                        shotIndex,
                        storyboard.shots.length,
                        "video_downloaded",
                    );
                } catch (dlErr) {
                    // ダウンロード失敗はワーニングのみ（生成自体は成功）
                    console.warn(
                        `[StoryboardPipeline] Shot ${shotIndex} ダウンロード失敗:`,
                        dlErr,
                    );
                }
            }

            return {
                shotIndex,
                prompt,
                image,
                videoResult,
                savedVideoPath,
                durationMs: Date.now() - shotStart,
            };
        } catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            return {
                shotIndex,
                prompt,
                image,
                durationMs: Date.now() - shotStart,
                error: `Shot ${shotIndex}: 動画生成中にエラー — ${message}`,
            };
        }
    }

    /**
     * FlowShot からプロンプトテキストを組み立てる
     */
    private buildPromptForShot(shot: FlowShot, globalStyle?: string): string {
        const builder = new FlowPromptBuilder(shot.subject);

        if (shot.action) builder.setAction(shot.action);
        if (shot.setting) builder.setSetting(shot.setting);
        if (shot.camera) builder.setCamera(shot.camera);
        if (shot.angle) builder.setAngle(shot.angle);
        if (shot.shotSize) builder.setShotSize(shot.shotSize);
        if (shot.lighting) builder.setLighting(shot.lighting);
        if (shot.toneManner) builder.setToneManner(shot.toneManner);
        if (shot.motionGraphics) builder.setMotionGraphics(shot.motionGraphics);
        if (shot.duration) builder.setDuration(shot.duration);

        if (shot.characters) {
            for (const char of shot.characters) {
                builder.addCharacter(char);
            }
        }
        if (shot.objects) {
            for (const obj of shot.objects) {
                builder.addObject(obj);
            }
        }

        // グローバルスタイル + ショット固有スタイルを結合
        const styles = [globalStyle, shot.style].filter(Boolean).join(". ");
        if (styles) builder.setStyle(styles);

        if (shot.negativePrompt) builder.setNegativePrompt(shot.negativePrompt);

        return builder.buildPrompt();
    }
}

// ============================================================
// Utility
// ============================================================

function chunkArray<T>(arr: T[], size: number): T[][] {
    const chunks: T[][] = [];
    for (let i = 0; i < arr.length; i += size) {
        chunks.push(arr.slice(i, i + size));
    }
    return chunks;
}
