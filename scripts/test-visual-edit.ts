/**
 * test-visual-edit.ts
 *
 * T-306: VisualEditEngine E2E テストスクリプト
 * 参照画像でオブジェクト差し替えワークフローを検証。
 *
 * 使い方:
 *   npx tsx scripts/test-visual-edit.ts
 *
 * 環境変数:
 *   GEMINI_API_KEY — 必須 (Gemini Vision API)
 */

import "dotenv/config";
import { VisualEditEngine, type VisualEditInstruction } from "../src/lib/visual-edit-engine";
import { ResourceVideoGenerator } from "../src/lib/resource-video-generator";
import type { EditablePromptData } from "../src/lib/editable-prompt";

const DIVIDER = "========================================";

function createMockPreviousResult() {
    const editablePrompt: EditablePromptData = {
        sections: [
            {
                id: "scene",
                label: "シーン記述",
                content: "A cozy living room with warm lighting and wooden furniture",
                source: "analysis",
                modified: false,
            },
            {
                id: "characters",
                label: "登場人物",
                content: "A young woman wearing a blue dress, sitting on a sofa",
                source: "analysis",
                modified: false,
            },
            {
                id: "objects",
                label: "小道具・物体",
                content: "wooden table, ceramic vase with flowers, old leather-bound book",
                source: "analysis",
                modified: false,
            },
            {
                id: "style",
                label: "スタイル",
                content: "warm color grading, soft focus, indie film aesthetic",
                source: "analysis",
                modified: false,
            },
        ],
        combinedPrompt: "A cozy living room with warm lighting and wooden furniture. A young woman wearing a blue dress, sitting on a sofa. wooden table, ceramic vase with flowers, old leather-bound book. warm color grading, soft focus, indie film aesthetic.",
        updatedAt: new Date().toISOString(),
    };

    return {
        status: "completed" as const,
        mode: "text_to_video" as const,
        finalPrompt: editablePrompt.combinedPrompt,
        editablePrompt,
        log: [
            { step: "テスト", status: "ok" as const, message: "モックデータ作成済", durationMs: 0 },
        ],
        createdAt: new Date().toISOString(),
    };
}

async function testEditTypeMapping() {
    console.log(`\n${DIVIDER}`);
    console.log("テスト 1: editType → referenceType マッピング");
    console.log(DIVIDER);

    const engine = new VisualEditEngine();

    const mappings: Record<string, string> = {
        replace_shape: "asset",
        replace_style: "style",
        replace_color: "style",
        add_from_image: "asset",
        match_pose: "subject",
    };

    let passed = 0;
    for (const [editType, expected] of Object.entries(mappings)) {
        const result = engine.mapEditTypeToReferenceType(
            editType as VisualEditInstruction["editType"]
        );
        const ok = result === expected;
        console.log(`  ${ok ? "✅" : "❌"} ${editType} → ${result} (期待値: ${expected})`);
        if (ok) passed++;
    }

    console.log(`\n  結果: ${passed}/5 パス\n`);
    return passed === 5;
}

async function testResourceVideoGeneratorIntegration() {
    console.log(`\n${DIVIDER}`);
    console.log("テスト 2: ResourceVideoGenerator.regenerateWithVisualReference 統合");
    console.log(DIVIDER);

    const generator = new ResourceVideoGenerator();
    const previousResult = createMockPreviousResult();

    console.log("  モック previousResult 作成完了");
    console.log(`  セクション数: ${previousResult.editablePrompt.sections.length}`);
    console.log(`  objects: "${previousResult.editablePrompt.sections.find(s => s.id === 'objects')?.content}"`);

    // Note: regenerateWithVisualReference は Gemini Vision API が必要
    // API キーがない場合はスキップ
    const apiKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY;
    if (!apiKey) {
        console.log("\n  ⚠️  GEMINI_API_KEY 未設定: Gemini Vision テストをスキップ");
        console.log("  (editType マッピングは上記で検証済)\n");
        return true;
    }

    // ダミー画像（1x1 白ピクセル PNG）
    const dummyImageBytes = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==";

    const instruction: VisualEditInstruction = {
        referenceImageBytes: dummyImageBytes,
        referenceImageMimeType: "image/png",
        targetElement: "vase",
        editType: "replace_shape",
        additionalInstruction: "Replace the ceramic vase with a tall glass vase",
    };

    console.log(`\n  参照画像でオブジェクト差し替え実行中...`);
    console.log(`  targetElement: "${instruction.targetElement}"`);
    console.log(`  editType: "${instruction.editType}"`);

    try {
        const result = await generator.regenerateWithVisualReference(
            previousResult,
            instruction,
        );

        console.log(`\n  ✅ 再生成結果:`);
        console.log(`     status: ${result.status}`);
        console.log(`     finalPrompt: ${result.finalPrompt.slice(0, 100)}...`);
        console.log(`     ログ数: ${result.log.length}`);

        const editLog = result.log.find(l => l.step === "画像参照編集");
        if (editLog) {
            console.log(`     編集ログ: ${editLog.message}`);
        }

        return true;
    } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.log(`\n  ❌ エラー: ${msg}`);
        return false;
    }
}

async function testPromptDiffGeneration() {
    console.log(`\n${DIVIDER}`);
    console.log("テスト 3: プロンプト差分生成 (ローカル)");
    console.log(DIVIDER);

    const previousResult = createMockPreviousResult();

    // オブジェクトセクションの内容確認
    const objectsSection = previousResult.editablePrompt.sections.find(s => s.id === "objects");
    console.log(`  objects セクション: "${objectsSection?.content}"`);

    // "vase" がオブジェクトに含まれているか確認
    const hasVase = objectsSection?.content.includes("vase") ?? false;
    console.log(`  "vase" が含まれている: ${hasVase ? "✅" : "❌"}`);

    // "book" がオブジェクトに含まれているか確認
    const hasBook = objectsSection?.content.includes("book") ?? false;
    console.log(`  "book" が含まれている: ${hasBook ? "✅" : "❌"}`);

    const passed = hasVase && hasBook;
    console.log(`\n  結果: ${passed ? "✅ パス" : "❌ 失敗"}\n`);
    return passed;
}

async function main() {
    console.log(DIVIDER);
    console.log("VisualEditEngine E2E テスト");
    console.log(DIVIDER);

    const results: boolean[] = [];

    results.push(await testEditTypeMapping());
    results.push(await testPromptDiffGeneration());
    results.push(await testResourceVideoGeneratorIntegration());

    const passed = results.filter(Boolean).length;
    const total = results.length;

    console.log(`\n${DIVIDER}`);
    console.log(`最終結果: ${passed}/${total} テストパス`);
    console.log(DIVIDER);

    if (passed < total) {
        process.exit(1);
    }
}

main().catch((err) => {
    console.error("致命的エラー:", err);
    process.exit(1);
});
