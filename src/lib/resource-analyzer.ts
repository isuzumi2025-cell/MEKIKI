/**
 * resource-analyzer.ts
 *
 * リソース解析エンジン — 画像・動画・URL を分析し
 * EditablePrompt に変換する Gemini マルチモーダル解析ツール
 *
 * FlowForge SDK — Analysis Layer
 */

import * as fs from "fs";
import * as path from "path";
import { EditablePrompt } from "./editable-prompt.js";
import type { CharacterDetail, ObjectDetail } from "./flow-prompt-builder.js";

export type ResourceType = "image" | "video" | "url";

export interface ResourceInput {
    type: ResourceType;
    source: string;
    metadata?: Record<string, unknown>;
}

export interface AnalysisResult {
    sceneDescription: string;
    characters: CharacterDetail[];
    objects: ObjectDetail[];
    style: string;
    mood: string;
    dominantColors: string[];
    detectedTexts: { text: string; confidence: number; bounds: number[] }[];
    suggestedCamera: string;
    rawResponse?: string;
}

interface GeminiResponse {
    candidates?: {
        content?: {
            parts?: { text?: string }[];
        };
    }[];
}

export interface ResourceAnalyzerOptions {
    geminiApiKey?: string;
    detail?: "quick" | "standard" | "deep";
}

export class ResourceAnalyzer {
    private readonly geminiApiKey: string;
    private readonly detail: "quick" | "standard" | "deep";

    constructor(options?: ResourceAnalyzerOptions) {
        const key = options?.geminiApiKey
            ?? (typeof process !== "undefined" ? process.env.GEMINI_API_KEY : undefined);

        if (!key) {
            throw new Error("Gemini API キーが必要です。GEMINI_API_KEY を設定してください。");
        }
        this.geminiApiKey = key;
        this.detail = options?.detail ?? "standard";
    }

    async analyzeToPrompt(resource: ResourceInput): Promise<EditablePrompt> {
        const analysis = await this.analyze(resource);
        return this.analysisToPrompt(analysis);
    }

    async analyze(resource: ResourceInput): Promise<AnalysisResult> {
        switch (resource.type) {
            case "image":
                return this.analyzeImage(resource.source);
            case "video":
                return this.analyzeVideo(resource.source);
            case "url":
                return this.analyzeUrl(resource.source);
            default:
                throw new Error(`未対応のリソースタイプ: ${resource.type}`);
        }
    }

    async analyzeMultiple(resources: ResourceInput[]): Promise<EditablePrompt> {
        const analyses = await Promise.all(
            resources.map(r => this.analyze(r))
        );
        const merged = this.mergeAnalyses(analyses);
        return this.analysisToPrompt(merged);
    }

    private async analyzeImage(imagePath: string): Promise<AnalysisResult> {
        const absPath = path.resolve(imagePath);
        if (!fs.existsSync(absPath)) {
            throw new Error(`画像ファイルが見つかりません: ${absPath}`);
        }

        const imageData = fs.readFileSync(absPath);
        const base64 = imageData.toString("base64");
        const mimeType = this.getMimeType(absPath);

        const prompt = this.buildAnalysisPrompt();

        const url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent";

        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "x-goog-api-key": this.geminiApiKey,
            },
            body: JSON.stringify({
                contents: [{
                    parts: [
                        { text: prompt },
                        { inlineData: { mimeType, data: base64 } },
                    ],
                }],
                generationConfig: {
                    temperature: 0.3,
                    maxOutputTokens: 2048,
                },
            }),
        });

        if (!res.ok) {
            throw new Error(`Gemini API エラー: ${res.status} ${res.statusText}`);
        }

        const json = (await res.json()) as GeminiResponse;
        return this.parseAnalysisResponse(json);
    }

    private async analyzeVideo(_videoPath: string): Promise<AnalysisResult> {
        throw new Error("動画解析は現在未実装です。画像解析をご利用ください。");
    }

    private async analyzeUrl(_url: string): Promise<AnalysisResult> {
        throw new Error("URL 解析は現在未実装です。画像解析をご利用ください。");
    }

    buildAnalysisPrompt(): string {
        const detailInstructions: Record<string, string> = {
            quick: "Provide a brief analysis focusing on main subjects and actions.",
            standard: "Provide a detailed analysis covering all visual elements.",
            deep: "Provide an exhaustive analysis with fine-grained details about every visual element, texture, lighting, and composition.",
        };

        return `Analyze this image for video generation. ${detailInstructions[this.detail]}

Return a JSON object with this exact structure:
{
  "sceneDescription": "A detailed description of the overall scene",
  "characters": [
    {
      "name": "descriptive identifier",
      "role": "their role in the scene",
      "appearance": "physical description",
      "clothing": "what they are wearing",
      "action": "what they are doing",
      "position": "where in the frame"
    }
  ],
  "objects": [
    {
      "name": "object name",
      "description": "detailed description",
      "material": "material/texture",
      "color": "color description",
      "scale": "relative size",
      "position": "location in scene",
      "keyFeatures": ["distinctive feature 1", "distinctive feature 2"]
    }
  ],
  "style": "visual style description",
  "mood": "emotional tone",
  "dominantColors": ["color1", "color2"],
  "detectedTexts": [
    { "text": "any visible text", "confidence": 0.95, "bounds": [0, 0, 100, 100] }
  ],
  "suggestedCamera": "recommended camera movement for video"
}

All descriptions should be in English, optimized for Veo 3.1 video generation prompts.
Return ONLY valid JSON, no markdown formatting.`;
    }

    async analyzeInlineImage(
        base64Data: string,
        mimeType: string,
        prompt: string,
    ): Promise<string> {
        const url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent";

        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "x-goog-api-key": this.geminiApiKey,
            },
            body: JSON.stringify({
                contents: [{
                    parts: [
                        { text: prompt },
                        { inlineData: { mimeType, data: base64Data } },
                    ],
                }],
                generationConfig: {
                    temperature: 0.3,
                    maxOutputTokens: 2048,
                },
            }),
        });

        if (!res.ok) {
            throw new Error(`Gemini API エラー: ${res.status} ${res.statusText}`);
        }

        const json = (await res.json()) as GeminiResponse;
        const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
        if (!text) {
            throw new Error("Gemini API からテキスト応答がありませんでした");
        }
        return text;
    }

    private parseAnalysisResponse(response: GeminiResponse): AnalysisResult {
        const rawText = response.candidates?.[0]?.content?.parts?.[0]?.text;

        if (!rawText) {
            throw new Error("Gemini API からの応答が空です");
        }

        const cleanJson = rawText
            .replace(/```json\s*/g, "")
            .replace(/```\s*/g, "")
            .trim();

        const parsed = JSON.parse(cleanJson) as AnalysisResult & {
            objects?: (ObjectDetail & { keyFeatures?: string[] })[];
        };

        return {
            sceneDescription: parsed.sceneDescription ?? "",
            characters: parsed.characters ?? [],
            objects: (parsed.objects ?? []).map(o => ({
                name: o.name ?? "",
                description: o.description ?? "",
                material: o.material,
                color: o.color,
                scale: o.scale,
                position: o.position,
                keyFeatures: o.keyFeatures,
            })),
            style: parsed.style ?? "",
            mood: parsed.mood ?? "",
            dominantColors: parsed.dominantColors ?? [],
            detectedTexts: parsed.detectedTexts ?? [],
            suggestedCamera: parsed.suggestedCamera ?? "",
            rawResponse: rawText,
        };
    }

    private analysisToPrompt(analysis: AnalysisResult): EditablePrompt {
        const prompt = new EditablePrompt();

        prompt.addSection("scene", "シーン記述", analysis.sceneDescription, "analysis");

        if (analysis.characters.length > 0) {
            const charDesc = analysis.characters
                .map(c => {
                    const parts = [c.name];
                    if (c.role) parts.push(`(${c.role})`);
                    parts.push(c.appearance);
                    if (c.clothing) parts.push(`wearing ${c.clothing}`);
                    if (c.action) parts.push(c.action);
                    return parts.join(", ");
                })
                .join("; ");
            prompt.addSection("characters", "登場人物", charDesc, "analysis");
        }

        if (analysis.objects.length > 0) {
            const objDesc = analysis.objects
                .map(o => {
                    const parts = [o.name, o.description];
                    if (o.material) parts.push(`made of ${o.material}`);
                    if (o.color) parts.push(o.color);
                    return parts.join(", ");
                })
                .join("; ");
            prompt.addSection("objects", "小道具・物体", objDesc, "analysis");
        }

        if (analysis.style) {
            prompt.addSection("style", "スタイル", analysis.style, "analysis");
        }

        if (analysis.mood) {
            prompt.addSection("mood", "ムード", analysis.mood, "analysis");
        }

        if (analysis.suggestedCamera) {
            prompt.addSection("camera", "カメラワーク", analysis.suggestedCamera, "analysis");
        }

        return prompt;
    }

    private mergeAnalyses(analyses: AnalysisResult[]): AnalysisResult {
        const merged: AnalysisResult = {
            sceneDescription: analyses.map(a => a.sceneDescription).join(". "),
            characters: analyses.flatMap(a => a.characters),
            objects: analyses.flatMap(a => a.objects),
            style: analyses.map(a => a.style).filter(Boolean).join(", "),
            mood: analyses.map(a => a.mood).filter(Boolean).join(", "),
            dominantColors: [...new Set(analyses.flatMap(a => a.dominantColors))],
            detectedTexts: analyses.flatMap(a => a.detectedTexts),
            suggestedCamera: analyses.map(a => a.suggestedCamera).filter(Boolean)[0] ?? "",
        };
        return merged;
    }

    private getMimeType(filePath: string): string {
        const ext = path.extname(filePath).toLowerCase();
        const mimeMap: Record<string, string> = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        };
        return mimeMap[ext] ?? "image/jpeg";
    }
}
