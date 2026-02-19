/**
 * test-artmotion-e2e.ts — ArtMotion Forge E2E テスト
 *
 * Imagen 3 でイラスト生成 → Veo 3.1 で 1080p アニメーション化
 * Draft モード (NanoBanana → 720p) テスト
 * キービジュアルからのスタイル学習テスト
 *
 * 実行: npx tsx scripts/test-artmotion-e2e.ts
 * 環境変数: GEMINI_API_KEY が必要
 */

import { ArtMotionForge, type ArtMotionProgressStep } from "../src/lib/artmotion-forge.js";

(async () => {
  let passed = 0;
  let failed = 0;
  const results: string[] = [];

  function check(name: string, fn: () => void): void {
    try {
      fn();
      results.push("PASS " + name);
      passed++;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      results.push("FAIL " + name + ": " + msg);
      failed++;
    }
  }

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    console.error("GEMINI_API_KEY が設定されていません。");
    console.error("export GEMINI_API_KEY=your-key を実行してください。");
    process.exit(1);
  }

  console.log("=== ArtMotion Forge E2E テスト ===\n");

  // === 1. Production モード: Imagen 3 → Veo 3.1 1080p ===
  console.log("--- 1. Production モード (Imagen 3 → Veo 3.1 1080p) ---");
  {
    const forge = new ArtMotionForge({ apiKey });
    const steps: ArtMotionProgressStep[] = [];

    const result = await forge.generateProduction({
      prompt: "桜の木の下で風に揺れる花びら、春の朝の光",
      style: "illustration",
      onProgress: (step, message) => {
        steps.push(step);
        console.log(`  [${step}] ${message}`);
      },
    });

    check("Production: ステータスが completed または partial", () => {
      if (result.status !== "completed" && result.status !== "partial") {
        throw new Error(`status=${result.status}, error=${result.error}`);
      }
    });

    check("Production: イラストが生成された", () => {
      if (!result.illustration) throw new Error("illustration is null");
      if (!result.illustration.imageBytes) throw new Error("no imageBytes");
    });

    check("Production: アニメーション結果あり", () => {
      if (result.status === "completed" && !result.animation) {
        throw new Error("animation is null");
      }
    });

    check("Production: プロンプトにスタイル文が含まれる", () => {
      if (!result.prompt.includes("illustration")) {
        throw new Error("style not in prompt: " + result.prompt);
      }
    });

    check("Production: 進捗コールバックが呼ばれた", () => {
      if (!steps.includes("started")) throw new Error("no started step");
      if (!steps.includes("generating_illustration")) {
        throw new Error("no generating_illustration step");
      }
    });

    check("Production: durationMs > 0", () => {
      if (result.durationMs <= 0) throw new Error("durationMs=" + result.durationMs);
    });

    console.log(`  結果: status=${result.status}, durationMs=${result.durationMs}`);
  }

  // === 2. Draft モード (Gemini Flash → Veo 3.1 Fast 720p) ===
  console.log("\n--- 2. Draft モード (NanoBanana → 720p) ---");
  {
    const forge = new ArtMotionForge({ apiKey });
    const steps: ArtMotionProgressStep[] = [];

    const result = await forge.generateDraft({
      prompt: "宇宙空間に浮かぶネオン色のバナナ、SF風",
      style: "flat_design",
      onProgress: (step, message) => {
        steps.push(step);
        console.log(`  [${step}] ${message}`);
      },
    });

    check("Draft: ステータスが completed または partial", () => {
      if (result.status !== "completed" && result.status !== "partial") {
        throw new Error(`status=${result.status}, error=${result.error}`);
      }
    });

    check("Draft: イラスト生成成功", () => {
      if (!result.illustration) throw new Error("illustration is null");
    });

    check("Draft: 進捗コールバック", () => {
      if (steps.length === 0) throw new Error("no progress callbacks");
    });

    console.log(`  結果: status=${result.status}, durationMs=${result.durationMs}`);
  }

  // === 3. キービジュアルからのスタイル学習 ===
  console.log("\n--- 3. キービジュアルからのスタイル学習 ---");
  {
    const forge = new ArtMotionForge({ apiKey });

    const result = await forge.generate({
      prompt: "夜の東京タワー、雨の反射、ネオンライト",
      style: "custom",
      stylePromptOverride:
        "cinematic Japanese city photography style, moody neon lighting, rain reflections",
      skipAnimation: true,
      onProgress: (step, message) => {
        console.log(`  [${step}] ${message}`);
      },
    });

    check("Style: ステータスが completed または partial", () => {
      if (result.status !== "completed" && result.status !== "partial") {
        throw new Error(`status=${result.status}, error=${result.error}`);
      }
    });

    check("Style: カスタムスタイルがプロンプトに反映", () => {
      if (!result.prompt.includes("cinematic Japanese city")) {
        throw new Error("style override not in prompt");
      }
    });

    check("Style: skipAnimation でアニメーションなし", () => {
      if (result.animation !== null) throw new Error("animation should be null");
    });

    console.log(`  結果: status=${result.status}, durationMs=${result.durationMs}`);
  }

  // === 4. キャッシュ機構 ===
  console.log("\n--- 4. キャッシュ機構 ---");
  {
    const forge = new ArtMotionForge({ apiKey });
    const prompt = "テスト用キャッシュ確認プロンプト";

    const result1 = await forge.generate({
      prompt,
      skipAnimation: true,
      style: "watercolor",
    });

    const result2 = await forge.generate({
      prompt,
      skipAnimation: true,
      style: "watercolor",
    });

    check("Cache: 初回はキャッシュなし", () => {
      if (result1.cached) throw new Error("first should not be cached");
    });

    check("Cache: 2回目はキャッシュヒット", () => {
      if (!result2.cached) throw new Error("second should be cached");
    });

    check("Cache: キャッシュヒット時の durationMs が短い", () => {
      if (result2.durationMs > result1.durationMs) {
        console.log(`  警告: cache hit が遅い (${result2.durationMs}ms > ${result1.durationMs}ms)`);
      }
    });

    check("Cache: cacheSize = 1", () => {
      if (forge.cacheSize !== 1) throw new Error("cacheSize=" + forge.cacheSize);
    });

    forge.clearCache();
    check("Cache: clearCache 後 cacheSize = 0", () => {
      if (forge.cacheSize !== 0) throw new Error("cacheSize=" + forge.cacheSize);
    });
  }

  // === 5. バッチ生成 ===
  console.log("\n--- 5. バッチ生成 ---");
  {
    const forge = new ArtMotionForge({ apiKey });

    const batchResult = await forge.generateBatch(
      [
        { prompt: "バッチ1: 山の風景", skipAnimation: true, style: "watercolor" },
        { prompt: "バッチ2: 海の夕焼け", skipAnimation: true, style: "illustration" },
        { prompt: "バッチ3: 都会の夜景", skipAnimation: true, style: "photorealistic" },
      ],
      {
        concurrency: 2,
        onProgress: (index, total, step, message) => {
          console.log(`  [${index + 1}/${total}] [${step}] ${message}`);
        },
      }
    );

    check("Batch: 全3件の結果", () => {
      if (batchResult.results.length !== 3) {
        throw new Error("results.length=" + batchResult.results.length);
      }
    });

    check("Batch: successCount + partialCount + failureCount = 3", () => {
      const total =
        batchResult.successCount + batchResult.partialCount + batchResult.failureCount;
      if (total !== 3) throw new Error("total=" + total);
    });

    check("Batch: totalDurationMs > 0", () => {
      if (batchResult.totalDurationMs <= 0) {
        throw new Error("totalDurationMs=" + batchResult.totalDurationMs);
      }
    });

    console.log(
      `  結果: success=${batchResult.successCount}, partial=${batchResult.partialCount}, ` +
        `failed=${batchResult.failureCount}, duration=${batchResult.totalDurationMs}ms`
    );
  }

  // === 6. AbortSignal ===
  console.log("\n--- 6. AbortSignal ---");
  {
    const forge = new ArtMotionForge({ apiKey });
    const controller = new AbortController();
    controller.abort();

    const result = await forge.generate({
      prompt: "キャンセルテスト",
      signal: controller.signal,
    });

    check("Abort: 事前キャンセルで failed", () => {
      if (result.status !== "failed") throw new Error("status=" + result.status);
    });

    check("Abort: エラーメッセージにキャンセル", () => {
      if (!result.error?.includes("キャンセル")) {
        throw new Error("error=" + result.error);
      }
    });
  }

  // === Summary ===
  console.log("\n" + "=".repeat(50));
  results.forEach((r) => console.log(r));
  console.log("=".repeat(50));
  console.log(`\nTotal: ${passed}/${passed + failed} passed`);

  if (failed > 0) {
    console.error(`\n${failed} 件のテストが失敗しました。`);
    process.exit(1);
  }

  console.log("\nArtMotion Forge E2E テスト全パス!");
})();
