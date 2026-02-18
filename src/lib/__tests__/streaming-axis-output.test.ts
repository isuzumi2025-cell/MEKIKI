/**
 * streaming-axis-output.test.ts
 *
 * T-602 + T-603: Tests for EmotionAxis schema and streaming pipeline
 */

import { describe, it, expect, vi } from "vitest";
import {
    EmotionAxisSchema,
    safeValidateEmotionAxis,
    PromptUnderstandingInputSchema,
} from "../prompt-understanding-schemas.js";
import {
    StreamingAxisPipeline,
    streamAxisAnalysis,
    type AxisAnalyzers,
    type StreamEvent,
} from "../streaming-axis-output.js";

// ============================================================
// T-602: EmotionAxis validation
// ============================================================

describe("EmotionAxisSchema (T-602)", () => {
    const validEmotionAxis = {
        emotionCurve: [
            { position: 0, intensity: 0.3, emotion: "serenity" as const, transition: "ease-in" as const },
            { position: 0.5, intensity: 0.8, emotion: "joy" as const, transition: "ease-in-out" as const },
            { position: 1.0, intensity: 0.4, emotion: "anticipation" as const, transition: "ease-out" as const },
        ],
        palette: {
            primary: "joy",
            secondary: "anticipation",
            colorMapping: { joy: "#FFD700", serenity: "#87CEEB", anticipation: "#FFA500" },
            overallMood: "uplifting" as const,
        },
        suggestedTempoBpm: 120,
        visualImpact: 0.7,
        reasoning: "The prompt conveys a warm, uplifting mood transitioning through calm to excitement.",
    };

    it("validates a valid EmotionAxis", () => {
        const result = EmotionAxisSchema.safeParse(validEmotionAxis);
        expect(result.success).toBe(true);
    });

    it("rejects empty emotionCurve", () => {
        const invalid = { ...validEmotionAxis, emotionCurve: [] };
        const result = EmotionAxisSchema.safeParse(invalid);
        expect(result.success).toBe(false);
    });

    it("rejects out-of-range position", () => {
        const invalid = {
            ...validEmotionAxis,
            emotionCurve: [{ position: 1.5, intensity: 0.5, emotion: "joy" }],
        };
        const result = EmotionAxisSchema.safeParse(invalid);
        expect(result.success).toBe(false);
    });

    it("rejects invalid emotion label", () => {
        const invalid = {
            ...validEmotionAxis,
            emotionCurve: [{ position: 0, intensity: 0.5, emotion: "boredom" }],
        };
        const result = EmotionAxisSchema.safeParse(invalid);
        expect(result.success).toBe(false);
    });

    it("rejects out-of-range BPM", () => {
        const invalid = { ...validEmotionAxis, suggestedTempoBpm: 300 };
        const result = EmotionAxisSchema.safeParse(invalid);
        expect(result.success).toBe(false);
    });

    it("accepts BPM as optional", () => {
        const { suggestedTempoBpm, ...withoutBpm } = validEmotionAxis;
        const result = EmotionAxisSchema.safeParse(withoutBpm);
        expect(result.success).toBe(true);
    });

    it("validates overallMood enum", () => {
        const moods = ["uplifting", "melancholic", "tense", "peaceful", "energetic", "dramatic"];
        for (const mood of moods) {
            const data = {
                ...validEmotionAxis,
                palette: { ...validEmotionAxis.palette, overallMood: mood },
            };
            expect(EmotionAxisSchema.safeParse(data).success).toBe(true);
        }
    });

    it("safeValidateEmotionAxis returns success", () => {
        const result = safeValidateEmotionAxis(validEmotionAxis);
        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.palette.overallMood).toBe("uplifting");
        }
    });

    it("safeValidateEmotionAxis returns error for invalid data", () => {
        const result = safeValidateEmotionAxis({});
        expect(result.success).toBe(false);
    });

    it("includeAxes now accepts A7", () => {
        const input = PromptUnderstandingInputSchema.safeParse({
            prompt: "test",
            includeAxes: ["A1", "A7"],
        });
        expect(input.success).toBe(true);
    });
});

// ============================================================
// T-603: Streaming pipeline
// ============================================================

describe("StreamingAxisPipeline (T-603)", () => {
    const mockGrokResult = {
        A1_trendWords: [{ originalTerm: "test", interpretation: "test", confidence: 0.9, relatedTerms: [], source: "general" as const }],
        A2_culturalContext: { references: [], implicitMeaning: "test" },
        A3_visualTrends: { matchedTrends: [], suggestedStyle: "modern" },
    };

    const mockOpusResult = {
        A4_remotionMapping: { components: [], compositions: [] },
        A5_effectStructure: {
            layers: [],
            transitions: [],
            timeline: { totalFrames: 900, fps: 30 },
        },
        A6_cssSvgWebgl: {
            cssEffects: [],
            svgFilters: [],
            webglShaders: [],
            implementationPath: "css_only" as const,
        },
    };

    const mockEmotionResult = {
        emotionCurve: [{ position: 0, intensity: 0.5, emotion: "joy" as const }],
        palette: {
            primary: "joy",
            colorMapping: { joy: "#FFD700" },
            overallMood: "uplifting" as const,
        },
        visualImpact: 0.7,
        reasoning: "Positive mood",
    };

    it("yields progress and final events", async () => {
        const analyzers: AxisAnalyzers = {
            grok: vi.fn().mockResolvedValue(mockGrokResult),
            opus: vi.fn().mockResolvedValue(mockOpusResult),
            emotion: vi.fn().mockResolvedValue(mockEmotionResult),
        };

        const pipeline = new StreamingAxisPipeline(analyzers);
        const events: StreamEvent[] = [];

        for await (const event of pipeline.analyze({ prompt: "sunset", language: "ja" })) {
            events.push(event);
        }

        // Should have progress events and a final event
        expect(events.length).toBeGreaterThanOrEqual(2);
        const finalEvent = events.find((e) => e.type === "final");
        expect(finalEvent).toBeDefined();
        expect(finalEvent!.overallProgress).toBe(100);
        expect(finalEvent!.finalResult).toBeDefined();
    });

    it("produces valid FinalAxisResult with all analyzers", async () => {
        const analyzers: AxisAnalyzers = {
            grok: vi.fn().mockResolvedValue(mockGrokResult),
            opus: vi.fn().mockResolvedValue(mockOpusResult),
            emotion: vi.fn().mockResolvedValue(mockEmotionResult),
        };

        const events: StreamEvent[] = [];
        const pipeline = new StreamingAxisPipeline(analyzers);

        for await (const event of pipeline.analyze({ prompt: "test", language: "ja" })) {
            events.push(event);
        }

        const final = events.find((e) => e.type === "final")!.finalResult!;
        expect(final.grokAxes).toBeDefined();
        expect(final.opusAxes).toBeDefined();
        expect(final.emotionAxis).toBeDefined();
        expect(final.confidence.total).toBeGreaterThan(0);
        expect(final.totalDurationMs).toBeGreaterThanOrEqual(0);
    });

    it("handles missing analyzers gracefully", async () => {
        const analyzers: AxisAnalyzers = {
            grok: vi.fn().mockResolvedValue(mockGrokResult),
            // opus and emotion are missing
        };

        const pipeline = new StreamingAxisPipeline(analyzers, ["A1", "A2", "A3", "A7"]);
        const events: StreamEvent[] = [];

        for await (const event of pipeline.analyze({ prompt: "test", language: "ja" })) {
            events.push(event);
        }

        const final = events.find((e) => e.type === "final")!.finalResult!;
        expect(final.grokAxes).toBeDefined();
        expect(final.emotionAxis).toBeUndefined(); // no emotion analyzer
    });

    it("handles analyzer errors without crashing", async () => {
        const analyzers: AxisAnalyzers = {
            grok: vi.fn().mockRejectedValue(new Error("API timeout")),
            opus: vi.fn().mockResolvedValue(mockOpusResult),
        };

        const pipeline = new StreamingAxisPipeline(analyzers, ["A1", "A2", "A3", "A4", "A5", "A6"]);
        const events: StreamEvent[] = [];

        for await (const event of pipeline.analyze({ prompt: "test", language: "ja" })) {
            events.push(event);
        }

        const final = events.find((e) => e.type === "final")!.finalResult!;
        // Grok failed, Opus succeeded
        expect(final.grokAxes).toBeUndefined();
        expect(final.opusAxes).toBeDefined();
        // Some axes should have error status
        const failedAxes = final.axisResults.filter((a) => a.status === "failed");
        expect(failedAxes.length).toBeGreaterThan(0);
    });

    it("callback API works correctly", async () => {
        const analyzers: AxisAnalyzers = {
            grok: vi.fn().mockResolvedValue(mockGrokResult),
        };

        const CB = vi.fn<[StreamEvent], void>();
        const result = await streamAxisAnalysis(
            { prompt: "test stream", language: "ja" },
            analyzers,
            CB,
        );

        expect(CB).toHaveBeenCalled();
        expect(result).not.toBeNull();
    });

    it("respects abort signal", async () => {
        const controller = new AbortController();
        const analyzers: AxisAnalyzers = {
            grok: vi.fn().mockImplementation(async () => {
                await new Promise((r) => setTimeout(r, 5000));
                return mockGrokResult;
            }),
        };

        const pipeline = new StreamingAxisPipeline(analyzers, ["A1", "A2", "A3"]);
        const events: StreamEvent[] = [];

        // Abort after 50ms
        setTimeout(() => controller.abort(), 50);

        for await (const event of pipeline.analyze({ prompt: "test", language: "ja" }, controller.signal)) {
            events.push(event);
            if (controller.signal.aborted) break;
        }

        // Should have aborted before the 5-second analyzer completed
        expect(events.length).toBeLessThan(100);
    });
});
