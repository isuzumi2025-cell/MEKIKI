import { describe, it, expect } from "vitest";
import type { GenerationJobResult, GenerationStep } from "../resource-video-generator.js";
import type { EditablePromptData } from "../editable-prompt.js";

function makeEditablePromptData(overrides?: Partial<EditablePromptData>): EditablePromptData {
    return {
        sections: [
            {
                id: "scene",
                label: "シーン記述",
                content: "A sunset over the ocean",
                source: "analysis",
                modified: false,
            },
        ],
        combinedPrompt: "A sunset over the ocean.",
        updatedAt: new Date().toISOString(),
        ...overrides,
    };
}

function makeJobResult(overrides?: Partial<GenerationJobResult>): GenerationJobResult {
    return {
        status: "ready",
        mode: "text_to_video",
        finalPrompt: "A sunset over the ocean.",
        editablePrompt: makeEditablePromptData(),
        log: [],
        createdAt: new Date().toISOString(),
        ...overrides,
    };
}

describe("GenerationJobResult structure", () => {
    it("has required fields", () => {
        const result = makeJobResult();
        expect(result.status).toBe("ready");
        expect(result.mode).toBe("text_to_video");
        expect(result.finalPrompt).toBeTruthy();
        expect(result.editablePrompt.sections.length).toBeGreaterThan(0);
        expect(result.log).toEqual([]);
        expect(result.createdAt).toBeTruthy();
    });

    it("supports completed status with videoResult", () => {
        const result = makeJobResult({
            status: "completed",
            videoResult: {
                status: "completed",
                videoUri: "https://example.com/video.mp4",
            },
        });
        expect(result.status).toBe("completed");
        expect(result.videoResult!.videoUri).toBeTruthy();
    });

    it("supports failed status", () => {
        const result = makeJobResult({
            status: "failed",
            videoResult: {
                status: "failed",
                error: "Generation failed",
            },
        });
        expect(result.status).toBe("failed");
        expect(result.videoResult!.error).toBe("Generation failed");
    });

    it("supports referenceImages field", () => {
        const result = makeJobResult({
            referenceImages: [
                {
                    imageBytes: "base64data",
                    mimeType: "image/png",
                    referenceType: "asset",
                },
            ],
        });
        expect(result.referenceImages!.length).toBe(1);
        expect(result.referenceImages![0].referenceType).toBe("asset");
    });

    it("supports all generation modes", () => {
        const modes = ["text_to_video", "image_to_video", "resource_to_video"] as const;
        for (const mode of modes) {
            const result = makeJobResult({ mode });
            expect(result.mode).toBe(mode);
        }
    });
});

describe("GenerationStep structure", () => {
    it("tracks step with status and duration", () => {
        const step: GenerationStep = {
            step: "動画生成",
            status: "ok",
            message: "動画生成完了",
            durationMs: 5000,
        };
        expect(step.status).toBe("ok");
        expect(step.durationMs).toBe(5000);
    });

    it("supports error status", () => {
        const step: GenerationStep = {
            step: "リソース解析",
            status: "error",
            message: "API error",
            durationMs: 100,
        };
        expect(step.status).toBe("error");
    });

    it("supports skipped status", () => {
        const step: GenerationStep = {
            step: "テスト",
            status: "skipped",
            message: "Not applicable",
            durationMs: 0,
        };
        expect(step.status).toBe("skipped");
    });
});

describe("regenerateWithEdit logic (pure data)", () => {
    it("editing a section updates content and marks modified", () => {
        const original = makeJobResult({
            editablePrompt: makeEditablePromptData({
                sections: [
                    { id: "scene", label: "シーン記述", content: "Original scene", source: "analysis", modified: false },
                    { id: "style", label: "スタイル", content: "Original style", source: "manual", modified: false },
                ],
            }),
        });

        const editedSections = { scene: "Updated scene description" };
        const updatedSections = original.editablePrompt.sections.map(s => {
            if (editedSections[s.id as keyof typeof editedSections]) {
                return { ...s, content: editedSections[s.id as keyof typeof editedSections], modified: true };
            }
            return s;
        });

        expect(updatedSections[0].content).toBe("Updated scene description");
        expect(updatedSections[0].modified).toBe(true);
        expect(updatedSections[1].content).toBe("Original style");
        expect(updatedSections[1].modified).toBe(false);
    });

    it("combined prompt updates after section edit", () => {
        const sections = [
            { id: "scene", label: "シーン記述", content: "Updated scene", source: "analysis" as const, modified: true },
            { id: "style", label: "スタイル", content: "cinematic", source: "manual" as const, modified: false },
        ];

        const combined = sections.map(s => s.content.trim()).filter(Boolean).join(". ") + ".";
        expect(combined).toBe("Updated scene. cinematic.");
    });
});

describe("regenerateWithVisualReference structure", () => {
    it("result includes referenceImages after visual edit", () => {
        const result = makeJobResult({
            referenceImages: [
                {
                    imageBytes: "ref-image-data",
                    mimeType: "image/png",
                    referenceType: "style",
                },
            ],
            log: [
                {
                    step: "画像参照編集",
                    status: "ok",
                    message: "car を参照画像で replace_style 編集 (ref: style)",
                    durationMs: 1200,
                },
            ],
        });

        expect(result.referenceImages).toBeDefined();
        expect(result.referenceImages!.length).toBe(1);
        expect(result.log[0].step).toBe("画像参照編集");
    });
});
