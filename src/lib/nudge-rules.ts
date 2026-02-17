/**
 * nudge-rules.ts
 *
 * NudgeEngine プラグイン — 宣言的ルール配列。
 * ルールを追加・削除するだけで NudgeEngine の振る舞いを拡張可能。
 *
 * FlowForge SDK — Agent Layer (Nudge Rules)
 */

import type { AgentContext, HealthStatus, NudgeMessage } from "./flowforge-agent-types.js";

export interface NudgeRule {
    id: string;
    priority: NudgeMessage["priority"];
    cooldownMs: number;
    condition: (context: AgentContext, health: HealthStatus | null) => boolean;
    message: (context: AgentContext, health: HealthStatus | null) => string;
    category: NudgeMessage["category"];
    action?: string;
}

export const defaultNudgeRules: NudgeRule[] = [
    {
        id: "prompt_refine_suggest",
        priority: "medium",
        cooldownMs: 30_000,
        category: "prompt",
        action: "refine_prompt",
        condition: (ctx) =>
            !!ctx.lastPrompt &&
            !ctx.lastRefinedPrompt &&
            ctx.promptEditIdleMs > 5000,
        message: () =>
            "プロンプトが入力されています。自動強化を実行しますか？",
    },
    {
        id: "grok_fallback",
        priority: "high",
        cooldownMs: 120_000,
        category: "health",
        action: "switch_gemini_only",
        condition: (_ctx, health) =>
            health?.grok.status === "down" && health.gemini.status === "ok",
        message: () =>
            "Grok API が応答しません。Gemini-only モードに切り替えることを推奨します。",
    },
    {
        id: "all_down_warning",
        priority: "high",
        cooldownMs: 60_000,
        category: "health",
        condition: (_ctx, health) => health?.overall === "all_down",
        message: () =>
            "全ての API が応答していません。ネットワーク接続を確認してください。",
    },
    {
        id: "devin_running",
        priority: "low",
        cooldownMs: 60_000,
        category: "devin",
        action: "check_devin_progress",
        condition: (ctx) =>
            Object.values(ctx.devinSessionStatus).some((s) => s === "running"),
        message: (ctx) => {
            const count = Object.values(ctx.devinSessionStatus).filter(
                (s) => s === "running",
            ).length;
            return `Devin セッション ${count}件が実行中です。`;
        },
    },
    {
        id: "gemini_slow",
        priority: "medium",
        cooldownMs: 120_000,
        category: "optimization",
        action: "switch_light_mode",
        condition: (_ctx, health) =>
            health?.gemini.status === "ok" && health.gemini.latencyMs > 3000,
        message: (_ctx, health) =>
            `Gemini のレスポンスが遅延しています (${health?.gemini.latencyMs ?? 0}ms)。light モードを推奨します。`,
    },
];
