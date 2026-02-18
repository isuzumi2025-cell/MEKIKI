/**
 * prompt-understanding-schemas.ts
 *
 * 7軸プロンプト理解の Zod スキーマバリデーション (T-601 + T-602)
 * Grok 3軸 + Opus 3軸 + A7感情分析軸 の入出力を厳密に型検証する。
 *
 * FlowForge SDK — Validation Layer
 */

import { z } from "zod";

// ============================================================
// 入力スキーマ
// ============================================================

export const PromptUnderstandingInputSchema = z.object({
    prompt: z.string().min(1, "プロンプトは1文字以上必要です"),
    language: z.enum(["ja", "en"]).default("ja"),
    includeAxes: z.array(z.enum(["A1", "A2", "A3", "A4", "A5", "A6", "A7"])).optional(),
});

export type PromptUnderstandingInput = z.infer<typeof PromptUnderstandingInputSchema>;

// ============================================================
// Grok 3軸 (A1–A3) スキーマ
// ============================================================

export const TrendWordInterpretationSchema = z.object({
    originalTerm: z.string(),
    interpretation: z.string(),
    confidence: z.number().min(0).max(1),
    relatedTerms: z.array(z.string()),
    source: z.enum(["slang", "industry", "meme", "brand", "general"]),
});

export const CulturalContextSchema = z.object({
    references: z.array(z.object({
        name: z.string(),
        type: z.enum(["anime", "film", "music", "art", "game", "fashion", "architecture", "other"]),
        relevance: z.number().min(0).max(1),
    })),
    implicitMeaning: z.string(),
    targetAudience: z.string().optional(),
});

export const VisualTrendSchema = z.object({
    matchedTrends: z.array(z.object({
        name: z.string(),
        description: z.string(),
        popularity: z.enum(["emerging", "mainstream", "declining", "niche"]),
        examples: z.array(z.string()),
    })),
    suggestedStyle: z.string(),
});

export const GrokAxesSchema = z.object({
    A1_trendWords: TrendWordInterpretationSchema.array(),
    A2_culturalContext: CulturalContextSchema,
    A3_visualTrends: VisualTrendSchema,
});

export type GrokAxes = z.infer<typeof GrokAxesSchema>;

// ============================================================
// Opus 3軸 (A4–A6) スキーマ
// ============================================================

export const RemotionMappingSchema = z.object({
    components: z.array(z.object({
        name: z.string(),
        importPath: z.string(),
        purpose: z.string(),
        props: z.record(z.string(), z.string()).optional(),
    })),
    compositions: z.array(z.object({
        id: z.string(),
        durationFrames: z.number().int().positive(),
        fps: z.number().positive(),
    })),
});

export const EffectStructureSchema = z.object({
    layers: z.array(z.object({
        id: z.string(),
        type: z.enum(["video", "image", "text", "shape", "effect", "audio"]),
        zIndex: z.number().int(),
        startFrame: z.number().int().min(0),
        endFrame: z.number().int().min(0),
        opacity: z.number().min(0).max(1).optional(),
    })),
    transitions: z.array(z.object({
        type: z.string(),
        durationFrames: z.number().int().positive(),
        fromLayerId: z.string(),
        toLayerId: z.string(),
    })),
    timeline: z.object({
        totalFrames: z.number().int().positive(),
        fps: z.number().positive(),
    }),
});

export const CssSvgWebglSchema = z.object({
    cssEffects: z.array(z.object({
        property: z.string(),
        value: z.string(),
        keyframes: z.array(z.object({
            offset: z.number().min(0).max(1),
            value: z.string(),
        })).optional(),
    })),
    svgFilters: z.array(z.object({
        type: z.string(),
        params: z.record(z.string(), z.union([z.string(), z.number()])),
    })),
    webglShaders: z.array(z.object({
        name: z.string(),
        type: z.enum(["vertex", "fragment"]),
        uniforms: z.record(z.string(), z.string()),
    })),
    implementationPath: z.enum(["css_only", "svg_css", "webgl", "canvas_2d", "hybrid"]),
});

export const OpusAxesSchema = z.object({
    A4_remotionMapping: RemotionMappingSchema,
    A5_effectStructure: EffectStructureSchema,
    A6_cssSvgWebgl: CssSvgWebglSchema,
});

export type OpusAxes = z.infer<typeof OpusAxesSchema>;

// ============================================================
// A7: 感情分析軸 (T-602 — Gemini提案)
// ============================================================

export const EmotionCurvePointSchema = z.object({
    /** タイムライン上の位置 (0.0-1.0) */
    position: z.number().min(0).max(1),
    /** 感情の強度 (0.0-1.0) */
    intensity: z.number().min(0).max(1),
    /** 感情のラベル */
    emotion: z.enum([
        "joy", "sadness", "anger", "fear", "surprise",
        "disgust", "trust", "anticipation", "serenity",
        "ecstasy", "grief", "terror", "amazement", "loathing",
    ]),
    /** トランジション種別 */
    transition: z.enum(["linear", "ease-in", "ease-out", "ease-in-out", "step"]).default("ease-in-out"),
});

export const EmotionPaletteSchema = z.object({
    /** 主要感情 */
    primary: z.string(),
    /** 副次感情 */
    secondary: z.string().optional(),
    /** 感情に対応するカラーコード */
    colorMapping: z.record(z.string(), z.string()),
    /** 全体的なムード */
    overallMood: z.enum([
        "uplifting", "melancholic", "tense", "peaceful",
        "energetic", "mysterious", "romantic", "epic",
        "playful", "contemplative", "nostalgic", "dramatic",
    ]),
});

export const EmotionAxisSchema = z.object({
    /** 感情曲線 — 動画タイムライン上の感情変化 */
    emotionCurve: z.array(EmotionCurvePointSchema).min(1),
    /** 感情パレット */
    palette: EmotionPaletteSchema,
    /** 音楽のテンポ推奨 (BPM) */
    suggestedTempoBpm: z.number().int().min(40).max(200).optional(),
    /** 視覚効果への影響度 (0.0-1.0) */
    visualImpact: z.number().min(0).max(1),
    /** 感情分析の根拠 */
    reasoning: z.string(),
});

export type EmotionAxis = z.infer<typeof EmotionAxisSchema>;

// ============================================================
// 統合結果スキーマ
// ============================================================

export const ConfidenceScoreSchema = z.object({
    coverage: z.number().min(0).max(100),
    depth: z.number().min(0).max(100),
    coherence: z.number().min(0).max(100),
    specificity: z.number().min(0).max(100),
    total: z.number().min(0).max(100),
});

export type ConfidenceScore = z.infer<typeof ConfidenceScoreSchema>;

export const PromptUnderstandingResultSchema = z.object({
    input: PromptUnderstandingInputSchema,
    grokAxes: GrokAxesSchema.optional(),
    opusAxes: OpusAxesSchema.optional(),
    emotionAxis: EmotionAxisSchema.optional(),
    confidence: ConfidenceScoreSchema,
    contradictions: z.array(z.object({
        axisA: z.string(),
        axisB: z.string(),
        description: z.string(),
        resolution: z.string().optional(),
    })),
    processedAt: z.string().datetime(),
});

export type PromptUnderstandingResult = z.infer<typeof PromptUnderstandingResultSchema>;

// ============================================================
// バリデーション関数
// ============================================================

export function validateGrokAxes(data: unknown): GrokAxes {
    return GrokAxesSchema.parse(data);
}

export function validateOpusAxes(data: unknown): OpusAxes {
    return OpusAxesSchema.parse(data);
}

export function validatePromptInput(data: unknown): PromptUnderstandingInput {
    return PromptUnderstandingInputSchema.parse(data);
}

export function safeValidateGrokAxes(data: unknown): { success: true; data: GrokAxes } | { success: false; error: z.ZodError } {
    const result = GrokAxesSchema.safeParse(data);
    if (result.success) {
        return { success: true, data: result.data };
    }
    return { success: false, error: result.error };
}

export function safeValidateOpusAxes(data: unknown): { success: true; data: OpusAxes } | { success: false; error: z.ZodError } {
    const result = OpusAxesSchema.safeParse(data);
    if (result.success) {
        return { success: true, data: result.data };
    }
    return { success: false, error: result.error };
}

export function validateEmotionAxis(data: unknown): EmotionAxis {
    return EmotionAxisSchema.parse(data);
}

export function safeValidateEmotionAxis(data: unknown): { success: true; data: EmotionAxis } | { success: false; error: z.ZodError } {
    const result = EmotionAxisSchema.safeParse(data);
    if (result.success) {
        return { success: true, data: result.data };
    }
    return { success: false, error: result.error };
}

export function calculateConfidenceScore(partial: {
    coverage?: number;
    depth?: number;
    coherence?: number;
    specificity?: number;
}): ConfidenceScore {
    const coverage = partial.coverage ?? 0;
    const depth = partial.depth ?? 0;
    const coherence = partial.coherence ?? 0;
    const specificity = partial.specificity ?? 0;
    const total = coverage * 0.3 + depth * 0.3 + coherence * 0.2 + specificity * 0.2;
    return { coverage, depth, coherence, specificity, total };
}
