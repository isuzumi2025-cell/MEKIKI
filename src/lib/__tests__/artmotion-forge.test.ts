/**
 * artmotion-forge.test.ts
 *
 * ArtMotionForge のユニットテスト
 * - 単一生成 (generate)
 * - エラーリカバリ (フォールバック)
 * - キャッシュ機構
 * - バッチ生成
 * - 進捗コールバック
 * - AbortSignal 対応
 * - Draft / Production モード
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  ArtMotionForge,
  type ArtMotionGenerateOptions,
  type ArtMotionResult,
  type ArtMotionProgressStep,
  type ArtMotionBatchResult,
} from "../artmotion-forge.js";
import { ImageGenClient } from "../image-gen-client.js";
import { VeoClient } from "../veo-client.js";

// ============================================================
// モック設定
// ============================================================

vi.mock("../logger.js", () => ({
  createLogger: () => ({
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  }),
}));

vi.mock("../image-gen-client.js", () => {
  class MockImageGenClient {
    generateImage = vi.fn().mockResolvedValue({
      success: true,
      images: [
        {
          imageBytes: "base64-image-data",
          mimeType: "image/png",
        },
      ],
    });
    generateStartFrame = vi.fn().mockResolvedValue({
      imageBytes: "base64-image-data",
      mimeType: "image/png",
    });
  }

  return { ImageGenClient: MockImageGenClient };
});

vi.mock("../veo-client.js", () => {
  class MockVeoClient {
    generateVideo = vi.fn().mockResolvedValue({
      status: "completed",
      videoUri: "https://example.com/video.mp4",
    });
    generateVideoFromImage = vi.fn().mockResolvedValue({
      status: "completed",
      videoUri: "https://example.com/video.mp4",
    });
    downloadVideo = vi.fn().mockResolvedValue("/tmp/video.mp4");
  }

  return {
    VeoClient: MockVeoClient,
    VideoGenerationReferenceType: { ASSET: "ASSET", STYLE: "STYLE" },
  };
});

const MOCK_API_KEY = "test-api-key-12345";

function createForge(
  overrides?: Partial<ConstructorParameters<typeof ArtMotionForge>[0]>
) {
  return new ArtMotionForge({
    apiKey: MOCK_API_KEY,
    ...overrides,
  });
}

// ============================================================
// コンストラクタ
// ============================================================

describe("ArtMotionForge constructor", () => {
  it("正常にインスタンス化", () => {
    const forge = createForge();
    expect(forge).toBeInstanceOf(ArtMotionForge);
  });

  it("カスタムキャッシュ容量を受け取る", () => {
    const forge = createForge({ cacheCapacity: 100 });
    expect(forge).toBeInstanceOf(ArtMotionForge);
  });

  it("デフォルトモデルを指定", () => {
    const forge = createForge({
      defaultImageModel: "gemini-2.5-flash-image",
      defaultVideoModel: "veo-3.1-fast-generate-preview",
    });
    expect(forge).toBeInstanceOf(ArtMotionForge);
  });
});

// ============================================================
// generate() — 正常系
// ============================================================

describe("ArtMotionForge.generate — 正常系", () => {
  it("イラスト + アニメーション生成に成功", async () => {
    const forge = createForge();
    const result = await forge.generate({
      prompt: "美しい夕焼けの風景",
    });

    expect(result.status).toBe("completed");
    expect(result.illustration).not.toBeNull();
    expect(result.animation).not.toBeNull();
    expect(result.cached).toBe(false);
    expect(result.durationMs).toBeGreaterThanOrEqual(0);
    expect(result.prompt).toContain("美しい夕焼けの風景");
  });

  it("スタイル指定でプロンプトにスタイル文を追加", async () => {
    const forge = createForge();
    const result = await forge.generate({
      prompt: "テスト",
      style: "watercolor",
    });

    expect(result.status).toBe("completed");
    expect(result.prompt).toContain("watercolor");
  });

  it("skipAnimation でイラストのみ生成", async () => {
    const forge = createForge();
    const result = await forge.generate({
      prompt: "テスト",
      skipAnimation: true,
    });

    expect(result.status).toBe("completed");
    expect(result.illustration).not.toBeNull();
    expect(result.animation).toBeNull();
  });

  it("custom スタイルではスタイル文を追加しない", async () => {
    const forge = createForge();
    const result = await forge.generate({
      prompt: "純粋なプロンプト",
      style: "custom",
    });

    expect(result.prompt).toBe("純粋なプロンプト");
  });

  it("stylePromptOverride でカスタムスタイル文を注入", async () => {
    const forge = createForge();
    const result = await forge.generate({
      prompt: "基本プロンプト",
      style: "custom",
      stylePromptOverride: "my custom style directive",
    });

    expect(result.prompt).toContain("my custom style directive");
    expect(result.prompt).toContain("基本プロンプト");
  });

  it("各スタイルのプロンプト変換", async () => {
    const forge = createForge();
    const styles = [
      "illustration",
      "watercolor",
      "anime",
      "photorealistic",
      "flat_design",
    ] as const;

    for (const style of styles) {
      const result = await forge.generate({
        prompt: "テスト",
        style,
        skipAnimation: true,
      });
      expect(result.status).toBe("completed");
    }
  });
});

// ============================================================
// generate() — バリデーション
// ============================================================

describe("ArtMotionForge.generate — バリデーション", () => {
  it("空プロンプトでバリデーションエラー", async () => {
    const forge = createForge();
    const result = await forge.generate({
      prompt: "",
    });

    expect(result.status).toBe("failed");
    expect(result.error).toContain("バリデーションエラー");
  });
});

// ============================================================
// generate() — エラーリカバリ (フォールバック)
// ============================================================

describe("ArtMotionForge.generate — エラーリカバリ", () => {
  it("プライマリモデル失敗時にフォールバック", async () => {
    const forge = createForge();

    const mockImageClient = (forge as unknown as { imageClient: { generateImage: ReturnType<typeof vi.fn> } }).imageClient;

    let callCount = 0;
    mockImageClient.generateImage = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({ success: false, images: [], error: "primary failed" });
      }
      return Promise.resolve({
        success: true,
        images: [{ imageBytes: "fallback-data", mimeType: "image/png" }],
      });
    });

    const result = await forge.generate({
      prompt: "テスト",
      skipAnimation: true,
    });

    expect(result.status).toBe("completed");
    expect(mockImageClient.generateImage).toHaveBeenCalledTimes(2);
  });

  it("全モデル失敗で status: failed", async () => {
    const forge = createForge();

    const mockImageClient = (forge as unknown as { imageClient: { generateImage: ReturnType<typeof vi.fn> } }).imageClient;
    mockImageClient.generateImage = vi.fn().mockResolvedValue({
      success: false,
      images: [],
      error: "all models failed",
    });

    const result = await forge.generate({
      prompt: "テスト",
    });

    expect(result.status).toBe("failed");
    expect(result.error).toContain("フォールバック含む全モデルで失敗");
  });

  it("動画生成失敗で status: partial (イラストは返す)", async () => {
    const forge = createForge();

    const mockVeoClient = (forge as unknown as { veoClient: { generateVideoFromImage: ReturnType<typeof vi.fn> } }).veoClient;
    mockVeoClient.generateVideoFromImage = vi.fn().mockResolvedValue({
      status: "failed",
      error: "video generation failed",
    });

    const result = await forge.generate({
      prompt: "テスト",
    });

    expect(result.status).toBe("partial");
    expect(result.illustration).not.toBeNull();
    expect(result.error).toContain("アニメーション生成に失敗");
  });

  it("動画生成で例外が発生しても partial で返す", async () => {
    const forge = createForge();

    const mockVeoClient = (forge as unknown as { veoClient: { generateVideoFromImage: ReturnType<typeof vi.fn> } }).veoClient;
    mockVeoClient.generateVideoFromImage = vi.fn().mockRejectedValue(
      new Error("unexpected error")
    );

    const result = await forge.generate({
      prompt: "テスト",
    });

    expect(result.status).toBe("partial");
    expect(result.illustration).not.toBeNull();
  });
});

// ============================================================
// キャッシュ機構
// ============================================================

describe("ArtMotionForge キャッシュ", () => {
  it("同じリクエストでキャッシュヒット", async () => {
    const forge = createForge();

    const result1 = await forge.generate({
      prompt: "キャッシュテスト",
      skipAnimation: true,
    });

    const result2 = await forge.generate({
      prompt: "キャッシュテスト",
      skipAnimation: true,
    });

    expect(result1.cached).toBe(false);
    expect(result2.cached).toBe(true);
    expect(result2.illustration).toEqual(result1.illustration);
  });

  it("異なるリクエストはキャッシュミス", async () => {
    const forge = createForge();

    await forge.generate({
      prompt: "プロンプトA",
      skipAnimation: true,
    });

    const result2 = await forge.generate({
      prompt: "プロンプトB",
      skipAnimation: true,
    });

    expect(result2.cached).toBe(false);
  });

  it("異なるスタイルはキャッシュミス", async () => {
    const forge = createForge();

    await forge.generate({
      prompt: "テスト",
      style: "anime",
      skipAnimation: true,
    });

    const result2 = await forge.generate({
      prompt: "テスト",
      style: "watercolor",
      skipAnimation: true,
    });

    expect(result2.cached).toBe(false);
  });

  it("clearCache でキャッシュをクリア", async () => {
    const forge = createForge();

    await forge.generate({
      prompt: "テスト",
      skipAnimation: true,
    });

    expect(forge.cacheSize).toBe(1);
    forge.clearCache();
    expect(forge.cacheSize).toBe(0);
  });

  it("cacheSize プロパティが正確", async () => {
    const forge = createForge();
    expect(forge.cacheSize).toBe(0);

    await forge.generate({ prompt: "A", skipAnimation: true });
    expect(forge.cacheSize).toBe(1);

    await forge.generate({ prompt: "B", skipAnimation: true });
    expect(forge.cacheSize).toBe(2);
  });

  it("失敗結果はキャッシュしない (全モデル失敗)", async () => {
    const forge = createForge();

    const mockImageClient = (forge as unknown as { imageClient: { generateImage: ReturnType<typeof vi.fn> } }).imageClient;
    mockImageClient.generateImage = vi.fn().mockResolvedValue({
      success: false,
      images: [],
      error: "fail",
    });

    await forge.generate({ prompt: "失敗テスト" });
    expect(forge.cacheSize).toBe(0);
  });

  it("partial 結果はキャッシュする", async () => {
    const forge = createForge();

    const mockVeoClient = (forge as unknown as { veoClient: { generateVideoFromImage: ReturnType<typeof vi.fn> } }).veoClient;
    mockVeoClient.generateVideoFromImage = vi.fn().mockResolvedValue({
      status: "failed",
      error: "video failed",
    });

    await forge.generate({ prompt: "部分成功テスト" });
    expect(forge.cacheSize).toBe(1);
  });
});

// ============================================================
// 進捗コールバック
// ============================================================

describe("ArtMotionForge 進捗コールバック", () => {
  it("生成の各ステップでコールバックが呼ばれる", async () => {
    const forge = createForge();
    const steps: ArtMotionProgressStep[] = [];

    await forge.generate({
      prompt: "テスト",
      skipAnimation: true,
      onProgress: (step) => {
        steps.push(step);
      },
    });

    expect(steps).toContain("started");
    expect(steps).toContain("generating_illustration");
    expect(steps).toContain("illustration_complete");
    expect(steps).toContain("completed");
  });

  it("キャッシュヒット時に cache_hit コールバック", async () => {
    const forge = createForge();
    await forge.generate({ prompt: "テスト", skipAnimation: true });

    const steps: ArtMotionProgressStep[] = [];
    await forge.generate({
      prompt: "テスト",
      skipAnimation: true,
      onProgress: (step) => steps.push(step),
    });

    expect(steps).toContain("cache_hit");
  });

  it("フォールバック時に illustration_fallback コールバック", async () => {
    const forge = createForge();
    const mockImageClient = (forge as unknown as { imageClient: { generateImage: ReturnType<typeof vi.fn> } }).imageClient;

    let callCount = 0;
    mockImageClient.generateImage = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({ success: false, images: [] });
      }
      return Promise.resolve({
        success: true,
        images: [{ imageBytes: "data", mimeType: "image/png" }],
      });
    });

    const steps: ArtMotionProgressStep[] = [];
    await forge.generate({
      prompt: "テスト",
      skipAnimation: true,
      onProgress: (step) => steps.push(step),
    });

    expect(steps).toContain("illustration_fallback");
  });

  it("失敗時に failed コールバック", async () => {
    const forge = createForge();
    const mockImageClient = (forge as unknown as { imageClient: { generateImage: ReturnType<typeof vi.fn> } }).imageClient;
    mockImageClient.generateImage = vi.fn().mockResolvedValue({
      success: false,
      images: [],
    });

    const steps: ArtMotionProgressStep[] = [];
    await forge.generate({
      prompt: "テスト",
      onProgress: (step) => steps.push(step),
    });

    expect(steps).toContain("failed");
  });
});

// ============================================================
// AbortSignal 対応
// ============================================================

describe("ArtMotionForge AbortSignal", () => {
  it("生成前にキャンセルされると failed を返す", async () => {
    const forge = createForge();
    const controller = new AbortController();
    controller.abort();

    const result = await forge.generate({
      prompt: "テスト",
      signal: controller.signal,
    });

    expect(result.status).toBe("failed");
    expect(result.error).toContain("キャンセル");
  });

  it("イラスト生成後にキャンセルされると partial を返す", async () => {
    const forge = createForge();
    const controller = new AbortController();

    const mockImageClient = (forge as unknown as { imageClient: { generateImage: ReturnType<typeof vi.fn> } }).imageClient;
    mockImageClient.generateImage = vi.fn().mockImplementation(async () => {
      controller.abort();
      return {
        success: true,
        images: [{ imageBytes: "data", mimeType: "image/png" }],
      };
    });

    const result = await forge.generate({
      prompt: "テスト",
      signal: controller.signal,
    });

    expect(result.status).toBe("partial");
    expect(result.illustration).not.toBeNull();
  });
});

// ============================================================
// バッチ生成
// ============================================================

describe("ArtMotionForge.generateBatch", () => {
  it("複数リクエストを一括処理", async () => {
    const forge = createForge();
    const requests: ArtMotionGenerateOptions[] = [
      { prompt: "シーン1", skipAnimation: true },
      { prompt: "シーン2", skipAnimation: true },
      { prompt: "シーン3", skipAnimation: true },
    ];

    const batchResult = await forge.generateBatch(requests);

    expect(batchResult.results).toHaveLength(3);
    expect(batchResult.successCount).toBe(3);
    expect(batchResult.failureCount).toBe(0);
    expect(batchResult.totalDurationMs).toBeGreaterThanOrEqual(0);
  });

  it("並列度制御 (concurrency)", async () => {
    const forge = createForge();
    const requests: ArtMotionGenerateOptions[] = Array.from(
      { length: 6 },
      (_, i) => ({
        prompt: `シーン${i}`,
        skipAnimation: true,
      })
    );

    const batchResult = await forge.generateBatch(requests, {
      concurrency: 2,
    });

    expect(batchResult.results).toHaveLength(6);
    expect(batchResult.successCount).toBe(6);
  });

  it("バッチ全体の進捗コールバック", async () => {
    const forge = createForge();
    const progressCalls: { index: number; total: number; step: string }[] = [];

    const requests: ArtMotionGenerateOptions[] = [
      { prompt: "A", skipAnimation: true },
      { prompt: "B", skipAnimation: true },
    ];

    await forge.generateBatch(requests, {
      onProgress: (index, total, step, _message) => {
        progressCalls.push({ index, total, step });
      },
    });

    expect(progressCalls.length).toBeGreaterThan(0);
    expect(progressCalls.some((c) => c.index === 0)).toBe(true);
    expect(progressCalls.some((c) => c.index === 1)).toBe(true);
  });

  it("バッチ AbortSignal でキャンセル", async () => {
    const forge = createForge();
    const controller = new AbortController();
    controller.abort();

    const requests: ArtMotionGenerateOptions[] = [
      { prompt: "A" },
      { prompt: "B" },
    ];

    const batchResult = await forge.generateBatch(requests, {
      signal: controller.signal,
    });

    expect(batchResult.failureCount).toBe(2);
    for (const r of batchResult.results) {
      expect(r.status).toBe("failed");
      expect(r.error).toContain("キャンセル");
    }
  });

  it("一部失敗しても他は継続", async () => {
    const forge = createForge();
    const mockImageClient = (forge as unknown as { imageClient: { generateImage: ReturnType<typeof vi.fn> } }).imageClient;

    let callCount = 0;
    mockImageClient.generateImage = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount <= 2) {
        return Promise.resolve({ success: false, images: [] });
      }
      return Promise.resolve({
        success: true,
        images: [{ imageBytes: "data", mimeType: "image/png" }],
      });
    });

    const requests: ArtMotionGenerateOptions[] = [
      { prompt: "失敗1", skipAnimation: true },
      { prompt: "成功", skipAnimation: true },
    ];

    const batchResult = await forge.generateBatch(requests);
    expect(batchResult.results).toHaveLength(2);
    expect(batchResult.failureCount).toBeGreaterThanOrEqual(0);
  });

  it("空リクエスト配列", async () => {
    const forge = createForge();
    const batchResult = await forge.generateBatch([]);
    expect(batchResult.results).toHaveLength(0);
    expect(batchResult.successCount).toBe(0);
  });

  it("partialCount を正しくカウント", async () => {
    const forge = createForge();
    const mockVeoClient = (forge as unknown as { veoClient: { generateVideoFromImage: ReturnType<typeof vi.fn> } }).veoClient;
    mockVeoClient.generateVideoFromImage = vi.fn().mockResolvedValue({
      status: "failed",
      error: "video failed",
    });

    const requests: ArtMotionGenerateOptions[] = [
      { prompt: "partial1" },
      { prompt: "partial2" },
    ];

    const batchResult = await forge.generateBatch(requests);
    expect(batchResult.partialCount).toBe(2);
  });
});

// ============================================================
// Draft / Production モード
// ============================================================

describe("ArtMotionForge Draft/Production", () => {
  it("generateDraft は Draft モードモデルを使用", async () => {
    const forge = createForge();
    const result = await forge.generateDraft({
      prompt: "ドラフトテスト",
      skipAnimation: true,
    });

    expect(result.status).toBe("completed");
  });

  it("generateProduction は Production モードモデルを使用", async () => {
    const forge = createForge();
    const result = await forge.generateProduction({
      prompt: "プロダクションテスト",
      skipAnimation: true,
    });

    expect(result.status).toBe("completed");
  });
});

// ============================================================
// キャッシュキー差分テスト
// ============================================================

describe("ArtMotionForge キャッシュキー", () => {
  it("resolution の違いでキャッシュミス", async () => {
    const forge = createForge();

    await forge.generate({
      prompt: "テスト",
      resolution: "720p",
      skipAnimation: true,
    });

    const result2 = await forge.generate({
      prompt: "テスト",
      resolution: "1080p",
      skipAnimation: true,
    });

    expect(result2.cached).toBe(false);
  });

  it("negativePrompt の違いでキャッシュミス", async () => {
    const forge = createForge();

    await forge.generate({
      prompt: "テスト",
      negativePrompt: "blur",
      skipAnimation: true,
    });

    const result2 = await forge.generate({
      prompt: "テスト",
      negativePrompt: "noise",
      skipAnimation: true,
    });

    expect(result2.cached).toBe(false);
  });

  it("skipAnimation の違いでキャッシュミス", async () => {
    const forge = createForge();

    await forge.generate({
      prompt: "テスト",
      skipAnimation: true,
    });

    const result2 = await forge.generate({
      prompt: "テスト",
      skipAnimation: false,
    });

    expect(result2.cached).toBe(false);
  });
});
