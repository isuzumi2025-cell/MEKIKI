/**
 * visual-edit-engine.ts
 *
 * VisualEditEngine — 参照画像ベースの動画オブジェクト差し替えエンジン
 *
 * ユーザーが動画生成後に参照画像を提示し、特定オブジェクトの形状・スタイル・色を
 * 差し替えて再生成するワークフローを提供する。
 *
 * FlowForge SDK — Visual Edit Layer
 */

import { ResourceAnalyzer, type AnalysisResult } from "./resource-analyzer.js";
import { EditablePrompt, type EditablePromptData } from "./editable-prompt.js";
import type { ObjectDetail } from "./flow-prompt-builder.js";
import type { GenerationJobResult } from "./resource-video-generator.js";
import type { ReferenceImageType } from "./veo-client.js";

export interface VisualEditInstruction {
    referenceImageBytes: string;
    referenceImageMimeType: "image/png" | "image/jpeg" | "image/webp";
    targetElement: string;
    editType: "replace_shape" | "replace_style" | "replace_color" | "add_from_image" | "match_pose";
    additionalInstruction?: string;
}

export interface ReferenceObjectDescription {
    description: string;
    keyFeatures: string[];
}

export interface VisualEditAnalysis {
    referenceObjects: ObjectDetail[];
    targetObjects: ObjectDetail[];
    matchedPairs: [ObjectDetail, ObjectDetail][];
    editPromptDiff: string;
    referenceDescription: string;
}

interface GeminiResponse {
    candidates?: {
        content?: {
            parts?: { text?: string }[];
        };
    }[];
}

const EDIT_TYPE_TO_REFERENCE_TYPE: Record<VisualEditInstruction["editType"], ReferenceImageType> = {
    replace_shape: "asset",
    replace_style: "style",
    replace_color: "style",
    add_from_image: "asset",
    match_pose: "subject",
};

export class VisualEditEngine {
    private analyzer: ResourceAnalyzer;
    private geminiApiKey: string;

    constructor(options?: { geminiApiKey?: string }) {
        this.geminiApiKey = options?.geminiApiKey
            ?? process.env.GOOGLE_API_KEY
            ?? process.env.GEMINI_API_KEY ?? "";
        this.analyzer = new ResourceAnalyzer({ geminiApiKey: this.geminiApiKey });
    }

    async analyzeEdit(
        previousResult: GenerationJobResult,
        instruction: VisualEditInstruction,
    ): Promise<VisualEditAnalysis> {
        const referenceDesc = await this.describeObjectForVeo(
            instruction.referenceImageBytes,
            instruction.referenceImageMimeType,
            instruction.targetElement,
        );

        const referenceObjects = this.buildReferenceObjects(referenceDesc, instruction.targetElement);

        const targetObjects = this.extractTargetObjects(previousResult.editablePrompt);

        const matchedPairs = this.matchObjects(
            targetObjects,
            referenceObjects,
            instruction.targetElement,
        );

        const editPromptDiff = this.buildEditPromptDiff(
            matchedPairs,
            referenceDesc,
            instruction,
        );

        return {
            referenceObjects,
            targetObjects,
            matchedPairs,
            editPromptDiff,
            referenceDescription: referenceDesc.description,
        };
    }

    async regenerateWithVisualReference(
        previousResult: GenerationJobResult,
        instruction: VisualEditInstruction,
    ): Promise<GenerationJobResult> {
        const startTime = Date.now();
        const analysis = await this.analyzeEdit(previousResult, instruction);

        const prompt = EditablePrompt.fromData(previousResult.editablePrompt);

        this.applyVisualEdit(prompt, analysis, instruction);

        const finalPrompt = prompt.combine();

        const referenceType = EDIT_TYPE_TO_REFERENCE_TYPE[instruction.editType];

        return {
            ...previousResult,
            status: "ready",
            finalPrompt,
            editablePrompt: prompt.toData(),
            log: [
                ...previousResult.log,
                {
                    step: "画像参照編集",
                    status: "ok",
                    message: `${instruction.targetElement} を参照画像で ${instruction.editType} 編集 (ref: ${referenceType})`,
                    durationMs: Date.now() - startTime,
                },
            ],
        };
    }

    mapEditTypeToReferenceType(editType: VisualEditInstruction["editType"]): ReferenceImageType {
        return EDIT_TYPE_TO_REFERENCE_TYPE[editType];
    }

    private async describeObjectForVeo(
        imageBytes: string,
        mimeType: string,
        targetElement: string,
    ): Promise<ReferenceObjectDescription> {
        const prompt = `Analyze the "${targetElement}" in this image. Provide:
1. Shape and form factor
2. Material and texture
3. Color and finish
4. Scale relative to surroundings
5. Distinctive details

Output as JSON: { "description": "...", "keyFeatures": ["..."] }
The description should be optimized for Veo 3.1 video generation prompts.
Return ONLY valid JSON, no markdown formatting.`;

        const rawResponse = await this.callGeminiVision(imageBytes, mimeType, prompt);

        const cleanJson = rawResponse
            .replace(/```json\s*/g, "")
            .replace(/```\s*/g, "")
            .trim();

        const parsed = JSON.parse(cleanJson) as ReferenceObjectDescription;

        return {
            description: parsed.description ?? "",
            keyFeatures: parsed.keyFeatures ?? [],
        };
    }

    private async callGeminiVision(
        imageBytes: string,
        mimeType: string,
        prompt: string,
    ): Promise<string> {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${this.geminiApiKey}`;

        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                contents: [{
                    parts: [
                        { text: prompt },
                        { inlineData: { mimeType, data: imageBytes } },
                    ],
                }],
                generationConfig: {
                    temperature: 0.3,
                    maxOutputTokens: 2048,
                },
            }),
        });

        if (!res.ok) {
            throw new Error(`Gemini Vision API エラー: ${res.status} ${res.statusText}`);
        }

        const json = (await res.json()) as GeminiResponse;
        const text = json.candidates?.[0]?.content?.parts?.[0]?.text;

        if (!text) {
            throw new Error("Gemini Vision API からテキスト応答がありませんでした");
        }

        return text;
    }

    private buildReferenceObjects(
        desc: ReferenceObjectDescription,
        targetElement: string,
    ): ObjectDetail[] {
        return [{
            name: targetElement,
            description: desc.description,
            keyFeatures: desc.keyFeatures,
        }];
    }

    private extractTargetObjects(editablePrompt: EditablePromptData): ObjectDetail[] {
        const objectsSection = editablePrompt.sections.find(s => s.id === "objects");
        if (!objectsSection) {
            return [];
        }

        const objectStrings = objectsSection.content.split(";").map(s => s.trim()).filter(Boolean);
        return objectStrings.map(s => {
            const parts = s.split(",").map(p => p.trim());
            return {
                name: parts[0] ?? s,
                description: parts.slice(1).join(", ") || s,
            };
        });
    }

    private matchObjects(
        targetObjects: ObjectDetail[],
        referenceObjects: ObjectDetail[],
        targetElement: string,
    ): [ObjectDetail, ObjectDetail][] {
        const pairs: [ObjectDetail, ObjectDetail][] = [];
        const normalizedTarget = targetElement.toLowerCase();

        for (const target of targetObjects) {
            const normalizedName = target.name.toLowerCase();
            const normalizedDesc = target.description.toLowerCase();

            if (
                normalizedName.includes(normalizedTarget) ||
                normalizedDesc.includes(normalizedTarget) ||
                normalizedTarget.includes(normalizedName)
            ) {
                for (const ref of referenceObjects) {
                    pairs.push([target, ref]);
                }
            }
        }

        if (pairs.length === 0 && referenceObjects.length > 0) {
            const bestMatch = targetObjects[0];
            if (bestMatch) {
                pairs.push([bestMatch, referenceObjects[0]]);
            }
        }

        return pairs;
    }

    private buildEditPromptDiff(
        matchedPairs: [ObjectDetail, ObjectDetail][],
        referenceDesc: ReferenceObjectDescription,
        instruction: VisualEditInstruction,
    ): string {
        if (matchedPairs.length === 0) {
            return `Add ${instruction.targetElement}: ${referenceDesc.description}`;
        }

        const diffs: string[] = [];
        for (const [existing, replacement] of matchedPairs) {
            switch (instruction.editType) {
                case "replace_shape":
                    diffs.push(
                        `Replace the shape of ${existing.name} with: ${replacement.description}`
                    );
                    break;
                case "replace_style":
                    diffs.push(
                        `Restyle ${existing.name} to match: ${replacement.description}`
                    );
                    break;
                case "replace_color":
                    diffs.push(
                        `Change the color of ${existing.name} to match: ${replacement.description}`
                    );
                    break;
                case "add_from_image":
                    diffs.push(
                        `Add ${replacement.name}: ${replacement.description}`
                    );
                    break;
                case "match_pose":
                    diffs.push(
                        `Match the pose/position of ${existing.name} to: ${replacement.description}`
                    );
                    break;
            }
        }

        if (instruction.additionalInstruction) {
            diffs.push(instruction.additionalInstruction);
        }

        return diffs.join(". ");
    }

    private applyVisualEdit(
        prompt: EditablePrompt,
        analysis: VisualEditAnalysis,
        instruction: VisualEditInstruction,
    ): void {
        if (instruction.editType === "add_from_image") {
            const existingObjects = prompt.getSection("objects");
            const newContent = existingObjects
                ? `${existingObjects.content}; ${analysis.referenceDescription}`
                : analysis.referenceDescription;
            if (existingObjects) {
                prompt.editSection("objects", newContent);
            } else {
                prompt.addSection("objects", "小道具・物体", newContent, "refined");
            }
            return;
        }

        if (analysis.matchedPairs.length > 0) {
            const objectsSection = prompt.getSection("objects");
            if (objectsSection) {
                let updatedContent = objectsSection.content;

                for (const [existing, replacement] of analysis.matchedPairs) {
                    const existingPattern = existing.name;
                    const existingDesc = existing.description;

                    if (updatedContent.includes(existingPattern) || updatedContent.includes(existingDesc)) {
                        const replacementText = `${replacement.name}, ${replacement.description}`;
                        if (updatedContent.includes(existingDesc)) {
                            updatedContent = updatedContent.replace(existingDesc, replacementText);
                        } else {
                            updatedContent = updatedContent.replace(
                                existingPattern,
                                `${existingPattern} (replaced with: ${replacement.description})`,
                            );
                        }
                    }
                }

                prompt.editSection("objects", updatedContent);
            } else {
                prompt.addSection(
                    "objects",
                    "小道具・物体",
                    analysis.referenceDescription,
                    "refined",
                );
            }
        }

        if (instruction.additionalInstruction) {
            const editNote = prompt.getSection("visual_edit_note");
            if (editNote) {
                prompt.editSection("visual_edit_note", instruction.additionalInstruction);
            } else {
                prompt.addSection(
                    "visual_edit_note",
                    "編集指示",
                    instruction.additionalInstruction,
                    "manual",
                );
            }
        }
    }
}
