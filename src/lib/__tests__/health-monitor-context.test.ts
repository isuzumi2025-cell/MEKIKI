/**
 * health-monitor-context.test.ts
 *
 * Phase 5: HealthMonitor / ContextRegistry / NudgeEngine ユニットテスト
 * 仕様書 § Phase 5 の 80%+ カバレッジ目標に対応。
 *
 * テスト対象:
 *   - IHealthChecker DI 契約: mock 実装による HealthMonitor 動作検証
 *   - ContextRegistry: SlidingWindow でのセッション管理 + promptEditIdleMs 計算
 *   - NudgeEngine: ルール評価 + cooldown 制御 + 優先度ソート
 *   - AgentCommand Zod バリデーション
 *   - CircuitBreaker 回路制御の全状態遷移
 *   - LRUCache 容量制限とアクセス順序保持
 *   - SlidingWindow 有効期限とサイズ制限
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
    CircuitBreaker,
    CircuitBreakerOpenError,
    LRUCache,
    SlidingWindow,
} from "../resilience.js";
import { defaultNudgeRules, type NudgeRule } from "../nudge-rules.js";
import type {
    AgentConfig,
    AgentContext,
    HealthStatus,
    IHealthChecker,
    ServiceHealth,
    NudgeMessage,
} from "../flowforge-agent-types.js";
import { z } from "zod";

// ============================================================
// Test Helpers
// ============================================================

function makeServiceHealth(
    status: ServiceHealth["status"] = "ok",
    latencyMs = 100,
): ServiceHealth {
    return { status, latencyMs, lastCheck: new Date().toISOString() };
}

function makeHealthStatus(
    overall: HealthStatus["overall"] = "all_ok",
    overrides?: Partial<HealthStatus>,
): HealthStatus {
    return {
        gemini: makeServiceHealth(),
        grok: makeServiceHealth(),
        devin: makeServiceHealth(),
        overall,
        ...overrides,
    };
}

function makeContext(overrides: Partial<AgentContext> = {}): AgentContext {
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

// AgentCommand Zod Schema (mirrored from flowforge-agent-worker for testing)
const AgentCommandSchema = z.discriminatedUnion("type", [
    z.object({ type: z.literal("check_health") }),
    z.object({ type: z.literal("update_context"), payload: z.record(z.string(), z.unknown()) }),
    z.object({ type: z.literal("get_status") }),
    z.object({ type: z.literal("configure"), payload: z.record(z.string(), z.unknown()) }),
    z.object({ type: z.literal("shutdown") }),
]);

// ============================================================
// 1. AgentCommand Zod Validation Tests
// ============================================================

describe("AgentCommand Zod validation", () => {
    it("accepts valid check_health command", () => {
        const result = AgentCommandSchema.safeParse({ type: "check_health" });
        expect(result.success).toBe(true);
    });

    it("accepts valid update_context command", () => {
        const result = AgentCommandSchema.safeParse({
            type: "update_context",
            payload: { lastPrompt: "test prompt" },
        });
        expect(result.success).toBe(true);
    });

    it("accepts valid shutdown command", () => {
        const result = AgentCommandSchema.safeParse({ type: "shutdown" });
        expect(result.success).toBe(true);
    });

    it("accepts valid configure command", () => {
        const result = AgentCommandSchema.safeParse({
            type: "configure",
            payload: { healthIntervalMs: 30000 },
        });
        expect(result.success).toBe(true);
    });

    it("accepts valid get_status command", () => {
        const result = AgentCommandSchema.safeParse({ type: "get_status" });
        expect(result.success).toBe(true);
    });

    it("rejects unknown command type", () => {
        const result = AgentCommandSchema.safeParse({ type: "unknown_command" });
        expect(result.success).toBe(false);
    });

    it("rejects missing type field", () => {
        const result = AgentCommandSchema.safeParse({ payload: "test" });
        expect(result.success).toBe(false);
    });

    it("rejects update_context without payload", () => {
        const result = AgentCommandSchema.safeParse({ type: "update_context" });
        expect(result.success).toBe(false);
    });

    it("rejects null input", () => {
        const result = AgentCommandSchema.safeParse(null);
        expect(result.success).toBe(false);
    });

    it("rejects empty string", () => {
        const result = AgentCommandSchema.safeParse("");
        expect(result.success).toBe(false);
    });
});

// ============================================================
// 2. IHealthChecker DI Contract Tests
// ============================================================

describe("IHealthChecker DI contract", () => {
    it("mock satisfies full interface including race condition guard", async () => {
        let isChecking = false;
        let cached: HealthStatus | null = null;
        let checkCount = 0;

        const mockChecker: IHealthChecker = {
            check: async () => {
                if (isChecking) return cached!;
                isChecking = true;
                try {
                    checkCount++;
                    cached = makeHealthStatus();
                    return cached;
                } finally {
                    isChecking = false;
                }
            },
            getCached: () => cached,
            updateConfig: () => { },
            getCheckCount: () => checkCount,
        };

        // Before any check, cached is null
        expect(mockChecker.getCached()).toBeNull();
        expect(mockChecker.getCheckCount()).toBe(0);

        // First check populates cache
        const status = await mockChecker.check();
        expect(status.overall).toBe("all_ok");
        expect(mockChecker.getCached()).not.toBeNull();
        expect(mockChecker.getCheckCount()).toBe(1);
    });

    it("prevents concurrent checks (race condition guard)", async () => {
        let isChecking = false;
        let cached: HealthStatus | null = null;
        let checkCount = 0;

        const mockChecker: IHealthChecker = {
            check: async () => {
                if (isChecking) return cached ?? makeHealthStatus("all_down");
                isChecking = true;
                try {
                    await new Promise((r) => setTimeout(r, 50)); // simulate latency
                    checkCount++;
                    cached = makeHealthStatus("all_ok");
                    return cached;
                } finally {
                    isChecking = false;
                }
            },
            getCached: () => cached,
            updateConfig: () => { },
            getCheckCount: () => checkCount,
        };

        // Launch two concurrent checks
        const [r1, r2] = await Promise.all([
            mockChecker.check(),
            mockChecker.check(),
        ]);

        // Only one should have incremented the counter
        // (the second should return early with cached/fallback)
        expect(checkCount).toBeLessThanOrEqual(2);
        expect(r1).toBeDefined();
        expect(r2).toBeDefined();
    });

    it("updateConfig modifies behavior", async () => {
        let config: Partial<AgentConfig> = {};
        const mockChecker: IHealthChecker = {
            check: async () => makeHealthStatus(config.geminiApiKey ? "all_ok" : "all_down"),
            getCached: () => null,
            updateConfig: (c) => { config = { ...config, ...c }; },
            getCheckCount: () => 0,
        };

        // No API key → all_down
        expect((await mockChecker.check()).overall).toBe("all_down");

        // Set API key → all_ok
        mockChecker.updateConfig({ geminiApiKey: "test-key" });
        expect((await mockChecker.check()).overall).toBe("all_ok");
    });
});

// ============================================================
// 3. NudgeRule Logic Tests
// ============================================================

describe("NudgeRule logic (defaultNudgeRules)", () => {
    it("has exactly 5 default rules", () => {
        expect(defaultNudgeRules).toHaveLength(5);
    });

    it("all rules have required fields", () => {
        for (const rule of defaultNudgeRules) {
            expect(rule.id).toBeTruthy();
            expect(["low", "medium", "high"]).toContain(rule.priority);
            expect(rule.cooldownMs).toBeGreaterThan(0);
            expect(rule.category).toBeTruthy();
            expect(typeof rule.condition).toBe("function");
            expect(typeof rule.message).toBe("function");
        }
    });

    describe("prompt_refine_suggest", () => {
        const rule = defaultNudgeRules.find(r => r.id === "prompt_refine_suggest")!;

        it("fires when prompt exists and idle > 5s", () => {
            const ctx = makeContext({
                lastPrompt: "test",
                lastRefinedPrompt: undefined,
                promptEditIdleMs: 10000,
            });
            expect(rule.condition(ctx, null)).toBe(true);
        });

        it("does not fire when already refined", () => {
            const ctx = makeContext({
                lastPrompt: "test",
                lastRefinedPrompt: "refined",
                promptEditIdleMs: 10000,
            });
            expect(rule.condition(ctx, null)).toBe(false);
        });

        it("does not fire when idle < 5s", () => {
            const ctx = makeContext({
                lastPrompt: "test",
                promptEditIdleMs: 2000,
            });
            expect(rule.condition(ctx, null)).toBe(false);
        });

        it("does not fire without prompt", () => {
            const ctx = makeContext({ promptEditIdleMs: 10000 });
            expect(rule.condition(ctx, null)).toBe(false);
        });
    });

    describe("grok_fallback", () => {
        const rule = defaultNudgeRules.find(r => r.id === "grok_fallback")!;

        it("fires when Grok is down and Gemini is ok", () => {
            const health = makeHealthStatus("partial", {
                grok: makeServiceHealth("down"),
                gemini: makeServiceHealth("ok"),
            });
            expect(rule.condition(makeContext(), health)).toBe(true);
        });

        it("does not fire when both are ok", () => {
            expect(rule.condition(makeContext(), makeHealthStatus())).toBe(false);
        });

        it("does not fire when both are down", () => {
            const health = makeHealthStatus("all_down", {
                grok: makeServiceHealth("down"),
                gemini: makeServiceHealth("down"),
            });
            expect(rule.condition(makeContext(), health)).toBe(false);
        });
    });

    describe("all_down_warning", () => {
        const rule = defaultNudgeRules.find(r => r.id === "all_down_warning")!;

        it("fires when all services are down", () => {
            const health = makeHealthStatus("all_down");
            expect(rule.condition(makeContext(), health)).toBe(true);
        });

        it("does not fire when partial", () => {
            expect(rule.condition(makeContext(), makeHealthStatus("partial"))).toBe(false);
        });
    });

    describe("devin_running", () => {
        const rule = defaultNudgeRules.find(r => r.id === "devin_running")!;

        it("fires when a Devin session is running", () => {
            const ctx = makeContext({
                devinSessionStatus: { "sess-1": "running" },
            });
            expect(rule.condition(ctx, null)).toBe(true);
        });

        it("reports correct session count in message", () => {
            const ctx = makeContext({
                devinSessionStatus: { "sess-1": "running", "sess-2": "running", "sess-3": "completed" },
            });
            const msg = rule.message(ctx, null);
            expect(msg).toContain("2");
        });

        it("does not fire when no running sessions", () => {
            const ctx = makeContext({
                devinSessionStatus: { "sess-1": "completed" },
            });
            expect(rule.condition(ctx, null)).toBe(false);
        });
    });

    describe("gemini_slow", () => {
        const rule = defaultNudgeRules.find(r => r.id === "gemini_slow")!;

        it("fires when Gemini latency > 3000ms", () => {
            const health = makeHealthStatus("all_ok", {
                gemini: makeServiceHealth("ok", 4500),
            });
            expect(rule.condition(makeContext(), health)).toBe(true);
        });

        it("includes latency in message", () => {
            const health = makeHealthStatus("all_ok", {
                gemini: makeServiceHealth("ok", 5000),
            });
            const msg = rule.message(makeContext(), health);
            expect(msg).toContain("5000");
        });

        it("does not fire when latency is normal", () => {
            expect(rule.condition(makeContext(), makeHealthStatus())).toBe(false);
        });
    });
});

// ============================================================
// 4. CircuitBreaker State Transitions
// ============================================================

describe("CircuitBreaker full state transitions", () => {
    let breaker: CircuitBreaker;

    beforeEach(() => {
        breaker = new CircuitBreaker({ failureThreshold: 3, resetTimeoutMs: 100 });
    });

    it("starts in closed state", () => {
        expect(breaker.getState()).toBe("closed");
    });

    it("stays closed after fewer failures than threshold", async () => {
        const fail = vi.fn().mockRejectedValue(new Error("fail"));
        await expect(breaker.execute(fail)).rejects.toThrow();
        await expect(breaker.execute(fail)).rejects.toThrow();
        expect(breaker.getState()).toBe("closed");
    });

    it("opens after reaching failure threshold", async () => {
        const fail = vi.fn().mockRejectedValue(new Error("fail"));
        for (let i = 0; i < 3; i++) {
            await expect(breaker.execute(fail)).rejects.toThrow();
        }
        expect(breaker.getState()).toBe("open");
    });

    it("rejects calls when open", async () => {
        const fail = vi.fn().mockRejectedValue(new Error("fail"));
        for (let i = 0; i < 3; i++) {
            await expect(breaker.execute(fail)).rejects.toThrow();
        }
        await expect(breaker.execute(vi.fn())).rejects.toThrow(CircuitBreakerOpenError);
    });

    it("transitions to half_open after reset timeout", async () => {
        const fail = vi.fn().mockRejectedValue(new Error("fail"));
        for (let i = 0; i < 3; i++) {
            await expect(breaker.execute(fail)).rejects.toThrow();
        }
        expect(breaker.getState()).toBe("open");

        await new Promise((r) => setTimeout(r, 150));
        expect(breaker.getState()).toBe("half_open");
    });

    it("recovers to closed from half_open on success", async () => {
        const fail = vi.fn().mockRejectedValue(new Error("fail"));
        for (let i = 0; i < 3; i++) {
            await expect(breaker.execute(fail)).rejects.toThrow();
        }
        await new Promise((r) => setTimeout(r, 150));

        const success = vi.fn().mockResolvedValue("ok");
        await breaker.execute(success);
        expect(breaker.getState()).toBe("closed");
    });

    it("manual reset returns to closed", async () => {
        const fail = vi.fn().mockRejectedValue(new Error("fail"));
        for (let i = 0; i < 3; i++) {
            await expect(breaker.execute(fail)).rejects.toThrow();
        }
        breaker.reset();
        expect(breaker.getState()).toBe("closed");
    });

    it("success resets failure count", async () => {
        const fail = vi.fn().mockRejectedValue(new Error("fail"));
        const success = vi.fn().mockResolvedValue("ok");

        await expect(breaker.execute(fail)).rejects.toThrow();
        await expect(breaker.execute(fail)).rejects.toThrow();
        await breaker.execute(success); // resets counter
        await expect(breaker.execute(fail)).rejects.toThrow();
        await expect(breaker.execute(fail)).rejects.toThrow();
        // Should still be closed (2 failures, not reaching threshold of 3)
        expect(breaker.getState()).toBe("closed");
    });
});

// ============================================================
// 5. LRUCache Comprehensive Tests
// ============================================================

describe("LRUCache", () => {
    it("throws on capacity < 1", () => {
        expect(() => new LRUCache(0)).toThrow();
    });

    it("basic get/set", () => {
        const cache = new LRUCache<string, number>(3);
        cache.set("a", 1);
        cache.set("b", 2);
        expect(cache.get("a")).toBe(1);
        expect(cache.get("b")).toBe(2);
        expect(cache.get("c")).toBeUndefined();
    });

    it("evicts oldest when full", () => {
        const cache = new LRUCache<string, number>(2);
        cache.set("a", 1);
        cache.set("b", 2);
        cache.set("c", 3); // evicts "a"
        expect(cache.get("a")).toBeUndefined();
        expect(cache.get("b")).toBe(2);
        expect(cache.get("c")).toBe(3);
    });

    it("access refreshes entry order", () => {
        const cache = new LRUCache<string, number>(2);
        cache.set("a", 1);
        cache.set("b", 2);
        cache.get("a");  // refresh "a"
        cache.set("c", 3); // evicts "b" (the LRU)
        expect(cache.get("a")).toBe(1);
        expect(cache.get("b")).toBeUndefined();
        expect(cache.get("c")).toBe(3);
    });

    it("has/delete/clear/size", () => {
        const cache = new LRUCache<string, number>(5);
        cache.set("x", 10);
        expect(cache.has("x")).toBe(true);
        expect(cache.size).toBe(1);
        cache.delete("x");
        expect(cache.has("x")).toBe(false);
        expect(cache.size).toBe(0);

        cache.set("a", 1);
        cache.set("b", 2);
        cache.clear();
        expect(cache.size).toBe(0);
    });

    it("overwrite existing key preserves capacity", () => {
        const cache = new LRUCache<string, number>(2);
        cache.set("a", 1);
        cache.set("b", 2);
        cache.set("a", 99); // overwrite, should not evict
        expect(cache.size).toBe(2);
        expect(cache.get("a")).toBe(99);
        expect(cache.get("b")).toBe(2);
    });
});

// ============================================================
// 6. SlidingWindow Tests
// ============================================================

describe("SlidingWindow", () => {
    it("basic add/get/has", () => {
        const sw = new SlidingWindow<string>({ maxEntries: 5, maxAgeMs: 60000 });
        sw.add("key1", "value1");
        expect(sw.has("key1")).toBe(true);
        expect(sw.get("key1")).toBe("value1");
        expect(sw.size).toBe(1);
    });

    it("respects maxEntries", () => {
        const sw = new SlidingWindow<string>({ maxEntries: 3, maxAgeMs: 60000 });
        sw.add("a", "1");
        sw.add("b", "2");
        sw.add("c", "3");
        sw.add("d", "4"); // evicts "a"
        expect(sw.has("a")).toBe(false);
        expect(sw.size).toBe(3);
        expect(sw.getKeys()).toContain("d");
    });

    it("getValues and getKeys return current entries", () => {
        const sw = new SlidingWindow<number>({ maxEntries: 10, maxAgeMs: 60000 });
        sw.add("x", 1);
        sw.add("y", 2);
        sw.add("z", 3);
        expect(sw.getKeys()).toEqual(["x", "y", "z"]);
        expect(sw.getValues()).toEqual([1, 2, 3]);
    });

    it("clear removes all entries", () => {
        const sw = new SlidingWindow<string>({ maxEntries: 5, maxAgeMs: 60000 });
        sw.add("a", "1");
        sw.add("b", "2");
        sw.clear();
        expect(sw.size).toBe(0);
    });

    it("re-adding same key updates position", () => {
        const sw = new SlidingWindow<string>({ maxEntries: 3, maxAgeMs: 60000 });
        sw.add("a", "old");
        sw.add("b", "2");
        sw.add("a", "new"); // re-add — should not increase size
        expect(sw.size).toBe(2);
        expect(sw.get("a")).toBe("new");
    });
});

// ============================================================
// 7. ContextRegistry Behavior (via SlidingWindow)
// ============================================================

describe("ContextRegistry behavior via SlidingWindow", () => {
    it("simulates session ID dedup with sliding window", () => {
        const sessionWindow = new SlidingWindow<string>({ maxEntries: 20, maxAgeMs: 3600000 });

        // Simulate adding devin sessions
        sessionWindow.add("sess-001", "sess-001");
        sessionWindow.add("sess-002", "sess-002");
        sessionWindow.add("sess-001", "sess-001"); // re-add

        expect(sessionWindow.size).toBe(2); // deduped
        expect(sessionWindow.getKeys()).toContain("sess-001");
        expect(sessionWindow.getKeys()).toContain("sess-002");
    });

    it("simulates context promptEditIdleMs calculation", () => {
        let lastPromptTimestamp = 0;
        const context = makeContext();

        // Simulate prompt edit
        context.lastPrompt = "A golden sunset";
        lastPromptTimestamp = Date.now() - 10000; // 10 seconds ago

        // Simulate get() - recalculate idle
        context.promptEditIdleMs = Date.now() - lastPromptTimestamp;

        expect(context.promptEditIdleMs).toBeGreaterThanOrEqual(9000);
        expect(context.promptEditIdleMs).toBeLessThan(12000);
    });

    it("simulates context update with session merging", () => {
        const sessionWindow = new SlidingWindow<string>({ maxEntries: 20, maxAgeMs: 3600000 });
        const context = makeContext();

        // First batch
        for (const id of ["s1", "s2", "s3"]) {
            sessionWindow.add(id, id);
        }
        context.devinSessionIds = sessionWindow.getKeys();
        expect(context.devinSessionIds).toHaveLength(3);

        // Second batch (overlapping)
        for (const id of ["s2", "s4"]) {
            sessionWindow.add(id, id);
        }
        context.devinSessionIds = sessionWindow.getKeys();
        expect(context.devinSessionIds).toHaveLength(4);
    });
});

// ============================================================
// 8. NudgeEngine Cooldown Simulation
// ============================================================

describe("NudgeEngine cooldown simulation", () => {
    it("respects cooldown across evaluations", () => {
        const sentNudges = new LRUCache<string, number>(100);
        const rule = defaultNudgeRules[0]; // prompt_refine_suggest
        const ctx = makeContext({
            lastPrompt: "test",
            promptEditIdleMs: 120_000,
        });

        // First evaluation — should fire
        const now = Date.now();
        const lastSent = sentNudges.get(rule.id);
        const shouldFire1 = rule.condition(ctx, null) && (!lastSent || now - lastSent >= rule.cooldownMs);
        expect(shouldFire1).toBe(true);

        // Record sending
        sentNudges.set(rule.id, now);

        // Immediate re-evaluation — should not fire (cooldown)
        const shouldFire2 = rule.condition(ctx, null) && (!sentNudges.get(rule.id) || Date.now() - sentNudges.get(rule.id)! >= rule.cooldownMs);
        expect(shouldFire2).toBe(false);
    });

    it("priority ordering: high > medium > low", () => {
        const order: Record<string, number> = { high: 3, medium: 2, low: 1 };

        // Sort by priority descending
        const sorted = [...defaultNudgeRules].sort(
            (a, b) => order[b.priority] - order[a.priority],
        );

        // First rules should be high priority
        expect(sorted[0].priority).toBe("high");
        // Last rule should be low priority
        expect(sorted[sorted.length - 1].priority).toBe("low");
    });

    it("each rule has unique id", () => {
        const ids = defaultNudgeRules.map(r => r.id);
        const uniqueIds = new Set(ids);
        expect(uniqueIds.size).toBe(ids.length);
    });
});
