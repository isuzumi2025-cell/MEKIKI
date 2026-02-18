/**
 * subject-registry.test.ts
 *
 * SubjectRegistry のユニットテスト。
 * - register / get / remove / clear
 * - keyFeatures 類似度マッチング (threshold 0.7)
 * - carryover 管理
 * - search
 * - extractFromResult (Gemini Vision mock)
 * - toJSON / fromJSON
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { SubjectRegistry } from "../lib/subject-registry.js";
import type { Subject, GenerationJobResult } from "../lib/types/subject.js";

function makeSubject(overrides: Partial<Subject> = {}): Subject {
  return {
    id: overrides.id ?? "test-1",
    name: overrides.name ?? "Test Subject",
    description: overrides.description ?? "A test subject",
    keyFeatures: overrides.keyFeatures ?? ["red", "round", "glossy"],
    sourceJobId: overrides.sourceJobId,
    thumbnail: overrides.thumbnail,
    carryover: overrides.carryover ?? false,
    createdAt: overrides.createdAt ?? new Date("2026-01-01"),
  };
}

describe("SubjectRegistry", () => {
  let registry: SubjectRegistry;

  beforeEach(() => {
    registry = new SubjectRegistry();
  });

  describe("register", () => {
    it("should register a subject and retrieve it", () => {
      const subject = makeSubject();
      const registered = registry.register(subject);

      expect(registered.id).toBe("test-1");
      expect(registered.name).toBe("Test Subject");
      expect(registry.size).toBe(1);

      const retrieved = registry.get("test-1");
      expect(retrieved).toBeDefined();
      expect(retrieved?.name).toBe("Test Subject");
    });

    it("should throw on empty id", () => {
      expect(() => registry.register(makeSubject({ id: "" }))).toThrow(
        "subject.id は必須です"
      );
    });

    it("should throw on empty name", () => {
      expect(() => registry.register(makeSubject({ name: "" }))).toThrow(
        "subject.name は必須です"
      );
    });

    it("should deduplicate keyFeatures", () => {
      const subject = makeSubject({
        keyFeatures: ["red", "round", "red", "glossy", "round"],
      });
      const registered = registry.register(subject);
      expect(registered.keyFeatures).toEqual(["red", "round", "glossy"]);
    });

    it("should overwrite an existing subject with the same id", () => {
      registry.register(makeSubject({ id: "a", name: "First" }));
      registry.register(makeSubject({ id: "a", name: "Second" }));
      expect(registry.size).toBe(1);
      expect(registry.get("a")?.name).toBe("Second");
    });
  });

  describe("remove / clear", () => {
    it("should remove a subject by id", () => {
      registry.register(makeSubject({ id: "a" }));
      registry.register(makeSubject({ id: "b" }));

      expect(registry.remove("a")).toBe(true);
      expect(registry.size).toBe(1);
      expect(registry.get("a")).toBeUndefined();
    });

    it("should return false when removing non-existent id", () => {
      expect(registry.remove("non-existent")).toBe(false);
    });

    it("should clear all subjects", () => {
      registry.register(makeSubject({ id: "a" }));
      registry.register(makeSubject({ id: "b" }));
      registry.clear();
      expect(registry.size).toBe(0);
    });
  });

  describe("getAll", () => {
    it("should return all registered subjects", () => {
      registry.register(makeSubject({ id: "a", name: "A" }));
      registry.register(makeSubject({ id: "b", name: "B" }));
      registry.register(makeSubject({ id: "c", name: "C" }));

      const all = registry.getAll();
      expect(all).toHaveLength(3);
      expect(all.map((s) => s.id).sort()).toEqual(["a", "b", "c"]);
    });
  });

  describe("carryover", () => {
    it("should toggle carryover flag", () => {
      registry.register(makeSubject({ id: "a", carryover: false }));

      const updated = registry.setCarryover("a", true);
      expect(updated.carryover).toBe(true);
      expect(registry.get("a")?.carryover).toBe(true);
    });

    it("should throw when subject not found", () => {
      expect(() => registry.setCarryover("non-existent", true)).toThrow(
        "が見つかりません"
      );
    });

    it("should return only carryover subjects", () => {
      registry.register(makeSubject({ id: "a", carryover: true }));
      registry.register(makeSubject({ id: "b", carryover: false }));
      registry.register(makeSubject({ id: "c", carryover: true }));

      const carryovers = registry.getCarryoverSubjects();
      expect(carryovers).toHaveLength(2);
      expect(carryovers.map((s) => s.id).sort()).toEqual(["a", "c"]);
    });
  });

  describe("search", () => {
    beforeEach(() => {
      registry.register(
        makeSubject({
          id: "car",
          name: "Red Car",
          description: "A sporty red sedan",
          keyFeatures: ["red", "glossy", "sedan"],
        })
      );
      registry.register(
        makeSubject({
          id: "tree",
          name: "Green Tree",
          description: "A tall oak tree",
          keyFeatures: ["green", "tall", "oak"],
        })
      );
      registry.register(
        makeSubject({
          id: "ball",
          name: "Red Ball",
          description: "A rubber ball",
          keyFeatures: ["red", "round", "rubber"],
        })
      );
    });

    it("should find subjects by name", () => {
      const results = registry.search("Red");
      expect(results).toHaveLength(2);
    });

    it("should find subjects by description", () => {
      const results = registry.search("oak");
      expect(results).toHaveLength(1);
      expect(results[0].id).toBe("tree");
    });

    it("should find subjects by keyFeature", () => {
      const results = registry.search("rubber");
      expect(results).toHaveLength(1);
      expect(results[0].id).toBe("ball");
    });

    it("should be case-insensitive", () => {
      const results = registry.search("RED");
      expect(results).toHaveLength(2);
    });

    it("should return all subjects for empty query", () => {
      expect(registry.search("")).toHaveLength(3);
      expect(registry.search("  ")).toHaveLength(3);
    });

    it("should return empty array for no matches", () => {
      expect(registry.search("xyz")).toHaveLength(0);
    });
  });

  describe("computeSimilarity", () => {
    it("should return 1.0 for identical keyFeatures", () => {
      const a = makeSubject({ keyFeatures: ["red", "round", "glossy"] });
      const b = makeSubject({ keyFeatures: ["red", "round", "glossy"] });

      expect(registry.computeSimilarity(a, b)).toBe(1.0);
    });

    it("should return 0 for completely different keyFeatures", () => {
      const a = makeSubject({ keyFeatures: ["red", "round", "glossy"] });
      const b = makeSubject({ keyFeatures: ["blue", "square", "matte"] });

      expect(registry.computeSimilarity(a, b)).toBe(0);
    });

    it("should calculate Jaccard similarity correctly", () => {
      const a = makeSubject({ keyFeatures: ["red", "round", "glossy"] });
      const b = makeSubject({
        keyFeatures: ["red", "round", "matte", "large"],
      });

      // intersection: {red, round} = 2
      // union: {red, round, glossy, matte, large} = 5
      // similarity = 2/5 = 0.4
      expect(registry.computeSimilarity(a, b)).toBeCloseTo(0.4, 5);
    });

    it("should be case-insensitive", () => {
      const a = makeSubject({ keyFeatures: ["Red", "Round"] });
      const b = makeSubject({ keyFeatures: ["red", "round"] });

      expect(registry.computeSimilarity(a, b)).toBe(1.0);
    });

    it("should return 0 for both empty keyFeatures", () => {
      const a = makeSubject({ keyFeatures: [] });
      const b = makeSubject({ keyFeatures: [] });

      expect(registry.computeSimilarity(a, b)).toBe(0);
    });
  });

  describe("findSimilar", () => {
    beforeEach(() => {
      registry.register(
        makeSubject({
          id: "car-red",
          name: "Red Car",
          keyFeatures: ["red", "glossy", "sedan", "metallic", "sports"],
        })
      );
      registry.register(
        makeSubject({
          id: "car-blue",
          name: "Blue Car",
          keyFeatures: ["blue", "glossy", "sedan", "metallic", "sports"],
        })
      );
      registry.register(
        makeSubject({
          id: "tree",
          name: "Tree",
          keyFeatures: ["green", "tall", "oak", "leafy"],
        })
      );
    });

    it("should find similar subjects above default threshold (0.7)", () => {
      const subject = makeSubject({
        id: "query",
        keyFeatures: ["red", "glossy", "sedan", "metallic", "sports"],
      });

      const matches = registry.findSimilar(subject);

      expect(matches).toHaveLength(1);
      expect(matches[0].subject.id).toBe("car-red");
      expect(matches[0].score).toBe(1.0);
    });

    it("should find similar subjects with custom threshold", () => {
      const subject = makeSubject({
        id: "query",
        keyFeatures: ["glossy", "sedan", "metallic", "sports", "compact"],
      });

      // vs car-red: intersection {glossy, sedan, metallic, sports} = 4, union = 6 => 0.667
      // vs car-blue: intersection {glossy, sedan, metallic, sports} = 4, union = 6 => 0.667
      // vs tree: intersection {} = 0

      const matches = registry.findSimilar(subject, 0.6);
      expect(matches).toHaveLength(2);
    });

    it("should exclude the subject itself from results", () => {
      const subject = registry.get("car-red")!;
      const matches = registry.findSimilar(subject);

      expect(matches.every((m) => m.subject.id !== "car-red")).toBe(true);
    });

    it("should sort results by score descending", () => {
      const subject = makeSubject({
        id: "query",
        keyFeatures: ["red", "glossy", "sedan", "tall"],
      });

      const matches = registry.findSimilar(subject, 0.1);
      for (let i = 1; i < matches.length; i++) {
        expect(matches[i - 1].score).toBeGreaterThanOrEqual(matches[i].score);
      }
    });

    it("should return empty array if nothing above threshold", () => {
      const subject = makeSubject({
        id: "query",
        keyFeatures: ["purple", "tiny", "fluffy"],
      });

      expect(registry.findSimilar(subject)).toHaveLength(0);
    });
  });

  describe("extractFromResult", () => {
    it("should throw without API key", async () => {
      const result: GenerationJobResult = {
        jobId: "job-1",
        outputUrl: "https://example.com/output.png",
      };

      await expect(registry.extractFromResult(result)).rejects.toThrow(
        "Gemini API キーが設定されていません"
      );
    });

    it("should extract subjects from Gemini Vision response", async () => {
      const mockResponse = {
        candidates: [
          {
            content: {
              parts: [
                {
                  text: JSON.stringify([
                    {
                      name: "Red Car",
                      description: "A glossy red sports car",
                      keyFeatures: ["red", "glossy", "sports car"],
                    },
                    {
                      name: "Road",
                      description: "An asphalt road",
                      keyFeatures: ["gray", "asphalt", "wide"],
                    },
                  ]),
                },
              ],
            },
          },
        ],
      };

      const mockAi = {
        models: {
          generateContent: vi.fn().mockResolvedValue(mockResponse),
        },
      };

      const registryWithApi = new SubjectRegistry({ apiKey: "test-key" });
      (registryWithApi as unknown as { ai: typeof mockAi }).ai = mockAi;

      const result: GenerationJobResult = {
        jobId: "job-1",
        outputUrl: "https://example.com/output.png",
        imageBytes: "base64data",
        imageMimeType: "image/png",
      };

      const subjects = await registryWithApi.extractFromResult(result);

      expect(subjects).toHaveLength(2);
      expect(subjects[0].name).toBe("Red Car");
      expect(subjects[0].keyFeatures).toContain("red");
      expect(subjects[0].sourceJobId).toBe("job-1");
      expect(subjects[1].name).toBe("Road");
      expect(registryWithApi.size).toBe(2);
    });

    it("should handle malformed Gemini response gracefully", async () => {
      const mockResponse = {
        candidates: [
          {
            content: {
              parts: [{ text: "not valid json" }],
            },
          },
        ],
      };

      const mockAi = {
        models: {
          generateContent: vi.fn().mockResolvedValue(mockResponse),
        },
      };

      const registryWithApi = new SubjectRegistry({ apiKey: "test-key" });
      (registryWithApi as unknown as { ai: typeof mockAi }).ai = mockAi;

      const result: GenerationJobResult = {
        jobId: "job-2",
        outputUrl: "https://example.com/output.png",
      };

      const subjects = await registryWithApi.extractFromResult(result);
      expect(subjects).toHaveLength(0);
    });

    it("should handle empty candidates gracefully", async () => {
      const mockResponse = { candidates: [] };

      const mockAi = {
        models: {
          generateContent: vi.fn().mockResolvedValue(mockResponse),
        },
      };

      const registryWithApi = new SubjectRegistry({ apiKey: "test-key" });
      (registryWithApi as unknown as { ai: typeof mockAi }).ai = mockAi;

      const result: GenerationJobResult = {
        jobId: "job-3",
        outputUrl: "https://example.com/output.png",
      };

      const subjects = await registryWithApi.extractFromResult(result);
      expect(subjects).toHaveLength(0);
    });
  });

  describe("toJSON / fromJSON", () => {
    it("should serialize and deserialize registry state", () => {
      registry.register(
        makeSubject({ id: "a", name: "A", carryover: true })
      );
      registry.register(
        makeSubject({ id: "b", name: "B", carryover: false })
      );

      const snapshot = registry.toJSON();
      expect(snapshot.version).toBe("1.0.0");
      expect(snapshot.subjects).toHaveLength(2);
      expect(snapshot.exportedAt).toBeDefined();

      const restored = SubjectRegistry.fromJSON(snapshot);
      expect(restored.size).toBe(2);
      expect(restored.get("a")?.name).toBe("A");
      expect(restored.get("a")?.carryover).toBe(true);
      expect(restored.get("b")?.carryover).toBe(false);
    });

    it("should restore Date objects from serialized strings", () => {
      const date = new Date("2026-01-15T10:00:00Z");
      registry.register(makeSubject({ id: "a", createdAt: date }));

      const snapshot = registry.toJSON();
      const jsonString = JSON.stringify(snapshot);
      const parsed = JSON.parse(jsonString);

      const restored = SubjectRegistry.fromJSON(parsed);
      const subject = restored.get("a");
      expect(subject?.createdAt).toBeInstanceOf(Date);
    });
  });

  describe("constructor options", () => {
    it("should accept custom similarity threshold", () => {
      const customRegistry = new SubjectRegistry({
        similarityThreshold: 0.5,
      });

      customRegistry.register(
        makeSubject({
          id: "a",
          keyFeatures: ["red", "round", "glossy", "big"],
        })
      );

      // 2/5 = 0.4 < 0.5 threshold
      const subject = makeSubject({
        id: "query",
        keyFeatures: ["red", "round", "matte"],
      });

      const matchesDefault = customRegistry.findSimilar(subject);
      expect(matchesDefault).toHaveLength(0);

      // 2/5 = 0.4 >= 0.3 threshold
      const matchesLow = customRegistry.findSimilar(subject, 0.3);
      expect(matchesLow).toHaveLength(1);
    });
  });
});
