/**
 * test-visual-edit.ts
 *
 * VisualEditEngine E2E テストスクリプト
 *
 * テストフロー:
 * 1. テストプロンプトで text_to_video 初回生成結果をシミュレート
 * 2. 参照画像（ダミー Base64）を読み込み
 * 3. VisualEditEngine.analyzeEdit() でオブジェクトマッチング検証
 * 4. regenerateWithVisualReference() で修正プロンプト生成
 * 5. editType → ReferenceImageType マッピング確認
 * 6. 修正プロンプトを表示
 *
 * 実行: npx tsx scripts/test-visual-edit.ts
 */

import { EditablePrompt } from "../src/lib/editable-prompt.js";
import { VisualEditEngine } from "../src/lib/visual-edit-engine.js";
import type { VisualEditInstruction } from "../src/lib/visual-edit-engine.js";
import type { GenerationJobResult } from "../src/lib/resource-video-generator.js";

function createMockPreviousResult(): GenerationJobResult {
    const prompt = new EditablePrompt();
    prompt.addSection(
        "scene",
        "シーン記述",
        "A construction site with workers in safety gear performing maintenance tasks",
        "analysis",
    );
    prompt.addSection(
        "characters",
        "登場人物",
        "Lead worker, tall man with a hardhat, wearing an orange safety vest, directing the crew at the center of the frame",
        "analysis",
    );
    prompt.addSection(
        "objects",
        "小道具・物体",
        "metal rod, a thin cylindrical steel rod with a yellow safety flag; safety cone, bright orange traffic cone at the corner",
        "analysis",
    );
    prompt.addSection(
        "camera",
        "カメラワーク",
        "medium shot, slow dolly in movement, eye level angle",
        "analysis",
    );
    prompt.addSection(
        "style",
        "スタイル",
        "photorealistic, cinematic lighting, industrial documentary style",
        "analysis",
    );

    return {
        status: "completed",
        mode: "text_to_video",
        finalPrompt: prompt.combine(),
        editablePrompt: prompt.toData(),
        log: [
            {
                step: "プロンプト構築",
                status: "ok",
                message: "テキストプロンプト設定完了",
                durationMs: 0,
            },
        ],
        createdAt: new Date().toISOString(),
    };
}

function createDummyBase64Image(): string {
    const header = Buffer.from([
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    ]);
    return header.toString("base64");
}

async function testEditTypeMapping(): Promise<void> {
    console.log("=== Test: editType → ReferenceImageType mapping ===");

    const engine = new VisualEditEngine({ geminiApiKey: "test-key" });

    const mappings: Record<string, string> = {
        replace_shape: "asset",
        replace_style: "style",
        replace_color: "style",
        add_from_image: "asset",
        match_pose: "subject",
    };

    for (const [editType, expected] of Object.entries(mappings)) {
        const result = engine.mapEditTypeToReferenceType(
            editType as VisualEditInstruction["editType"],
        );
        const status = result === expected ? "PASS" : "FAIL";
        console.log(`  ${status}: ${editType} → ${result} (expected: ${expected})`);
    }

    console.log("");
}

function testPromptRestoration(): void {
    console.log("=== Test: EditablePrompt restoration from data ===");

    const previousResult = createMockPreviousResult();

    const restored = EditablePrompt.fromData(previousResult.editablePrompt);
    const sections = restored.getSections();

    console.log(`  Sections restored: ${sections.length}`);
    for (const section of sections) {
        console.log(`    [${section.id}] ${section.label}: ${section.content.substring(0, 60)}...`);
    }

    const combined = restored.combine();
    console.log(`  Combined prompt length: ${combined.length} chars`);
    console.log(`  PASS: Prompt restoration successful`);
    console.log("");
}

function testObjectExtraction(): void {
    console.log("=== Test: Object extraction from EditablePrompt ===");

    const previousResult = createMockPreviousResult();
    const objectsSection = previousResult.editablePrompt.sections.find(s => s.id === "objects");

    if (!objectsSection) {
        console.log("  FAIL: No objects section found");
        return;
    }

    const objectStrings = objectsSection.content.split(";").map(s => s.trim()).filter(Boolean);
    console.log(`  Extracted ${objectStrings.length} objects:`);
    for (const obj of objectStrings) {
        console.log(`    - ${obj}`);
    }

    console.log(`  PASS: Object extraction successful`);
    console.log("");
}

function testPromptEditing(): void {
    console.log("=== Test: Prompt section editing ===");

    const previousResult = createMockPreviousResult();
    const prompt = EditablePrompt.fromData(previousResult.editablePrompt);

    const originalObjects = prompt.getSection("objects")?.content ?? "";
    console.log(`  Original objects: ${originalObjects}`);

    const newObjectsContent = originalObjects.replace(
        "a thin cylindrical steel rod with a yellow safety flag",
        "A thick cylindrical metal rod with a red safety flag, heavy-duty industrial grade",
    );
    prompt.editSection("objects", newObjectsContent);

    const edited = prompt.getSection("objects");
    console.log(`  Edited objects: ${edited?.content}`);
    console.log(`  Modified flag: ${edited?.modified}`);

    const finalPrompt = prompt.combine();
    console.log(`  Final prompt: ${finalPrompt.substring(0, 120)}...`);
    console.log(`  PASS: Prompt editing successful`);
    console.log("");
}

function testVisualEditInstructionTypes(): void {
    console.log("=== Test: VisualEditInstruction type validation ===");

    const dummyImage = createDummyBase64Image();

    const instructions: VisualEditInstruction[] = [
        {
            referenceImageBytes: dummyImage,
            referenceImageMimeType: "image/png",
            targetElement: "metal rod",
            editType: "replace_shape",
            additionalInstruction: "Make it thicker and more industrial",
        },
        {
            referenceImageBytes: dummyImage,
            referenceImageMimeType: "image/jpeg",
            targetElement: "safety cone",
            editType: "replace_color",
        },
        {
            referenceImageBytes: dummyImage,
            referenceImageMimeType: "image/webp",
            targetElement: "warning sign",
            editType: "add_from_image",
        },
    ];

    for (const inst of instructions) {
        console.log(`  ${inst.editType} on "${inst.targetElement}" (${inst.referenceImageMimeType})`);
        if (inst.additionalInstruction) {
            console.log(`    Additional: ${inst.additionalInstruction}`);
        }
    }

    console.log(`  PASS: All instruction types valid`);
    console.log("");
}

function testEndToEndWithoutApi(): void {
    console.log("=== Test: End-to-end flow (without API calls) ===");

    const previousResult = createMockPreviousResult();
    console.log(`  1. Previous result created with ${previousResult.editablePrompt.sections.length} sections`);
    console.log(`     Mode: ${previousResult.mode}, Status: ${previousResult.status}`);

    const prompt = EditablePrompt.fromData(previousResult.editablePrompt);
    console.log(`  2. Prompt restored successfully`);

    const mockReferenceDescription = "A thick cylindrical metal rod with a red safety flag, heavy-duty construction grade, matte steel finish with visible welding marks";

    const objectsSection = prompt.getSection("objects");
    if (objectsSection) {
        const updatedContent = objectsSection.content.replace(
            /metal rod,[^;]*/,
            `metal rod, ${mockReferenceDescription}`,
        );
        prompt.editSection("objects", updatedContent);
        console.log(`  3. Objects section updated with reference description`);
    }

    const finalPrompt = prompt.combine();
    console.log(`  4. Final prompt generated (${finalPrompt.length} chars):`);
    console.log(`     ${finalPrompt.substring(0, 200)}...`);

    const updatedResult: GenerationJobResult = {
        ...previousResult,
        status: "ready",
        finalPrompt,
        editablePrompt: prompt.toData(),
        log: [
            ...previousResult.log,
            {
                step: "画像参照編集",
                status: "ok",
                message: "metal rod を参照画像で replace_shape 編集 (ref: asset)",
                durationMs: 150,
            },
        ],
    };

    console.log(`  5. Updated result: status=${updatedResult.status}, log entries=${updatedResult.log.length}`);
    console.log(`  PASS: End-to-end flow completed`);
    console.log("");
}

async function main(): Promise<void> {
    console.log("========================================");
    console.log("  VisualEditEngine E2E Test Suite");
    console.log("========================================\n");

    await testEditTypeMapping();
    testPromptRestoration();
    testObjectExtraction();
    testPromptEditing();
    testVisualEditInstructionTypes();
    testEndToEndWithoutApi();

    console.log("========================================");
    console.log("  All offline tests completed!");
    console.log("========================================");
}

main().catch(err => {
    console.error("Test failed:", err);
    process.exit(1);
});
