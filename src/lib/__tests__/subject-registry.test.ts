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
        const invalid = [
            { id: "not-a-uuid", name: "" },
            ...registry.register(makeCharacter()) ? [registry.toJSON()[0]] : [],
        ];

        registry.register(makeCharacter());
        const json = registry.toJSON();
        const restored = SubjectRegistry.fromJSON([{ bad: true }, ...json]);
        expect(restored.size).toBe(1);
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
