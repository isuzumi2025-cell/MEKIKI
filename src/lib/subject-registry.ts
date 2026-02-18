/**
 * subject-registry.ts
 *
 * Subject Persistence — カット間オブジェクト持ち越し + 呼び出し機能
 *
 * 動画生成時に登場する人物・動物・物体を「サブジェクト」として登録し、
 * 次のカットへの持ち越し有無を選択。有事に呼び出して再利用できる。
 *
 * FlowForge SDK — Subject Layer
 */

import { z } from "zod";
import { LRUCache } from "./resilience.js";

// ============================================================
// Zod Schemas
// ============================================================

export const SubjectTypeSchema = z.enum([
    "character",
    "animal",
    "object",
    "vehicle",
    "background",
]);

export type SubjectType = z.infer<typeof SubjectTypeSchema>;

export const SubjectSchema = z.object({
    id: z.string().uuid(),
    name: z.string().min(1, "サブジェクト名は必須です"),
    type: SubjectTypeSchema,
    description: z.string().min(1, "外見記述は必須です"),
    keyFeatures: z.array(z.string()).min(1, "少なくとも1つの特徴が必要です"),
    referenceImageBytes: z.string().optional(),
    referenceImageMimeType: z.enum(["image/png", "image/jpeg", "image/webp"]).optional(),
    originCutId: z.string(),
    carryover: z.boolean().default(true),
    tags: z.array(z.string()).default([]),
    createdAt: z.string().datetime(),
    lastUsedInCutId: z.string().optional(),
});

export type Subject = z.infer<typeof SubjectSchema>;

export const SubjectCreateInputSchema = z.object({
    name: z.string().min(1),
    type: SubjectTypeSchema,
    description: z.string().min(1),
    keyFeatures: z.array(z.string()).min(1),
    referenceImageBytes: z.string().optional(),
    referenceImageMimeType: z.enum(["image/png", "image/jpeg", "image/webp"]).optional(),
    originCutId: z.string(),
    carryover: z.boolean().default(true),
    tags: z.array(z.string()).default([]),
});

export type SubjectCreateInput = z.infer<typeof SubjectCreateInputSchema>;

// ============================================================
// Carryover Prompt Builder
// ============================================================

/**
 * 持ち越しサブジェクトのプロンプト注入文を構築する。
 * 各サブジェクトの外見・特徴をプロンプトフォーマットに変換。
 */
export function buildCarryoverPromptBlock(subjects: Subject[]): string {
    if (subjects.length === 0) return "";

    const lines: string[] = [
        "## Persistent Subjects (carry over from previous cut)",
        "",
    ];

    for (const subject of subjects) {
        const typeLabel = subject.type === "character" ? "👤"
            : subject.type === "animal" ? "🐾"
                : subject.type === "vehicle" ? "🚗"
                    : subject.type === "background" ? "🏔️"
                        : "📦";

        lines.push(`### ${typeLabel} ${subject.name}`);
        lines.push(`- Description: ${subject.description}`);
        lines.push(`- Key features: ${subject.keyFeatures.join(", ")}`);
        if (subject.tags.length > 0) {
            lines.push(`- Tags: ${subject.tags.join(", ")}`);
        }
        lines.push("");
    }

    return lines.join("\n");
}

// ============================================================
// Subject Auto-Extraction (from prompt text)
// ============================================================

/**
 * プロンプトテキストからサブジェクト候補を簡易抽出する。
 * Gemini Vision がある場合はそちらを優先すべき。これはフォールバック。
 */
export function extractSubjectCandidatesFromText(
    promptText: string,
    cutId: string,
): SubjectCreateInput[] {
    const candidates: SubjectCreateInput[] = [];

    // パターンベースの簡易抽出
    const patterns: { pattern: RegExp; type: SubjectType }[] = [
        { pattern: /(?:a |the )?(\w+(?:\s+\w+)*)\s+(?:character|person|man|woman|boy|girl|child)/gi, type: "character" },
        { pattern: /(?:a |the )?(\w+(?:\s+\w+)*)\s+(?:cat|dog|bird|horse|rabbit|fox|wolf|bear|fish)/gi, type: "animal" },
        { pattern: /(?:a |the )?(\w+(?:\s+\w+)*)\s+(?:car|truck|bus|train|boat|ship|airplane|bicycle)/gi, type: "vehicle" },
    ];

    for (const { pattern, type } of patterns) {
        let match: RegExpExecArray | null;
        while ((match = pattern.exec(promptText)) !== null) {
            const fullMatch = match[0].trim();
            if (fullMatch.length < 3) continue;

            candidates.push({
                name: fullMatch,
                type,
                description: fullMatch,
                keyFeatures: [fullMatch],
                originCutId: cutId,
                carryover: true,
                tags: [type],
            });
        }
    }

    return candidates;
}

// ============================================================
// SubjectRegistry
// ============================================================

const MAX_SUBJECTS = 50;

export class SubjectRegistry {
    private subjects: LRUCache<string, Subject>;
    private nameIndex = new Map<string, string>(); // lowercase name → id
    private tagIndex = new Map<string, Set<string>>(); // tag → Set<id>

    constructor() {
        this.subjects = new LRUCache<string, Subject>(MAX_SUBJECTS);
    }

    // ── Register ────────────────────────────────────────────

    /**
     * 新規サブジェクトを登録する。Zod でバリデーション後に UUID を付与。
     */
    register(input: SubjectCreateInput): Subject {
        const parsed = SubjectCreateInputSchema.parse(input);

        const subject: Subject = {
            ...parsed,
            id: crypto.randomUUID(),
            createdAt: new Date().toISOString(),
        };

        this.subjects.set(subject.id, subject);
        this.nameIndex.set(subject.name.toLowerCase(), subject.id);

        for (const tag of subject.tags) {
            if (!this.tagIndex.has(tag)) {
                this.tagIndex.set(tag, new Set());
            }
            this.tagIndex.get(tag)!.add(subject.id);
        }

        return subject;
    }

    // ── Recall ──────────────────────────────────────────────

    /**
     * ID でサブジェクトを呼び出す。
     */
    recall(id: string): Subject | undefined {
        return this.subjects.get(id);
    }

    /**
     * 名前でサブジェクトを呼び出す (部分一致)。
     */
    recallByName(name: string): Subject | undefined {
        const lowerName = name.toLowerCase();

        // 完全一致
        const exactId = this.nameIndex.get(lowerName);
        if (exactId) return this.subjects.get(exactId);

        // 部分一致
        for (const [indexedName, id] of this.nameIndex) {
            if (indexedName.includes(lowerName) || lowerName.includes(indexedName)) {
                return this.subjects.get(id);
            }
        }

        return undefined;
    }

    // ── Search ──────────────────────────────────────────────

    /**
     * 名前/タグ/タイプで検索する。
     */
    search(query: {
        name?: string;
        tag?: string;
        type?: SubjectType;
        carryoverOnly?: boolean;
    }): Subject[] {
        const results: Subject[] = [];
        const allSubjects = this.getAllSubjects();

        for (const subject of allSubjects) {
            if (query.name && !subject.name.toLowerCase().includes(query.name.toLowerCase())) {
                continue;
            }
            if (query.tag) {
                const tagIds = this.tagIndex.get(query.tag);
                if (!tagIds || !tagIds.has(subject.id)) continue;
            }
            if (query.type && subject.type !== query.type) {
                continue;
            }
            if (query.carryoverOnly && !subject.carryover) {
                continue;
            }
            results.push(subject);
        }

        return results;
    }

    // ── Carryover ───────────────────────────────────────────

    /**
     * サブジェクトの持ち越しを ON/OFF に設定する。
     */
    setCarryover(id: string, carryover: boolean): boolean {
        const subject = this.subjects.get(id);
        if (!subject) return false;

        subject.carryover = carryover;
        this.subjects.set(id, subject);
        return true;
    }

    /**
     * 持ち越し ON のサブジェクト一覧を返す。
     */
    getCarryoverSubjects(): Subject[] {
        return this.getAllSubjects().filter((s) => s.carryover);
    }

    /**
     * 持ち越しサブジェクトをプロンプト注入文に変換する。
     */
    buildCarryoverPrompt(): string {
        return buildCarryoverPromptBlock(this.getCarryoverSubjects());
    }

    // ── Usage Tracking ──────────────────────────────────────

    /**
     * サブジェクトが特定カットで使用されたことを記録する。
     */
    markUsedInCut(id: string, cutId: string): boolean {
        const subject = this.subjects.get(id);
        if (!subject) return false;

        subject.lastUsedInCutId = cutId;
        this.subjects.set(id, subject);
        return true;
    }

    // ── Bulk Operations ─────────────────────────────────────

    /**
     * 全サブジェクトを返す。
     */
    getAllSubjects(): Subject[] {
        const all: Subject[] = [];
        // LRUCache doesn't have an iterator, so we track via nameIndex
        for (const id of this.nameIndex.values()) {
            const subject = this.subjects.get(id);
            if (subject) all.push(subject);
        }
        return all;
    }

    /**
     * レジストリのサブジェクト数を返す。
     */
    get size(): number {
        return this.nameIndex.size;
    }

    /**
     * ID でサブジェクトを削除する。
     */
    delete(id: string): boolean {
        const subject = this.subjects.get(id);
        if (!subject) return false;

        this.subjects.delete(id);
        this.nameIndex.delete(subject.name.toLowerCase());

        for (const tag of subject.tags) {
            const tagSet = this.tagIndex.get(tag);
            if (tagSet) {
                tagSet.delete(id);
                if (tagSet.size === 0) this.tagIndex.delete(tag);
            }
        }

        return true;
    }

    /**
     * 全クリア。
     */
    clear(): void {
        this.subjects.clear();
        this.nameIndex.clear();
        this.tagIndex.clear();
    }

    // ── Serialization ───────────────────────────────────────

    /**
     * JSON 永続化用。
     */
    toJSON(): Subject[] {
        return this.getAllSubjects();
    }

    /**
     * JSON からレジストリを復元する。
     */
    static fromJSON(data: unknown[]): SubjectRegistry {
        const registry = new SubjectRegistry();

        for (const item of data) {
            const parsed = SubjectSchema.safeParse(item);
            if (!parsed.success) continue;

            const subject = parsed.data;
            registry.subjects.set(subject.id, subject);
            registry.nameIndex.set(subject.name.toLowerCase(), subject.id);

            for (const tag of subject.tags) {
                if (!registry.tagIndex.has(tag)) {
                    registry.tagIndex.set(tag, new Set());
                }
                registry.tagIndex.get(tag)!.add(subject.id);
            }
        }

        return registry;
    }
}
