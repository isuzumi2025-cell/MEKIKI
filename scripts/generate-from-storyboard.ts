/**
 * generate-from-storyboard.ts
 *
 * T-402: StoryboardPipeline CLI テストスクリプト
 * 3ショットのサンプルストーリーボードで一括生成をテスト。
 *
 * 使い方:
 *   npx tsx scripts/generate-from-storyboard.ts
 *   npx tsx scripts/generate-from-storyboard.ts --image-only
 *
 * 環境変数:
 *   GEMINI_API_KEY — 必須 (画像生成 + 動画生成)
 */

import "dotenv/config";
import {
    StoryboardPipeline,
    type FlowStoryboardData,
} from "../src/lib/storyboard-pipeline";

const args = process.argv.slice(2);
const imageOnly = args.includes("--image-only");

const sampleStoryboard: FlowStoryboardData = {
    title: "桜の下の猫 — 3ショットデモ",
    globalStyle: "cinematic, soft lighting, film grain, pastel color palette",
    shots: [
        {
            subject: "A fluffy white cat sitting under a cherry blossom tree",
            action: "looking up at falling petals",
            setting: "peaceful Japanese garden in spring",
            camera: "static",
            shotSize: "wide",
            lighting: "golden hour sunlight filtering through branches",
            duration: 5,
        },
        {
            subject: "Close-up of the cat's face",
            action: "a single petal lands on its nose, the cat sneezes gently",
            camera: "dolly_in",
            shotSize: "close_up",
            angle: "eye_level",
            lighting: "soft diffused light with bokeh background",
            duration: 3,
        },
        {
            subject: "The cat walks along a stone path",
            action: "tail swaying gracefully, leaving small paw prints",
            setting: "winding garden path lined with moss-covered stones",
            camera: "tracking",
            shotSize: "medium",
            angle: "low_angle",
            lighting: "dappled sunlight through tree canopy",
            duration: 5,
        },
    ],
};

async function main() {
    console.log("========================================");
    console.log("StoryboardPipeline CLI テスト");
    console.log("========================================");
    console.log(`タイトル: ${sampleStoryboard.title}`);
    console.log(`ショット数: ${sampleStoryboard.shots.length}`);
    console.log(`imageOnly: ${imageOnly}`);
    console.log("----------------------------------------\n");

    const pipeline = new StoryboardPipeline();

    const result = await pipeline.generateFromStoryboard(sampleStoryboard, {
        imageOnly,
        parallelShots: 1,
        aspectRatio: "16:9",
        onProgress: (shotIndex, total, step) => {
            console.log(`[${shotIndex + 1}/${total}] ${step}`);
        },
    });

    console.log("\n========================================");
    console.log("結果サマリー");
    console.log("========================================");
    console.log(`成功: ${result.successCount} / ${result.shots.length}`);
    console.log(`失敗: ${result.failureCount} / ${result.shots.length}`);
    console.log(`合計時間: ${(result.totalDurationMs / 1000).toFixed(1)} 秒`);
    console.log("----------------------------------------\n");

    for (const shot of result.shots) {
        const status = shot.error ? "❌" : "✅";
        console.log(`${status} Shot ${shot.shotIndex}:`);
        console.log(`   プロンプト: ${shot.prompt.slice(0, 80)}...`);
        console.log(`   画像: ${shot.image ? "生成済" : "なし"}`);
        if (!imageOnly) {
            console.log(`   動画: ${shot.videoResult?.status ?? "なし"}`);
        }
        if (shot.error) {
            console.log(`   エラー: ${shot.error}`);
        }
        console.log(`   所要時間: ${(shot.durationMs / 1000).toFixed(1)} 秒\n`);
    }
}

main().catch((err) => {
    console.error("致命的エラー:", err);
    process.exit(1);
});
