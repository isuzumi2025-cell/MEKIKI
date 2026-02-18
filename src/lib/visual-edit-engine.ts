/**
 * visual-edit-engine.ts
 *
 * Gemini Vision を使ったビジュアル編集エンジン。
 * 画像内のオブジェクトを解析し、Veo 動画生成用のプロンプト記述を生成する。
 *
 * describeObjectForVeo パターン:
 * 画像バイナリ + テキストプロンプトを Gemini Vision に送信し、
 * オブジェクトの詳細な視覚的特徴を構造化データとして返す。
 * SubjectRegistry の extractFromResult もこのパターンを参照している。
 */

import { GoogleGenAI } from "@google/genai";
import { withRetry } from "./utils/retry.js";

export interface ObjectDescription {
  name: string;
  appearance: string;
  keyFeatures: string[];
  suggestedPrompt: string;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface DescribeObjectOptions {
  imageBytes: string;
  imageMimeType: string;
  objectHint?: string;
  includePromptSuggestion?: boolean;
}

export interface VisualEditEngineOptions {
  apiKey?: string;
}

export class VisualEditEngine {
  private ai: GoogleGenAI;

  constructor(options?: VisualEditEngineOptions) {
    const apiKey =
      options?.apiKey ??
      (typeof process !== "undefined"
        ? process.env.GEMINI_API_KEY ?? ""
        : "");

    if (!apiKey) {
      throw new Error(
        "[VisualEditEngine] GEMINI_API_KEY が設定されていません。" +
          ".env に GEMINI_API_KEY を追加してください。"
      );
    }

    this.ai = new GoogleGenAI({ apiKey });
  }

  async describeObjectForVeo(
    options: DescribeObjectOptions
  ): Promise<ObjectDescription[]> {
    this.validateOptions(options);

    const prompt = this.buildDescriptionPrompt(options);

    const response = await withRetry(() =>
      this.ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: [
          {
            role: "user",
            parts: [
              { text: prompt },
              {
                inlineData: {
                  data: options.imageBytes,
                  mimeType: options.imageMimeType,
                },
              },
            ],
          },
        ],
      })
    );

    const text = response.candidates?.[0]?.content?.parts?.[0]?.text ?? "";

    return this.parseDescriptionResponse(text);
  }

  async generateEditPrompt(
    sourceDescription: ObjectDescription,
    editInstruction: string
  ): Promise<string> {
    const response = await withRetry(() =>
      this.ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: [
          {
            role: "user",
            parts: [
              {
                text: [
                  "Given the following object description, generate a Veo video generation prompt",
                  "that applies the specified edit while preserving the object's identity.",
                  "",
                  `Object: ${sourceDescription.name}`,
                  `Appearance: ${sourceDescription.appearance}`,
                  `Key Features: ${sourceDescription.keyFeatures.join(", ")}`,
                  "",
                  `Edit Instruction: ${editInstruction}`,
                  "",
                  "Respond with ONLY the prompt text, no JSON or formatting.",
                ].join("\n"),
              },
            ],
          },
        ],
      })
    );

    return response.candidates?.[0]?.content?.parts?.[0]?.text?.trim() ?? "";
  }

  private buildDescriptionPrompt(options: DescribeObjectOptions): string {
    const lines = [
      "Analyze this image and describe the main objects/subjects for use in Veo video generation.",
    ];

    if (options.objectHint) {
      lines.push(`Focus on: ${options.objectHint}`);
    }

    lines.push(
      "",
      "For each object, provide:",
      "- name: concise identifier",
      "- appearance: detailed visual description",
      "- keyFeatures: array of distinctive visual attributes",
      "- suggestedPrompt: a Veo-ready prompt describing this object in motion",
      "",
      "Respond ONLY with a JSON array. Example:",
      '[{"name":"Golden retriever","appearance":"A fluffy golden retriever with a shiny coat",' +
        '"keyFeatures":["golden fur","fluffy","medium-sized","friendly expression"],' +
        '"suggestedPrompt":"A golden retriever running through a sunny meadow"}]',
    );

    return lines.join("\n");
  }

  private parseDescriptionResponse(text: string): ObjectDescription[] {
    const jsonMatch = text.match(/\[[\s\S]*\]/);
    if (!jsonMatch) {
      return [];
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonMatch[0]);
    } catch {
      return [];
    }

    if (!Array.isArray(parsed)) {
      return [];
    }

    const results: ObjectDescription[] = [];

    for (const item of parsed) {
      const obj = item as Record<string, unknown>;

      if (
        typeof obj !== "object" ||
        obj === null ||
        typeof obj.name !== "string"
      ) {
        continue;
      }

      results.push({
        name: obj.name,
        appearance: typeof obj.appearance === "string" ? obj.appearance : "",
        keyFeatures: Array.isArray(obj.keyFeatures)
          ? obj.keyFeatures.filter(
              (f: unknown): f is string => typeof f === "string"
            )
          : [],
        suggestedPrompt:
          typeof obj.suggestedPrompt === "string" ? obj.suggestedPrompt : "",
      });
    }

    return results;
  }

  private validateOptions(options: DescribeObjectOptions): void {
    if (!options.imageBytes || options.imageBytes.length === 0) {
      throw new Error(
        "[VisualEditEngine] imageBytes は必須です。空の画像データは指定できません。"
      );
    }
    if (!options.imageMimeType || options.imageMimeType.length === 0) {
      throw new Error(
        "[VisualEditEngine] imageMimeType は必須です。"
      );
    }
  }
}
