/**
 * subject-registry.test.ts
 *
 * Tests for Subject Persistence (SubjectRegistry)
 */

import { describe, it, expect, beforeEach } from "vitest";
import {
    SubjectRegistry,
    SubjectSchema,
    SubjectCreateInputSchema,
    SubjectTypeSchema,
    buildCarryoverPromptBlock,
    extractSubjectCandidatesFromText,
    computeJaccardSimilarity,
    type Subject,
    type SubjectCreateInput,
} from "../subject-registry.js";

// ============================================================
// Test Data
// ============================================================

function makeCharacter(overrides?: Partial<SubjectCreateInput>): SubjectCreateInput {
    return {
        name: "赤い帽子の少女",
        type: "character",
        description: "赤い帽子を被った10歳くらいの少女。長い黒髪でワンピースを着ている。",
        keyFeatures: ["赤い帽子", "長い黒髪", "白いワンピース"],
        originCutId: "cut-001",
        carryover: true,
        tags: ["protagonist", "girl"],
        ...overrides,
    };
}

function makeAnimal(overrides?: Partial<SubjectCreateInput>): SubjectCreateInput {
    return {
        name: "白い猫",
        type: "animal",
        description: "ふわふわの白い毛並みの猫。青い目をしている。",
        keyFeatures: ["白い毛並み", "青い目"],
        originCutId: "cut-001",
        carryover: true,
        tags: ["pet", "cat"],
        ...overrides,
    };
}

function makeVehicle(overrides?: Partial<SubjectCreateInput>): SubjectCreateInput {
    return {
        name: "赤いスポーツカー",
        type: "vehicle",
        description: "光沢のある赤いスポーツカー。低いフォルムでスポイラー付き。",
        keyFeatures: ["赤い塗装", "スポイラー", "低いフォルム"],
        originCutId: "cut-002",
        carryover: false,
        tags: ["vehicle", "sports"],
        ...overrides,
    };
}

// ============================================================
// Zod Schema Validation
// ============================================================

describe("SubjectSchema validation", () => {
    it("validates SubjectType enum", () => {
        expect(SubjectTypeSchema.safeParse("character").success).toBe(true);
        expect(SubjectTypeSchema.safeParse("animal").success).toBe(true);
        expect(SubjectTypeSchema.safeParse("object").success).toBe(true);
        expect(SubjectTypeSchema.safeParse("vehicle").success).toBe(true);
        expect(SubjectTypeSchema.safeParse("background").success).toBe(true);
        expect(SubjectTypeSchema.safeParse("unknown").success).toBe(false);
    });

    it("rejects empty name", () => {
        const input = makeCharacter({ name: "" });
        const result = SubjectCreateInputSchema.safeParse(input);
        expect(result.success).toBe(false);
    });

    it("rejects empty keyFeatures", () => {
        const input = makeCharacter({ keyFeatures: [] });
        const result = SubjectCreateInputSchema.safeParse(input);
        expect(result.success).toBe(false);
    });

    it("validates Subject with UUID", () => {
        const full = {
            ...makeCharacter(),
            id: crypto.randomUUID(),
            createdAt: new Date().toISOString(),
        };
        const result = SubjectSchema.safeParse(full);
        expect(result.success).toBe(true);
    });
});

// ============================================================
// SubjectRegistry Core
// ============================================================

describe("SubjectRegistry", () => {
    let registry: SubjectRegistry;

    beforeEach(() => {
        registry = new SubjectRegistry();
    });

    // ── Register + Recall ───────────────────────────────────

    it("registers and recalls a subject by ID", () => {
        const subject = registry.register(makeCharacter());
        expect(subject.id).toBeDefined();
        expect(subject.name).toBe("赤い帽子の少女");
        expect(subject.type).toBe("character");

        const recalled = registry.recall(subject.id);
        expect(recalled).toBeDefined();
        expect(recalled!.id).toBe(subject.id);
    });

    it("registers multiple subjects", () => {
        registry.register(makeCharacter());
        registry.register(makeAnimal());
        registry.register(makeVehicle());
        expect(registry.size).toBe(3);
    });

    it("recalls by name (exact match)", () => {
        registry.register(makeCharacter());
        const found = registry.recallByName("赤い帽子の少女");
        expect(found).toBeDefined();
        expect(found!.type).toBe("character");
    });

    it("recalls by name (partial match)", () => {
        registry.register(makeCharacter());
        const found = registry.recallByName("帽子");
        expect(found).toBeDefined();
        expect(found!.name).toBe("赤い帽子の少女");
    });

    it("returns undefined for unknown ID", () => {
        expect(registry.recall("nonexistent-id")).toBeUndefined();
    });

    // ── Carryover ───────────────────────────────────────────

    it("toggles carryover ON/OFF", () => {
        const subject = registry.register(makeCharacter({ carryover: true }));
        expect(registry.recall(subject.id)!.carryover).toBe(true);

        registry.setCarryover(subject.id, false);
        expect(registry.recall(subject.id)!.carryover).toBe(false);

        registry.setCarryover(subject.id, true);
        expect(registry.recall(subject.id)!.carryover).toBe(true);
    });

    it("returns only carryover subjects", () => {
        registry.register(makeCharacter({ carryover: true }));
        registry.register(makeAnimal({ carryover: true }));
        registry.register(makeVehicle({ carryover: false }));

        const carried = registry.getCarryoverSubjects();
        expect(carried.length).toBe(2);
        expect(carried.every((s) => s.carryover)).toBe(true);
    });

    it("setCarryover returns false for unknown ID", () => {
        expect(registry.setCarryover("nonexistent", true)).toBe(false);
    });

    // ── Search ──────────────────────────────────────────────

    it("searches by type", () => {
        registry.register(makeCharacter());
        registry.register(makeAnimal());
        registry.register(makeVehicle());

        const animals = registry.search({ type: "animal" });
        expect(animals.length).toBe(1);
        expect(animals[0].name).toBe("白い猫");
    });

    it("searches by name substring", () => {
        registry.register(makeCharacter());
        registry.register(makeAnimal());

        const results = registry.search({ name: "猫" });
        expect(results.length).toBe(1);
    });

    it("searches by tag", () => {
        registry.register(makeCharacter());
        registry.register(makeAnimal());

        const petResults = registry.search({ tag: "pet" });
        expect(petResults.length).toBe(1);
        expect(petResults[0].name).toBe("白い猫");
    });

    it("searches carryover only", () => {
        registry.register(makeCharacter({ carryover: true }));
        registry.register(makeVehicle({ carryover: false }));

        const results = registry.search({ carryoverOnly: true });
        expect(results.length).toBe(1);
        expect(results[0].name).toBe("赤い帽子の少女");
    });

    // ── Delete and Clear ────────────────────────────────────

    it("deletes a subject", () => {
        const subject = registry.register(makeCharacter());
        expect(registry.size).toBe(1);

        const deleted = registry.delete(subject.id);
        expect(deleted).toBe(true);
        expect(registry.size).toBe(0);
        expect(registry.recall(subject.id)).toBeUndefined();
    });

    it("clears all subjects", () => {
        registry.register(makeCharacter());
        registry.register(makeAnimal());
        registry.clear();
        expect(registry.size).toBe(0);
    });

    // ── Usage Tracking ──────────────────────────────────────

    it("tracks last used cut ID", () => {
        const subject = registry.register(makeCharacter());
        registry.markUsedInCut(subject.id, "cut-005");
        expect(registry.recall(subject.id)!.lastUsedInCutId).toBe("cut-005");
    });

    // ── Serialization ───────────────────────────────────────

    it("serializes and deserializes", () => {
        registry.register(makeCharacter());
        registry.register(makeAnimal());

        const json = registry.toJSON();
        expect(json.length).toBe(2);

        const restored = SubjectRegistry.fromJSON(json);
        expect(restored.size).toBe(2);

        const found = restored.recallByName("白い猫");
        expect(found).toBeDefined();
        expect(found!.type).toBe("animal");
    });

    it("fromJSON skips invalid entries", () => {
        registry.register(makeCharacter());
        const json = registry.toJSON();
        const restored = SubjectRegistry.fromJSON([{ bad: true }, ...json]);
        expect(restored.size).toBe(1);
    });

    // ── Jaccard Similarity ──────────────────────────────────

    it("computeSimilarity returns 1.0 for identical keyFeatures", () => {
        const a = registry.register(makeCharacter({ keyFeatures: ["red", "hat", "dress"] }));
        const b = registry.register(makeCharacter({
            name: "別のキャラ",
            keyFeatures: ["red", "hat", "dress"],
        }));
        expect(registry.computeSimilarity(a, b)).toBe(1.0);
    });

    it("computeSimilarity returns 0 for disjoint keyFeatures", () => {
        const a = registry.register(makeCharacter({ keyFeatures: ["red", "hat"] }));
        const b = registry.register(makeAnimal({ keyFeatures: ["blue", "fur"] }));
        expect(registry.computeSimilarity(a, b)).toBe(0);
    });

    it("computeSimilarity returns partial score for overlapping features", () => {
        const a = registry.register(makeCharacter({ keyFeatures: ["red", "hat", "dress"] }));
        const b = registry.register(makeCharacter({
            name: "赤い服の少年",
            keyFeatures: ["red", "shirt", "dress"],
        }));
        const score = registry.computeSimilarity(a, b);
        expect(score).toBeGreaterThan(0);
        expect(score).toBeLessThan(1);
        expect(score).toBeCloseTo(0.5, 1);
    });

    // ── findSimilar ─────────────────────────────────────────

    it("findSimilar returns matches above threshold", () => {
        const hero = registry.register(makeCharacter({
            keyFeatures: ["red hat", "black hair", "white dress"],
        }));
        registry.register(makeCharacter({
            name: "赤い服の少年",
            keyFeatures: ["red hat", "brown hair", "white dress"],
        }));
        registry.register(makeAnimal({ keyFeatures: ["white fur", "blue eyes"] }));

        const matches = registry.findSimilar(hero, 0.3);
        expect(matches.length).toBe(1);
        expect(matches[0].subject.name).toBe("赤い服の少年");
        expect(matches[0].score).toBeGreaterThan(0.3);
    });

    it("findSimilar returns empty for no matches above threshold", () => {
        const hero = registry.register(makeCharacter({
            keyFeatures: ["unique", "feature", "set"],
        }));
        registry.register(makeAnimal({ keyFeatures: ["completely", "different"] }));

        const matches = registry.findSimilar(hero, 0.5);
        expect(matches.length).toBe(0);
    });

    it("findSimilar excludes the subject itself", () => {
        const hero = registry.register(makeCharacter({
            keyFeatures: ["red hat", "black hair"],
        }));

        const matches = registry.findSimilar(hero, 0.0);
        const ids = matches.map(m => m.subject.id);
        expect(ids).not.toContain(hero.id);
    });

    // ── extractFromResult ───────────────────────────────────

    it("extracts characters from GenerationJobResult", () => {
        const result = {
            status: "ready" as const,
            mode: "text_to_video" as const,
            finalPrompt: "test",
            editablePrompt: {
                sections: [
                    {
                        id: "characters",
                        label: "登場人物",
                        content: "赤い帽子の少女, 長い黒髪, 白いワンピース; 白い猫, 青い目",
                        source: "analysis" as const,
                        modified: false,
                    },
                ],
                combinedPrompt: "test",
                updatedAt: new Date().toISOString(),
            },
            log: [],
            createdAt: new Date().toISOString(),
        };

        const extracted = registry.extractFromResult(result, "cut-001");
        expect(extracted.length).toBe(2);
        expect(extracted[0].type).toBe("character");
        expect(extracted[0].tags).toContain("extracted");
    });

    it("extracts objects from GenerationJobResult", () => {
        const result = {
            status: "ready" as const,
            mode: "text_to_video" as const,
            finalPrompt: "test",
            editablePrompt: {
                sections: [
                    {
                        id: "objects",
                        label: "小道具・物体",
                        content: "赤い車, 光沢ある; 古い橋",
                        source: "analysis" as const,
                        modified: false,
                    },
                ],
                combinedPrompt: "test",
                updatedAt: new Date().toISOString(),
            },
            log: [],
            createdAt: new Date().toISOString(),
        };

        const extracted = registry.extractFromResult(result, "cut-002");
        expect(extracted.length).toBe(2);
        expect(extracted[0].type).toBe("object");
    });

    it("extractFromResult skips duplicates (Jaccard >= 0.5)", () => {
        registry.register(makeCharacter({
            keyFeatures: ["赤い帽子の少女", "長い黒髪", "白いワンピース"],
        }));

        const result = {
            status: "ready" as const,
            mode: "text_to_video" as const,
            finalPrompt: "test",
            editablePrompt: {
                sections: [
                    {
                        id: "characters",
                        label: "登場人物",
                        content: "赤い帽子の少女, 長い黒髪, 白いワンピース",
                        source: "analysis" as const,
                        modified: false,
                    },
                ],
                combinedPrompt: "test",
                updatedAt: new Date().toISOString(),
            },
            log: [],
            createdAt: new Date().toISOString(),
        };

        const extracted = registry.extractFromResult(result, "cut-003");
        expect(extracted.length).toBe(0);
    });

    it("extractFromResult returns empty for no character/object sections", () => {
        const result = {
            status: "ready" as const,
            mode: "text_to_video" as const,
            finalPrompt: "test",
            editablePrompt: {
                sections: [
                    {
                        id: "scene",
                        label: "シーン記述",
                        content: "A beautiful sunset",
                        source: "analysis" as const,
                        modified: false,
                    },
                ],
                combinedPrompt: "test",
                updatedAt: new Date().toISOString(),
            },
            log: [],
            createdAt: new Date().toISOString(),
        };

        const extracted = registry.extractFromResult(result, "cut-004");
        expect(extracted.length).toBe(0);
    });
});

// ============================================================
// computeJaccardSimilarity
// ============================================================

describe("computeJaccardSimilarity", () => {
    it("returns 1.0 for identical arrays", () => {
        expect(computeJaccardSimilarity(["a", "b", "c"], ["a", "b", "c"])).toBe(1.0);
    });

    it("returns 0 for disjoint arrays", () => {
        expect(computeJaccardSimilarity(["a", "b"], ["c", "d"])).toBe(0);
    });

    it("returns 0 for two empty arrays", () => {
        expect(computeJaccardSimilarity([], [])).toBe(0);
    });

    it("returns correct score for partial overlap", () => {
        const score = computeJaccardSimilarity(["a", "b", "c"], ["b", "c", "d"]);
        expect(score).toBeCloseTo(0.5, 1);
    });

    it("is case-insensitive", () => {
        expect(computeJaccardSimilarity(["Red", "Hat"], ["red", "hat"])).toBe(1.0);
    });

    it("handles one empty array", () => {
        expect(computeJaccardSimilarity(["a"], [])).toBe(0);
        expect(computeJaccardSimilarity([], ["a"])).toBe(0);
    });
});

// ============================================================
// buildCarryoverPromptBlock
// ============================================================

describe("buildCarryoverPromptBlock", () => {
    it("returns empty string for no subjects", () => {
        expect(buildCarryoverPromptBlock([])).toBe("");
    });

    it("builds formatted prompt block", () => {
        const subjects: Subject[] = [
            {
                id: crypto.randomUUID(),
                name: "赤い帽子の少女",
                type: "character",
                description: "赤い帽子を被った少女",
                keyFeatures: ["赤い帽子", "黒髪"],
                originCutId: "cut-001",
                carryover: true,
                tags: ["main"],
                createdAt: new Date().toISOString(),
            },
        ];

        const block = buildCarryoverPromptBlock(subjects);
        expect(block).toContain("Persistent Subjects");
        expect(block).toContain("👤");
        expect(block).toContain("赤い帽子の少女");
        expect(block).toContain("赤い帽子, 黒髪");
    });

    it("uses correct emoji per type", () => {
        const types: Array<{ type: Subject["type"]; emoji: string }> = [
            { type: "character", emoji: "👤" },
            { type: "animal", emoji: "🐾" },
            { type: "vehicle", emoji: "🚗" },
            { type: "background", emoji: "🏔️" },
            { type: "object", emoji: "📦" },
        ];

        for (const { type, emoji } of types) {
            const block = buildCarryoverPromptBlock([{
                id: crypto.randomUUID(),
                name: "test",
                type,
                description: "test",
                keyFeatures: ["test"],
                originCutId: "cut-001",
                carryover: true,
                tags: [],
                createdAt: new Date().toISOString(),
            }]);
            expect(block).toContain(emoji);
        }
    });
});

// ============================================================
// extractSubjectCandidatesFromText
// ============================================================

describe("extractSubjectCandidatesFromText", () => {
    it("extracts character candidates", () => {
        const candidates = extractSubjectCandidatesFromText(
            "A young girl character walks through the forest",
            "cut-001",
        );
        expect(candidates.length).toBeGreaterThanOrEqual(1);
        expect(candidates.some((c) => c.type === "character")).toBe(true);
    });

    it("extracts animal candidates", () => {
        const candidates = extractSubjectCandidatesFromText(
            "A white cat sits on the windowsill",
            "cut-002",
        );
        expect(candidates.length).toBeGreaterThanOrEqual(1);
        expect(candidates.some((c) => c.type === "animal")).toBe(true);
    });

    it("returns empty array for no matches", () => {
        const candidates = extractSubjectCandidatesFromText(
            "The sky is blue and the wind blows gently",
            "cut-003",
        );
        expect(candidates).toEqual([]);
    });
});
