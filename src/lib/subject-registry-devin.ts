/**
 * subject-registry-devin.ts
 *
 * サブジェクトレジストリ SDK (Devin 版)
 * GenerationJobResult から Gemini Vision を使ってサブジェクト（登場人物等）を
 * 自動抽出し、keyFeatures の類似度でマッチングを行う。
 *
 * @see visual-edit-engine.ts の describeObjectForVeo パターン
 */

import { GoogleGenAI } from "@google/genai";
import { withRetry } from "./utils/retry.js";
import type {
  Subject,
  SubjectRegistryOptions,
  GenerationJobResult,
  SimilarityMatch,
  ExtractedSubjectData,
} from "./types/subject.js";

const DEFAULT_SIMILARITY_THRESHOLD = 0.7;

export class SubjectRegistry {
  private subjects: Map<string, Subject> = new Map();
  private ai: GoogleGenAI | null = null;
  private readonly similarityThreshold: number;

  constructor(options?: SubjectRegistryOptions) {
    this.similarityThreshold =
      options?.similarityThreshold ?? DEFAULT_SIMILARITY_THRESHOLD;

    const apiKey =
      options?.apiKey ??
      (typeof process !== "undefined"
        ? process.env.GEMINI_API_KEY ?? ""
        : "");

    if (apiKey) {
      this.ai = new GoogleGenAI({ apiKey });
    }
  }

  register(subject: Subject): Subject {
    if (!subject.id || subject.id.trim().length === 0) {
      throw new Error(
        "[SubjectRegistry] subject.id は必須です。空の ID は指定できません。"
      );
    }
    if (!subject.name || subject.name.trim().length === 0) {
      throw new Error(
        "[SubjectRegistry] subject.name は必須です。空の名前は指定できません。"
      );
    }

    const registered: Subject = {
      ...subject,
      createdAt: subject.createdAt ?? new Date(),
      carryover: subject.carryover ?? false,
      keyFeatures: [...new Set(subject.keyFeatures)],
    };

    this.subjects.set(registered.id, registered);
    return registered;
  }

  get(id: string): Subject | undefined {
    return this.subjects.get(id);
  }

  getAll(): Subject[] {
    return Array.from(this.subjects.values());
  }

  remove(id: string): boolean {
    return this.subjects.delete(id);
  }

  clear(): void {
    this.subjects.clear();
  }

  get size(): number {
    return this.subjects.size;
  }

  setCarryover(id: string, carryover: boolean): Subject {
    const subject = this.subjects.get(id);
    if (!subject) {
      throw new Error(
        `[SubjectRegistry] subject "${id}" が見つかりません。`
      );
    }
    const updated: Subject = { ...subject, carryover };
    this.subjects.set(id, updated);
    return updated;
  }

  getCarryoverSubjects(): Subject[] {
    return this.getAll().filter((s) => s.carryover);
  }

  search(query: string): Subject[] {
    if (!query || query.trim().length === 0) {
      return this.getAll();
    }

    const lowerQuery = query.toLowerCase();

    return this.getAll().filter((subject) => {
      if (subject.name.toLowerCase().includes(lowerQuery)) {
        return true;
      }
      if (subject.description?.toLowerCase().includes(lowerQuery)) {
        return true;
      }
      return subject.keyFeatures.some((f) =>
        f.toLowerCase().includes(lowerQuery)
      );
    });
  }

  computeSimilarity(a: Subject, b: Subject): number {
    if (a.keyFeatures.length === 0 && b.keyFeatures.length === 0) {
      return 0;
    }

    const setA = new Set(a.keyFeatures.map((f) => f.toLowerCase()));
    const setB = new Set(b.keyFeatures.map((f) => f.toLowerCase()));

    let intersectionSize = 0;
    for (const feature of setA) {
      if (setB.has(feature)) {
        intersectionSize++;
      }
    }

    const unionSize = new Set([...setA, ...setB]).size;

    if (unionSize === 0) {
      return 0;
    }

    return intersectionSize / unionSize;
  }

  findSimilar(
    subject: Subject,
    threshold?: number
  ): SimilarityMatch[] {
    const effectiveThreshold = threshold ?? this.similarityThreshold;

    const matches: SimilarityMatch[] = [];

    for (const candidate of this.subjects.values()) {
      if (candidate.id === subject.id) {
        continue;
      }

      const score = this.computeSimilarity(subject, candidate);

      if (score >= effectiveThreshold) {
        matches.push({ subject: candidate, score });
      }
    }

    matches.sort((a, b) => b.score - a.score);

    return matches;
  }

  async extractFromResult(
    result: GenerationJobResult
  ): Promise<Subject[]> {
    if (!this.ai) {
      throw new Error(
        "[SubjectRegistry] Gemini API キーが設定されていません。" +
        "コンストラクタで apiKey を指定するか、GEMINI_API_KEY 環境変数を設定してください。"
      );
    }

    const extractedData = await this.analyzeWithGeminiVision(result);
    const subjects: Subject[] = [];

    for (const data of extractedData) {
      const id = `subj-${result.jobId}-${data.index}`;

      const subject = this.register({
        id,
        name: data.name,
        description: data.description,
        keyFeatures: data.keyFeatures,
        sourceJobId: result.jobId,
        thumbnail: result.outputUrl,
        carryover: false,
        createdAt: new Date(),
      });

      subjects.push(subject);
    }

    return subjects;
  }

  private async analyzeWithGeminiVision(
    result: GenerationJobResult
  ): Promise<ExtractedSubjectData[]> {
    const prompt = buildExtractionPrompt();
    const parts = buildRequestParts(prompt, result);

    const response = await withRetry(() =>
      this.ai!.models.generateContent({
        model: "gemini-2.5-flash",
        contents: [{ role: "user", parts }],
      })
    );

    const text = response.candidates?.[0]?.content?.parts?.[0]?.text ?? "";

    return parseExtractionResponse(text);
  }

  toJSON(): SubjectRegistrySnapshot {
    return {
      version: "1.0.0",
      subjects: this.getAll(),
      exportedAt: new Date().toISOString(),
    };
  }

  static fromJSON(
    snapshot: SubjectRegistrySnapshot,
    options?: SubjectRegistryOptions
  ): SubjectRegistry {
    const registry = new SubjectRegistry(options);
    for (const subject of snapshot.subjects) {
      registry.register({
        ...subject,
        createdAt: new Date(subject.createdAt),
      });
    }
    return registry;
  }
}

export interface SubjectRegistrySnapshot {
  version: string;
  subjects: Subject[];
  exportedAt: string;
}

function buildExtractionPrompt(): string {
  return [
    "Analyze this image and extract all distinct subjects (objects, characters, elements).",
    "For each subject found, provide:",
    "- name: A concise name for the subject",
    "- description: A brief description of the subject's appearance",
    "- keyFeatures: An array of distinctive visual features (e.g., color, shape, texture, style)",
    "",
    "Respond ONLY with a JSON array. Example:",
    '[{"name":"Red car","description":"A glossy red sports car","keyFeatures":["red","glossy","sports car","sedan","metallic"]}]',
    "",
    "If no distinct subjects are found, respond with an empty array: []",
  ].join("\n");
}

function buildRequestParts(
  prompt: string,
  result: GenerationJobResult
): Array<{ text: string } | { inlineData: { data: string; mimeType: string } }> {
  const parts: Array<
    { text: string } | { inlineData: { data: string; mimeType: string } }
  > = [{ text: prompt }];

  if (result.imageBytes && result.imageMimeType) {
    parts.push({
      inlineData: {
        data: result.imageBytes,
        mimeType: result.imageMimeType,
      },
    });
  }

  return parts;
}

function parseExtractionResponse(text: string): ExtractedSubjectData[] {
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

  const results: ExtractedSubjectData[] = [];

  for (let i = 0; i < parsed.length; i++) {
    const item = parsed[i] as Record<string, unknown>;

    if (
      typeof item !== "object" ||
      item === null ||
      typeof item.name !== "string" ||
      !Array.isArray(item.keyFeatures)
    ) {
      continue;
    }

    const keyFeatures = item.keyFeatures.filter(
      (f: unknown): f is string => typeof f === "string"
    );

    results.push({
      index: i,
      name: item.name,
      description:
        typeof item.description === "string" ? item.description : "",
      keyFeatures,
    });
  }

  return results;
}
