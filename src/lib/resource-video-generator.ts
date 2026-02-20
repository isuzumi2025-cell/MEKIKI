/**
 * resource-video-generator.ts
 *
 * リソースベース動画生成エンジン — リソース解析結果から動画を生成する
 * ResourceAnalyzer → EditablePrompt → VeoClient のパイプラインを統合管理。
 *
 * FlowForge SDK — Generation Layer
 */

import { ResourceAnalyzer, type ResourceInput, type AnalysisResult } from "./resource-analyzer.js";
import { EditablePrompt, type EditablePromptData } from "./editable-prompt.js";
import { VeoClient, type VeoGenerationResult, type VeoReferenceImage } from "./veo-client.js";
import type { VisualEditInstruction } from "./visual-edit-engine.js";

export type GenerationMode = "text_to_video" | "image_to_video" | "resource_to_video";

export interface GenerationStep {
    step: string;
    status: "ok" | "error" | "skipped";
    message: string;
    durationMs: number;
}

export interface GenerationJobResult {
    status: "ready" | "generating" | "completed" | "failed";
    mode: GenerationMode;
    finalPrompt: string;
    editablePrompt: EditablePromptData;
    analysis?: AnalysisResult;
    videoResult?: VeoGenerationResult;
    referenceImages?: VeoReferenceImage[];
    log: GenerationStep[];
    createdAt: string;
}

export interface ResourceVideoGeneratorOptions {
    geminiApiKey?: string;
    veoModel?: "veo-3.1-generate-preview" | "veo-3.1-fast-generate-preview" | "veo-2-generate-001";
}

export class ResourceVideoGenerator {
    private analyzer: ResourceAnalyzer;
    private veoClient: VeoClient;

    constructor(options?: ResourceVideoGeneratorOptions) {
        const apiKey = options?.geminiApiKey
            ?? process.env.GOOGLE_API_KEY
            ?? process.env.GEMINI_API_KEY ?? "";

        this.analyzer = new ResourceAnalyzer({ geminiApiKey: apiKey });
        this.veoClient = new VeoClient({
            apiKey,
            defaultModel: options?.veoModel ?? "veo-3.1-generate-preview",
        });
    }

    async generateFromResource(resource: ResourceInput): Promise<GenerationJobResult> {
        const log: GenerationStep[] = [];
        const startTime = Date.now();

        let analysis: AnalysisResult;
        try {
            analysis = await this.analyzer.analyze(resource);
            log.push({
                step: "リソース解析",
                status: "ok",
                message: `${resource.type} 解析完了`,
                durationMs: Date.now() - startTime,
            });
        } catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            log.push({
                step: "リソース解析",
                status: "error",
                message,
                durationMs: Date.now() - startTime,
            });
            return this.buildFailedResult("resource_to_video", log, message);
        }

        const prompt = new EditablePrompt();
        prompt.addSection("scene", "シーン記述", analysis.sceneDescription, "analysis");

        if (analysis.characters.length > 0) {
            const charDesc = analysis.characters
                .map(c => [c.name, c.appearance].filter(Boolean).join(", "))
                .join("; ");
            prompt.addSection("characters", "登場人物", charDesc, "analysis");
        }

        if (analysis.objects.length > 0) {
            const objDesc = analysis.objects
                .map(o => [o.name, o.description].filter(Boolean).join(", "))
                .join("; ");
            prompt.addSection("objects", "小道具・物体", objDesc, "analysis");
        }

        if (analysis.style) {
            prompt.addSection("style", "スタイル", analysis.style, "analysis");
        }

        if (analysis.suggestedCamera) {
            prompt.addSection("camera", "カメラワーク", analysis.suggestedCamera, "analysis");
        }

        const finalPrompt = prompt.combine();

        log.push({
            step: "プロンプト構築",
            status: "ok",
            message: `${prompt.getSections().length} セクション構築`,
            durationMs: Date.now() - startTime,
        });

        return {
            status: "ready",
            mode: "resource_to_video",
            finalPrompt,
            editablePrompt: prompt.toData(),
            analysis,
            log,
            createdAt: new Date().toISOString(),
        };
    }

    async generateFromText(promptText: string): Promise<GenerationJobResult> {
        const log: GenerationStep[] = [];
        const prompt = new EditablePrompt();
        prompt.addSection("main", "メインプロンプト", promptText, "manual");
        const finalPrompt = prompt.combine();

        log.push({
            step: "プロンプト構築",
            status: "ok",
            message: "テキストプロンプト設定完了",
            durationMs: 0,
        });

        return {
            status: "ready",
            mode: "text_to_video",
            finalPrompt,
            editablePrompt: prompt.toData(),
            log,
            createdAt: new Date().toISOString(),
        };
    }

    async executeGeneration(
        job: GenerationJobResult,
        referenceImages?: VeoReferenceImage[],
    ): Promise<GenerationJobResult> {
        const startTime = Date.now();

        try {
            const videoResult = await this.veoClient.generateVideo({
                prompt: job.finalPrompt,
                referenceImages,
            });

            job.log.push({
                step: "動画生成",
                status: videoResult.status === "completed" ? "ok" : "error",
                message: videoResult.status === "completed"
                    ? "動画生成完了"
                    : (videoResult.error ?? "生成失敗"),
                durationMs: Date.now() - startTime,
            });

            return {
                ...job,
                status: videoResult.status === "completed" ? "completed" : "failed",
                videoResult,
            };
        } catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            job.log.push({
                step: "動画生成",
                status: "error",
                message,
                durationMs: Date.now() - startTime,
            });
            return { ...job, status: "failed" };
        }
    }

    async regenerateWithEdit(
        previousResult: GenerationJobResult,
        editedSections: Record<string, string>,
    ): Promise<GenerationJobResult> {
        const prompt = new EditablePrompt();
        for (const section of previousResult.editablePrompt.sections) {
            prompt.addSection(section.id, section.label, section.content, section.source);
        }

        for (const [id, content] of Object.entries(editedSections)) {
            prompt.editSection(id, content);
        }

        const finalPrompt = prompt.combine();

        return {
            ...previousResult,
            status: "ready",
            finalPrompt,
            editablePrompt: prompt.toData(),
            log: [
                ...previousResult.log,
                {
                    step: "手動編集",
                    status: "ok",
                    message: `${Object.keys(editedSections).length} セクション編集`,
                    durationMs: 0,
                },
            ],
        };
    }

    async regenerateWithVisualReference(
        previousResult: GenerationJobResult,
        instruction: VisualEditInstruction,
    ): Promise<GenerationJobResult> {
        const { VisualEditEngine } = await import("./visual-edit-engine.js");
        const engine = new VisualEditEngine({
            geminiApiKey: process.env.GOOGLE_API_KEY ?? process.env.GEMINI_API_KEY ?? "",
        });

        const editedJob = await engine.regenerateWithVisualReference(previousResult, instruction);

        const referenceType = engine.mapEditTypeToReferenceType(instruction.editType);
        const referenceImages: VeoReferenceImage[] = [{
            imageBytes: instruction.referenceImageBytes,
            mimeType: instruction.referenceImageMimeType,
            referenceType,
        }];

        return {
            ...editedJob,
            referenceImages,
        };
    }

    private buildFailedResult(
        mode: GenerationMode,
        log: GenerationStep[],
        error: string,
    ): GenerationJobResult {
        const prompt = new EditablePrompt();
        return {
            status: "failed",
            mode,
            finalPrompt: "",
            editablePrompt: prompt.toData(),
            log,
            createdAt: new Date().toISOString(),
        };
    }
}
