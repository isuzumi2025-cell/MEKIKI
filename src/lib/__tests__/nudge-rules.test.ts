/**
 * nudge-rules.test.ts — Unit tests for NudgeRule definitions
 */

import { describe, it, expect } from "vitest";
import { defaultNudgeRules } from "../nudge-rules.js";
import type { AgentContext, HealthStatus, ServiceHealth } from "../flowforge-agent-types.js";

function makeContext(overrides?: Partial<AgentContext>): AgentContext {
    return {
        activeFlowShotCount: 0,
        devinSessionIds: [],
        devinSessionStatus: {},
        toneMannerCached: false,
        lastActivity: new Date().toISOString(),
        promptEditIdleMs: 0,
        ...overrides,
    };
}

function makeHealth(overrides?: {
    gemini?: Partial<ServiceHealth>;
    grok?: Partial<ServiceHealth>;
    devin?: Partial<ServiceHealth>;
}): HealthStatus {
    const base: ServiceHealth = { status: "ok", latencyMs: 100, lastCheck: new Date().toISOString() };
    return {
        gemini: { ...base, ...overrides?.gemini },
        grok: { ...base, ...overrides?.grok },
        devin: { ...base, ...overrides?.devin },
        overall: "all_ok",
    };
}

describe("defaultNudgeRules", () => {
    it("has expected number of rules", () => {
        expect(defaultNudgeRules.length).toBe(5);
    });

    it("each rule has required fields", () => {
        for (const rule of defaultNudgeRules) {
            expect(rule.id).toBeTruthy();
            expect(rule.priority).toBeTruthy();
            expect(rule.cooldownMs).toBeGreaterThan(0);
            expect(typeof rule.condition).toBe("function");
            expect(typeof rule.message).toBe("function");
            expect(rule.category).toBeTruthy();
        }
    });

    describe("prompt_refine_suggest", () => {
        const rule = defaultNudgeRules.find(r => r.id === "prompt_refine_suggest")!;

        it("triggers when prompt exists, not refined, and idle > 5s", () => {
            const ctx = makeContext({
                lastPrompt: "test prompt",
                lastRefinedPrompt: undefined,
                promptEditIdleMs: 6000,
            });
            expect(rule.condition(ctx, null)).toBe(true);
        });

        it("does not trigger when already refined", () => {
            const ctx = makeContext({
                lastPrompt: "test",
                lastRefinedPrompt: "refined",
                promptEditIdleMs: 10000,
            });
            expect(rule.condition(ctx, null)).toBe(false);
        });

        it("does not trigger when idle < 5s", () => {
            const ctx = makeContext({
                lastPrompt: "test",
                promptEditIdleMs: 2000,
            });
            expect(rule.condition(ctx, null)).toBe(false);
        });
    });

    describe("grok_fallback", () => {
        const rule = defaultNudgeRules.find(r => r.id === "grok_fallback")!;

        it("triggers when grok is down but gemini is ok", () => {
            const health = makeHealth({ grok: { status: "down" } });
            expect(rule.condition(makeContext(), health)).toBe(true);
        });

        it("does not trigger when both are ok", () => {
            const health = makeHealth();
            expect(rule.condition(makeContext(), health)).toBe(false);
        });
    });

    describe("all_down_warning", () => {
        const rule = defaultNudgeRules.find(r => r.id === "all_down_warning")!;

        it("triggers when overall is all_down", () => {
            const health = makeHealth();
            health.overall = "all_down";
            expect(rule.condition(makeContext(), health)).toBe(true);
        });

        it("does not trigger when partial", () => {
            const health = makeHealth();
            health.overall = "partial";
            expect(rule.condition(makeContext(), health)).toBe(false);
        });
    });

    describe("devin_running", () => {
        const rule = defaultNudgeRules.find(r => r.id === "devin_running")!;

        it("triggers when sessions are running", () => {
            const ctx = makeContext({
                devinSessionStatus: { s1: "running", s2: "completed" },
            });
            expect(rule.condition(ctx, null)).toBe(true);
        });

        it("does not trigger when no sessions running", () => {
            const ctx = makeContext({
                devinSessionStatus: { s1: "completed" },
            });
            expect(rule.condition(ctx, null)).toBe(false);
        });
    });

    describe("gemini_slow", () => {
        const rule = defaultNudgeRules.find(r => r.id === "gemini_slow")!;

        it("triggers when gemini latency > 3000ms", () => {
            const health = makeHealth({ gemini: { latencyMs: 5000 } });
            expect(rule.condition(makeContext(), health)).toBe(true);
        });

        it("does not trigger when latency is normal", () => {
            const health = makeHealth({ gemini: { latencyMs: 500 } });
            expect(rule.condition(makeContext(), health)).toBe(false);
        });
    });
});
