/**
 * streaming-axis-output.ts
 *
 * T-603: ストリーミング出力 — 7軸プロンプト解析を段階的にUIに配信
 *
 * AsyncGenerator ベースのストリーミングアーキテクチャ:
 * - 各軸の解析完了時にリアルタイム通知
 * - 部分結果 (PartialResult) を段階的に蓄積
 * - エラー耐性: 一部軸の失敗が全体をブロックしない
 * - 進捗コールバック対応
 *
 * FlowForge SDK — Streaming Layer
 */

import { z } from "zod";
import type {
    GrokAxes,
    OpusAxes,
    EmotionAxis,
    ConfidenceScore,
    PromptUnderstandingInput,
} from "./prompt-understanding-schemas.js";
import {
    safeValidateGrokAxes,
    safeValidateOpusAxes,
    safeValidateEmotionAxis,
    calculateConfidenceScore,
} from "./prompt-understanding-schemas.js";

// ============================================================
// Types
// ============================================================

export type AxisId = "A1" | "A2" | "A3" | "A4" | "A5" | "A6" | "A7";

export type AxisStatus = "pending" | "running" | "completed" | "failed";

export interface AxisProgress {
    axisId: AxisId;
    label: string;
    status: AxisStatus;
    startedAt?: string;
    completedAt?: string;
    durationMs?: number;
    error?: string;
}

export interface StreamEvent {
    type: "axis_start" | "axis_complete" | "axis_error" | "progress" | "final";
    axisId?: AxisId;
    timestamp: string;
    progress: AxisProgress[];
    /** Percentage 0–100 */
    overallProgress: number;
    partialResult?: PartialAxisResult;
    finalResult?: FinalAxisResult;
}

export interface PartialAxisResult {
    grokAxes?: GrokAxes;
    opusAxes?: OpusAxes;
    emotionAxis?: EmotionAxis;
}

export interface FinalAxisResult extends PartialAxisResult {
    confidence: ConfidenceScore;
    processedAt: string;
    totalDurationMs: number;
    axisResults: AxisProgress[];
}

// ============================================================
// Axis metadata
// ============================================================

const AXIS_META: Record<AxisId, { label: string; group: "grok" | "opus" | "emotion" }> = {
    A1: { label: "トレンドワード解釈", group: "grok" },
    A2: { label: "文化的コンテキスト", group: "grok" },
    A3: { label: "ビジュアルトレンド", group: "grok" },
    A4: { label: "Remotionマッピング", group: "opus" },
    A5: { label: "エフェクト構造", group: "opus" },
    A6: { label: "CSS/SVG/WebGL", group: "opus" },
    A7: { label: "感情分析", group: "emotion" },
};

// ============================================================
// AxisAnalyzer — pluggable analysis function type
// ============================================================

export type AxisAnalyzerFn<T> = (
    input: PromptUnderstandingInput,
    signal?: AbortSignal,
) => Promise<T>;

export interface AxisAnalyzers {
    grok?: AxisAnalyzerFn<GrokAxes>;
    opus?: AxisAnalyzerFn<OpusAxes>;
    emotion?: AxisAnalyzerFn<EmotionAxis>;
}

// ============================================================
// StreamingAxisPipeline
// ============================================================

export class StreamingAxisPipeline {
    private analyzers: AxisAnalyzers;
    private readonly axesOrder: AxisId[];

    constructor(
        analyzers: AxisAnalyzers,
        axesOrder?: AxisId[],
    ) {
        this.analyzers = analyzers;
        this.axesOrder = axesOrder ?? ["A1", "A2", "A3", "A4", "A5", "A6", "A7"];
    }

    /**
     * ストリーミング解析を実行、各軸完了ごとに StreamEvent を yield
     */
    async *analyze(
        input: PromptUnderstandingInput,
        signal?: AbortSignal,
    ): AsyncGenerator<StreamEvent> {
        const startTime = Date.now();
        const requestedAxes = input.includeAxes ?? this.axesOrder;

        // Initialize progress
        const progress: AxisProgress[] = requestedAxes.map((axisId) => ({
            axisId,
            label: AXIS_META[axisId]?.label ?? axisId,
            status: "pending" as AxisStatus,
        }));

        const partial: PartialAxisResult = {};
        let completedCount = 0;

        // Emit initial progress
        yield this.makeEvent("progress", undefined, progress, 0, partial);

        // Group axes by analyzer: grok (A1-A3), opus (A4-A6), emotion (A7)
        const grokAxes = requestedAxes.filter((a) => ["A1", "A2", "A3"].includes(a));
        const opusAxes = requestedAxes.filter((a) => ["A4", "A5", "A6"].includes(a));
        const emotionAxes = requestedAxes.filter((a) => a === "A7");

        // Run groups concurrently but emit per-axis events
        const tasks: Promise<void>[] = [];

        if (grokAxes.length > 0 && this.analyzers.grok) {
            tasks.push(
                this.runGroup(grokAxes, "grok", input, signal, progress, partial, () => {
                    completedCount += grokAxes.length;
                }),
            );
        } else {
            grokAxes.forEach((id) => this.markSkipped(progress, id));
            completedCount += grokAxes.length;
        }

        if (opusAxes.length > 0 && this.analyzers.opus) {
            tasks.push(
                this.runGroup(opusAxes, "opus", input, signal, progress, partial, () => {
                    completedCount += opusAxes.length;
                }),
            );
        } else {
            opusAxes.forEach((id) => this.markSkipped(progress, id));
            completedCount += opusAxes.length;
        }

        if (emotionAxes.length > 0 && this.analyzers.emotion) {
            tasks.push(
                this.runGroup(emotionAxes, "emotion", input, signal, progress, partial, () => {
                    completedCount += emotionAxes.length;
                }),
            );
        } else {
            emotionAxes.forEach((id) => this.markSkipped(progress, id));
            completedCount += emotionAxes.length;
        }

        // Wait for all groups and yield intermediate events via polling
        const allDone = Promise.allSettled(tasks);
        let resolved = false;

        allDone.then(() => {
            resolved = true;
        });

        while (!resolved) {
            if (signal?.aborted) break;
            await new Promise((r) => setTimeout(r, 100));
            const pct = Math.round((completedCount / requestedAxes.length) * 100);
            yield this.makeEvent("progress", undefined, progress, pct, partial);
            if (resolved) break;
        }

        // Wait for actual completion
        await allDone;

        // Calculate confidence
        const completedAxesCount = progress.filter((p) => p.status === "completed").length;
        const confidence = calculateConfidenceScore({
            coverage: (completedAxesCount / requestedAxes.length) * 100,
            depth: completedAxesCount >= 6 ? 85 : completedAxesCount >= 3 ? 60 : 30,
            coherence: partial.grokAxes && partial.opusAxes ? 80 : 50,
            specificity: partial.emotionAxis ? 85 : 65,
        });

        // Emit final
        const finalResult: FinalAxisResult = {
            ...partial,
            confidence,
            processedAt: new Date().toISOString(),
            totalDurationMs: Date.now() - startTime,
            axisResults: progress,
        };

        yield this.makeEvent("final", undefined, progress, 100, partial, finalResult);
    }

    private async runGroup(
        axisIds: AxisId[],
        group: "grok" | "opus" | "emotion",
        input: PromptUnderstandingInput,
        signal: AbortSignal | undefined,
        progress: AxisProgress[],
        partial: PartialAxisResult,
        onComplete: () => void,
    ): Promise<void> {
        // Mark all axes in group as running
        for (const id of axisIds) {
            const entry = progress.find((p) => p.axisId === id);
            if (entry) {
                entry.status = "running";
                entry.startedAt = new Date().toISOString();
            }
        }

        try {
            const startMs = Date.now();
            let result: unknown;

            switch (group) {
                case "grok":
                    result = await this.analyzers.grok!(input, signal);
                    break;
                case "opus":
                    result = await this.analyzers.opus!(input, signal);
                    break;
                case "emotion":
                    result = await this.analyzers.emotion!(input, signal);
                    break;
            }

            const durationMs = Date.now() - startMs;

            // Validate and store
            if (group === "grok") {
                const validation = safeValidateGrokAxes(result);
                if (validation.success) {
                    partial.grokAxes = validation.data;
                }
            } else if (group === "opus") {
                const validation = safeValidateOpusAxes(result);
                if (validation.success) {
                    partial.opusAxes = validation.data;
                }
            } else if (group === "emotion") {
                const validation = safeValidateEmotionAxis(result);
                if (validation.success) {
                    partial.emotionAxis = validation.data;
                }
            }

            // Mark completed
            for (const id of axisIds) {
                const entry = progress.find((p) => p.axisId === id);
                if (entry) {
                    entry.status = "completed";
                    entry.completedAt = new Date().toISOString();
                    entry.durationMs = durationMs;
                }
            }

            onComplete();
        } catch (error) {
            const errMsg = error instanceof Error ? error.message : String(error);
            for (const id of axisIds) {
                const entry = progress.find((p) => p.axisId === id);
                if (entry) {
                    entry.status = "failed";
                    entry.completedAt = new Date().toISOString();
                    entry.error = errMsg;
                }
            }
            onComplete();
        }
    }

    private markSkipped(progress: AxisProgress[], axisId: AxisId): void {
        const entry = progress.find((p) => p.axisId === axisId);
        if (entry) {
            entry.status = "completed";
            entry.completedAt = new Date().toISOString();
            entry.durationMs = 0;
        }
    }

    private makeEvent(
        type: StreamEvent["type"],
        axisId: AxisId | undefined,
        progress: AxisProgress[],
        overallProgress: number,
        partialResult?: PartialAxisResult,
        finalResult?: FinalAxisResult,
    ): StreamEvent {
        return {
            type,
            axisId,
            timestamp: new Date().toISOString(),
            progress: [...progress],
            overallProgress,
            partialResult: partialResult ? { ...partialResult } : undefined,
            finalResult,
        };
    }
}

// ============================================================
// Convenience: callback-based streaming (for UI integration)
// ============================================================

export type StreamCallback = (event: StreamEvent) => void;

export async function streamAxisAnalysis(
    input: PromptUnderstandingInput,
    analyzers: AxisAnalyzers,
    callback: StreamCallback,
    signal?: AbortSignal,
): Promise<FinalAxisResult | null> {
    const pipeline = new StreamingAxisPipeline(analyzers);
    let finalResult: FinalAxisResult | null = null;

    for await (const event of pipeline.analyze(input, signal)) {
        callback(event);
        if (event.type === "final" && event.finalResult) {
            finalResult = event.finalResult;
        }
        if (signal?.aborted) break;
    }

    return finalResult;
}
