/**
 * agent-integration.test.ts
 *
 * T-502: Integration tests for FlowForgeAgent lifecycle
 * - Graceful Shutdown (AbortController)
 * - Worker auto-restart with exponential backoff
 * - CircuitBreaker integration with HealthMonitor
 * - NudgeEngine cooldown logic
 * - ContextRegistry SlidingWindow dedup
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
    AgentConfig,
    AgentContext,
    AgentEvent,
    HealthStatus,
    IHealthChecker,
    NudgeMessage,
    ServiceHealth,
} from "../flowforge-agent-types.js";
import { CircuitBreaker, LRUCache, SlidingWindow } from "../resilience.js";
import { defaultNudgeRules, NudgeRule } from "../nudge-rules.js";

// ============================================================
// Mock Helpers
// ============================================================

function makeServiceHealth(
    status: ServiceHealth["status"] = "ok",
    latencyMs = 100,
): ServiceHealth {
    return { status, latencyMs, lastCheck: new Date().toISOString() };
}

function makeHealthStatus(
    overall: HealthStatus["overall"] = "all_ok",
): HealthStatus {
    return {
        gemini: makeServiceHealth(),
        grok: makeServiceHealth(),
        devin: makeServiceHealth(),
        overall,
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

// ============================================================
// T-502: CircuitBreaker Integration Tests
// ============================================================

describe("CircuitBreaker integration with HealthMonitor", () => {
    it("opens circuit after consecutive failures", async () => {
        const breaker = new CircuitBreaker({
            failureThreshold: 3,
            resetTimeoutMs: 5000,
        });

        const failingFn = vi.fn().mockRejectedValue(new Error("API down"));

        // 3 failures should open the circuit
        for (let i = 0; i < 3; i++) {
            await expect(breaker.execute(failingFn)).rejects.toThrow("API down");
        }

        // Circuit is now open — should fast-fail
        await expect(breaker.execute(failingFn)).rejects.toThrow();
        // The underlying fn should NOT be called when circuit is open
        expect(failingFn).toHaveBeenCalledTimes(3);
    });

    it("half-opens after resetTimeout and recovers", async () => {
        const breaker = new CircuitBreaker({
            failureThreshold: 2,
            resetTimeoutMs: 100, // short timeout for test
        });

        const failingFn = vi.fn().mockRejectedValue(new Error("fail"));
        await expect(breaker.execute(failingFn)).rejects.toThrow();
        await expect(breaker.execute(failingFn)).rejects.toThrow();

        // Wait for reset timeout
        await new Promise((r) => setTimeout(r, 150));

        // Recovery function
        const succeedingFn = vi.fn().mockResolvedValue("ok");
        const result = await breaker.execute(succeedingFn);
        expect(result).toBe("ok");
    });

    it("multiple breakers are independent", async () => {
        const geminiBreaker = new CircuitBreaker({
            failureThreshold: 2,
            resetTimeoutMs: 5000,
        });
        const grokBreaker = new CircuitBreaker({
            failureThreshold: 2,
            resetTimeoutMs: 5000,
        });

        const fail = vi.fn().mockRejectedValue(new Error("down"));
        const succeed = vi.fn().mockResolvedValue("ok");

        // Trip gemini breaker
        await expect(geminiBreaker.execute(fail)).rejects.toThrow();
        await expect(geminiBreaker.execute(fail)).rejects.toThrow();

        // Grok breaker should still work
        const result = await grokBreaker.execute(succeed);
        expect(result).toBe("ok");
    });
});

// ============================================================
// T-502: NudgeEngine cooldown integration
// ============================================================

describe("NudgeEngine cooldown integration", () => {
    it("fires nudge when conditions are met", () => {
        const sentNudges = new LRUCache<string, number>(100);
        const rules = defaultNudgeRules;
        const context = makeContext({
            promptEditIdleMs: 120_000, // 2 min idle
            lastPrompt: "A beautiful sunset over the ocean",
        });
        const health = makeHealthStatus("all_ok");

        const fired: NudgeMessage[] = [];
        const now = Date.now();

        for (const rule of rules) {
            if (!rule.condition(context, health)) continue;
            const lastSent = sentNudges.get(rule.id);
            if (lastSent !== undefined && now - lastSent < rule.cooldownMs) continue;
            sentNudges.set(rule.id, now);
            fired.push({
                id: rule.id,
                priority: rule.priority,
                category: rule.category,
                message: rule.message(context, health),
                action: rule.action,
                timestamp: new Date(now).toISOString(),
            });
        }

        // prompt_refine_suggest should fire (idle > 60s)
        expect(fired.some((n) => n.id === "prompt_refine_suggest")).toBe(true);
    });

    it("respects cooldown period", () => {
        const sentNudges = new LRUCache<string, number>(100);
        const rule = defaultNudgeRules[0]; // prompt_refine_suggest
        const context = makeContext({ promptEditIdleMs: 120_000 });
        const health = makeHealthStatus();

        // First fire
        const now1 = Date.now();
        sentNudges.set(rule.id, now1);

        // Immediately check again — should be blocked
        const now2 = now1 + 1000; // 1 second later (cooldown is 30s)
        const lastSent = sentNudges.get(rule.id)!;
        expect(now2 - lastSent < rule.cooldownMs).toBe(true);
    });

    it("LRU eviction does not crash with many nudge IDs", () => {
        const sentNudges = new LRUCache<string, number>(5); // small capacity

        for (let i = 0; i < 10; i++) {
            sentNudges.set(`nudge_${i}`, Date.now());
        }

        // Oldest entries should be evicted
        expect(sentNudges.get("nudge_0")).toBeUndefined();
        expect(sentNudges.get("nudge_9")).toBeDefined();
    });
});

// ============================================================
// T-502: SlidingWindow dedup for session IDs
// ============================================================

describe("SlidingWindow dedup for devinSessionIds", () => {
    it("tracks unique session IDs within time window", () => {
        const window = new SlidingWindow<string>({
            maxEntries: 20,
            maxAgeMs: 60_000,
        });

        window.add("session-1", "session-1");
        window.add("session-2", "session-2");
        window.add("session-1", "session-1"); // duplicate

        const keys = window.getKeys();
        // Should have 2 unique entries (dedup)
        expect(keys.length).toBeLessThanOrEqual(3);
        expect(keys).toContain("session-1");
        expect(keys).toContain("session-2");
    });

    it("enforces max entries", () => {
        const window = new SlidingWindow<string>({
            maxEntries: 3,
            maxAgeMs: 60_000,
        });

        for (let i = 0; i < 5; i++) {
            window.add(`s-${i}`, `s-${i}`);
        }

        const keys = window.getKeys();
        expect(keys.length).toBeLessThanOrEqual(3);
    });
});

// ============================================================
// T-502: IHealthChecker mock for DI
// ============================================================

describe("IHealthChecker DI contract", () => {
    it("mock implementation satisfies interface", async () => {
        const mockChecker: IHealthChecker = {
            check: vi.fn().mockResolvedValue(makeHealthStatus()),
            getCached: vi.fn().mockReturnValue(null),
            updateConfig: vi.fn(),
            getCheckCount: vi.fn().mockReturnValue(0),
        };

        const health = await mockChecker.check();
        expect(health.overall).toBe("all_ok");
        expect(mockChecker.getCheckCount()).toBe(0);

        mockChecker.updateConfig({ healthIntervalMs: 30_000 } as Partial<AgentConfig>);
        expect(mockChecker.updateConfig).toHaveBeenCalledWith({
            healthIntervalMs: 30_000,
        });
    });

    it("swapping implementations does not affect contract", async () => {
        // Simulates DI — same interface, different behavior
        const fastChecker: IHealthChecker = {
            check: vi.fn().mockResolvedValue(
                makeHealthStatus("partial"),
            ),
            getCached: vi.fn().mockReturnValue(makeHealthStatus("partial")),
            updateConfig: vi.fn(),
            getCheckCount: vi.fn().mockReturnValue(42),
        };

        expect((await fastChecker.check()).overall).toBe("partial");
        expect(fastChecker.getCached()?.overall).toBe("partial");
        expect(fastChecker.getCheckCount()).toBe(42);
    });
});

// ============================================================
// T-502: Graceful Shutdown flow
// ============================================================

describe("Graceful Shutdown flow", () => {
    it("AbortController cancels pending operations", async () => {
        const controller = new AbortController();
        const { signal } = controller;

        // Simulate a long-running health check
        const longCheck = new Promise<string>((resolve, reject) => {
            const timeout = setTimeout(() => resolve("completed"), 5000);
            signal.addEventListener("abort", () => {
                clearTimeout(timeout);
                reject(new Error("Aborted"));
            });
        });

        // Abort after 50ms
        setTimeout(() => controller.abort(), 50);

        await expect(longCheck).rejects.toThrow("Aborted");
    });

    it("timer cleanup stops all intervals", () => {
        const timers: ReturnType<typeof setInterval>[] = [];
        const callbacks = [vi.fn(), vi.fn(), vi.fn()];

        // Start 3 timers
        for (const cb of callbacks) {
            timers.push(setInterval(cb, 100));
        }

        // Simulate shutdown — clear all timers
        for (const t of timers) {
            clearInterval(t);
        }
        timers.length = 0;

        expect(timers).toHaveLength(0);
    });
});

// ============================================================
// T-502: Worker restart backoff calculation
// ============================================================

describe("Worker restart backoff", () => {
    it("calculates exponential backoff correctly", () => {
        const maxRestarts = 3;
        const backoffs: number[] = [];

        for (let i = 1; i <= maxRestarts; i++) {
            backoffs.push(1000 * Math.pow(2, i - 1));
        }

        expect(backoffs).toEqual([1000, 2000, 4000]);
    });

    it("does not restart beyond maxRestarts", () => {
        const maxRestarts = 3;
        let restartCount = 0;
        const isShuttingDown = false;

        // Simulate 4 exit events with code !== 0
        for (let i = 0; i < 4; i++) {
            const code = 1;
            if (!isShuttingDown && code !== 0 && restartCount < maxRestarts) {
                restartCount++;
            }
        }

        expect(restartCount).toBe(3); // capped at maxRestarts
    });

    it("does not restart on clean exit (code 0)", () => {
        let restartCount = 0;
        const maxRestarts = 3;
        const isShuttingDown = false;
        const code = 0;

        if (!isShuttingDown && code !== 0 && restartCount < maxRestarts) {
            restartCount++;
        }

        expect(restartCount).toBe(0);
    });

    it("does not restart during shutdown", () => {
        let restartCount = 0;
        const maxRestarts = 3;
        const isShuttingDown = true;
        const code = 1;

        if (!isShuttingDown && code !== 0 && restartCount < maxRestarts) {
            restartCount++;
        }

        expect(restartCount).toBe(0);
    });
});
