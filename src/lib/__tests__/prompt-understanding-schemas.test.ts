/**
 * prompt-understanding-schemas.test.ts — Unit tests for 6-axis Zod schemas
 */

import { describe, it, expect } from "vitest";
import {
    validateGrokAxes,
    validateOpusAxes,
    validatePromptInput,
    safeValidateGrokAxes,
    safeValidateOpusAxes,
    calculateConfidenceScore,
    PromptUnderstandingInputSchema,
} from "../prompt-understanding-schemas.js";

describe("PromptUnderstandingInputSchema", () => {
    it("validates valid input", () => {
        const input = { prompt: "test prompt", language: "ja" };
        const result = PromptUnderstandingInputSchema.safeParse(input);
        expect(result.success).toBe(true);
    });

    it("rejects empty prompt", () => {
        const input = { prompt: "" };
        const result = PromptUnderstandingInputSchema.safeParse(input);
        expect(result.success).toBe(false);
    });

    it("defaults language to ja", () => {
        const result = validatePromptInput({ prompt: "test" });
        expect(result.language).toBe("ja");
    });

    it("rejects invalid language", () => {
        const result = PromptUnderstandingInputSchema.safeParse({ prompt: "test", language: "fr" });
        expect(result.success).toBe(false);
    });
});

describe("GrokAxes validation", () => {
    const validGrokAxes = {
        A1_trendWords: [{
            originalTerm: "vaporwave",
            interpretation: "retro-futuristic aesthetic",
            confidence: 0.9,
            relatedTerms: ["synthwave", "retrowave"],
            source: "general" as const,
        }],
        A2_culturalContext: {
            references: [{
                name: "Akira",
                type: "anime" as const,
                relevance: 0.85,
            }],
            implicitMeaning: "cyberpunk dystopia",
        },
        A3_visualTrends: {
            matchedTrends: [{
                name: "Neo-Tokyo aesthetic",
                description: "cyberpunk urban landscapes",
                popularity: "mainstream" as const,
                examples: ["Blade Runner", "Ghost in the Shell"],
            }],
            suggestedStyle: "dark cyberpunk with neon accents",
        },
    };

    it("validates valid GrokAxes", () => {
        const result = validateGrokAxes(validGrokAxes);
        expect(result.A1_trendWords).toHaveLength(1);
        expect(result.A2_culturalContext.references).toHaveLength(1);
    });

    it("rejects invalid GrokAxes (missing field)", () => {
        const result = safeValidateGrokAxes({ A1_trendWords: [] });
        expect(result.success).toBe(false);
    });

    it("rejects confidence out of range", () => {
        const invalid = {
            ...validGrokAxes,
            A1_trendWords: [{
                ...validGrokAxes.A1_trendWords[0],
                confidence: 1.5,
            }],
        };
        const result = safeValidateGrokAxes(invalid);
        expect(result.success).toBe(false);
    });
});

describe("OpusAxes validation", () => {
    const validOpusAxes = {
        A4_remotionMapping: {
            components: [{
                name: "MainScene",
                importPath: "./MainScene",
                purpose: "primary scene component",
            }],
            compositions: [{
                id: "main",
                durationFrames: 300,
                fps: 30,
            }],
        },
        A5_effectStructure: {
            layers: [{
                id: "bg",
                type: "video" as const,
                zIndex: 0,
                startFrame: 0,
                endFrame: 300,
            }],
            transitions: [{
                type: "fade",
                durationFrames: 15,
                fromLayerId: "bg",
                toLayerId: "fg",
            }],
            timeline: {
                totalFrames: 300,
                fps: 30,
            },
        },
        A6_cssSvgWebgl: {
            cssEffects: [{
                property: "filter",
                value: "blur(2px)",
            }],
            svgFilters: [],
            webglShaders: [],
            implementationPath: "css_only" as const,
        },
    };

    it("validates valid OpusAxes", () => {
        const result = validateOpusAxes(validOpusAxes);
        expect(result.A4_remotionMapping.components).toHaveLength(1);
    });

    it("rejects invalid OpusAxes", () => {
        const result = safeValidateOpusAxes({ A4_remotionMapping: {} });
        expect(result.success).toBe(false);
    });
});

describe("calculateConfidenceScore", () => {
    it("calculates weighted score correctly", () => {
        const score = calculateConfidenceScore({
            coverage: 80,
            depth: 70,
            coherence: 90,
            specificity: 60,
        });
        expect(score.total).toBe(80 * 0.3 + 70 * 0.3 + 90 * 0.2 + 60 * 0.2);
        expect(score.coverage).toBe(80);
    });

    it("defaults missing values to 0", () => {
        const score = calculateConfidenceScore({});
        expect(score.total).toBe(0);
    });

    it("handles partial input", () => {
        const score = calculateConfidenceScore({ coverage: 100 });
        expect(score.total).toBe(30);
        expect(score.coverage).toBe(100);
        expect(score.depth).toBe(0);
    });
});
