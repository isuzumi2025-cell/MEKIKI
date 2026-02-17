/**
 * flowforge-agent-worker.ts
 *
 * Worker Thread 内で稼働する自律エージェント本体
 *
 * - HealthMonitor: API 疎通を定期チェック（60秒 TTL）
 * - ContextRegistry: 最新コンテキストを保持
 * - NudgeEngine: ルールベースで処理提案を発行
 *
 * メインスレッドとは MessagePort のみで通信する。
 * このファイルは Worker Thread として起動される前提。
 *
 * FlowForge SDK — Agent Layer (Worker)
 */

import { parentPort } from "node:worker_threads";
import { z } from "zod";

import type {
    AgentCommand,
    AgentEvent,
    AgentConfig,
    AgentContext,
    AgentStatus,
    HealthStatus,
    ServiceHealth,
    NudgeMessage,
    IHealthChecker,
} from "./flowforge-agent-types.js";

import { CircuitBreaker } from "./resilience.js";
import { defaultNudgeRules, type NudgeRule } from "./nudge-rules.js";

// ============================================================
// Re-export types for backward compatibility
// ============================================================

export type {
    AgentCommand,
    AgentEvent,
    AgentConfig,
    AgentContext,
    AgentStatus,
    HealthStatus,
    ServiceHealth,
    NudgeMessage,
    IHealthChecker,
};

// ============================================================
// T-002: Zod バリデーション
// ============================================================

const AgentCommandSchema = z.discriminatedUnion("type", [
    z.object({ type: z.literal("check_health") }),
    z.object({ type: z.literal("update_context"), payload: z.record(z.string(), z.unknown()) }),
    z.object({ type: z.literal("get_status") }),
    z.object({ type: z.literal("configure"), payload: z.record(z.string(), z.unknown()) }),
    z.object({ type: z.literal("shutdown") }),
]);

// ============================================================
// T-010: LRU キャッシュ (最大100件)
// ============================================================

class LRUCache<T> {
    private capacity: number;
    private cache = new Map<string, T>();

    constructor(capacity: number) {
        this.capacity = capacity;
    }

    has(key: string): boolean {
        if (!this.cache.has(key)) return false;
        const value = this.cache.get(key) as T;
        this.cache.delete(key);
        this.cache.set(key, value);
        return true;
    }

    set(key: string, value: T): void {
        if (this.cache.has(key)) {
            this.cache.delete(key);
        } else if (this.cache.size >= this.capacity) {
            const oldest = this.cache.keys().next().value;
            if (oldest !== undefined) {
                this.cache.delete(oldest);
            }
        }
        this.cache.set(key, value);
    }

    delete(key: string): void {
        this.cache.delete(key);
    }

    clear(): void {
        this.cache.clear();
    }

    get size(): number {
        return this.cache.size;
    }
}

// ============================================================
// T-011: スライディングウィンドウ (最大20件, 1時間超削除)
// ============================================================

interface TimestampedEntry {
    value: string;
    addedAt: number;
}

class SlidingWindowSet {
    private entries: TimestampedEntry[] = [];
    private maxSize: number;
    private maxAgeMs: number;

    constructor(maxSize: number, maxAgeMs: number) {
        this.maxSize = maxSize;
        this.maxAgeMs = maxAgeMs;
    }

    add(value: string): void {
        this.prune();
        const idx = this.entries.findIndex((e) => e.value === value);
        if (idx !== -1) {
            this.entries[idx] = { value, addedAt: Date.now() };
            return;
        }
        if (this.entries.length >= this.maxSize) {
            this.entries.shift();
        }
        this.entries.push({ value, addedAt: Date.now() });
    }

    getValues(): string[] {
        this.prune();
        return this.entries.map((e) => e.value);
    }

    private prune(): void {
        const now = Date.now();
        this.entries = this.entries.filter(
            (e) => now - e.addedAt < this.maxAgeMs,
        );
    }
}

// ============================================================
// T-008: DefaultHealthChecker (implements IHealthChecker)
// ============================================================

class DefaultHealthChecker implements IHealthChecker {
    private cache: HealthStatus | null = null;
    private checkCount = 0;
    private config: AgentConfig;
    private isChecking = false; // T-006: レース条件防止
    private breakers: Record<string, CircuitBreaker>;
    private abortController: AbortController;

    constructor(config: AgentConfig, abortController: AbortController) {
        this.config = config;
        this.abortController = abortController;
        this.breakers = {
            gemini: new CircuitBreaker(),
            grok: new CircuitBreaker(),
            devin: new CircuitBreaker(),
        };
    }

    updateConfig(config: Partial<AgentConfig>): void {
        Object.assign(this.config, config);
    }

    getCached(): HealthStatus | null {
        return this.cache;
    }

    async check(): Promise<HealthStatus> {
        // T-006: 同時実行防止
        if (this.isChecking) {
            if (this.cache) return this.cache;
            return {
                gemini: { status: "unconfigured", latencyMs: 0, lastCheck: new Date().toISOString() },
                grok: { status: "unconfigured", latencyMs: 0, lastCheck: new Date().toISOString() },
                devin: { status: "unconfigured", latencyMs: 0, lastCheck: new Date().toISOString() },
                overall: "all_down",
            };
        }

        this.isChecking = true;
        try {
            this.checkCount++;

            const [gemini, grok, devin] = await Promise.all([
                this.checkGemini(),
                this.checkGrok(),
                this.checkDevin(),
            ]);

            const statuses = [gemini.status, grok.status, devin.status];
            const okCount = statuses.filter((s) => s === "ok").length;
            const configuredCount = statuses.filter((s) => s !== "unconfigured").length;

            let overall: HealthStatus["overall"];
            if (okCount === configuredCount && configuredCount > 0) overall = "all_ok";
            else if (okCount > 0) overall = "partial";
            else overall = "all_down";

            this.cache = { gemini, grok, devin, overall };
            return this.cache;
        } finally {
            this.isChecking = false;
        }
    }

    getCheckCount(): number {
        return this.checkCount;
    }

    // T-001: API キーを Header に移動
    private async checkGemini(): Promise<ServiceHealth> {
        if (!this.config.geminiApiKey) {
            return { status: "unconfigured", latencyMs: 0, lastCheck: new Date().toISOString() };
        }

        const start = Date.now();
        try {
            const result = await this.breakers.gemini.execute(async () => {
                const url = "https://generativelanguage.googleapis.com/v1beta/models";
                const res = await fetch(url, {
                    method: "GET",
                    headers: { "x-goog-api-key": this.config.geminiApiKey! },
                    signal: this.abortController.signal.aborted
                        ? AbortSignal.timeout(10000)
                        : AbortSignal.any([this.abortController.signal, AbortSignal.timeout(10000)]),
                });
                return res;
            });
            const latency = Date.now() - start;

            return {
                status: result.ok ? "ok" : "degraded",
                latencyMs: latency,
                lastCheck: new Date().toISOString(),
                error: result.ok ? undefined : `HTTP ${result.status}`,
            };
        } catch (error) {
            return {
                status: "down",
                latencyMs: Date.now() - start,
                lastCheck: new Date().toISOString(),
                error: (error as Error).message,
            };
        }
    }

    private async checkGrok(): Promise<ServiceHealth> {
        if (!this.config.grokApiKey) {
            return { status: "unconfigured", latencyMs: 0, lastCheck: new Date().toISOString() };
        }

        const start = Date.now();
        try {
            const result = await this.breakers.grok.execute(async () => {
                const res = await fetch("https://api.x.ai/v1/models", {
                    method: "GET",
                    headers: { Authorization: `Bearer ${this.config.grokApiKey}` },
                    signal: this.abortController.signal.aborted
                        ? AbortSignal.timeout(10000)
                        : AbortSignal.any([this.abortController.signal, AbortSignal.timeout(10000)]),
                });
                return res;
            });
            const latency = Date.now() - start;

            return {
                status: result.ok ? "ok" : "degraded",
                latencyMs: latency,
                lastCheck: new Date().toISOString(),
                error: result.ok ? undefined : `HTTP ${result.status}`,
            };
        } catch (error) {
            return {
                status: "down",
                latencyMs: Date.now() - start,
                lastCheck: new Date().toISOString(),
                error: (error as Error).message,
            };
        }
    }

    private async checkDevin(): Promise<ServiceHealth> {
        if (!this.config.devinApiKey || this.config.devinApiKey === "your_devin_api_key_here") {
            return { status: "unconfigured", latencyMs: 0, lastCheck: new Date().toISOString() };
        }

        const start = Date.now();
        const base = this.config.devinBaseUrl ?? "https://api.devin.ai/v1";
        try {
            const result = await this.breakers.devin.execute(async () => {
                const res = await fetch(`${base}/sessions?limit=1`, {
                    method: "GET",
                    headers: { Authorization: `Bearer ${this.config.devinApiKey}` },
                    signal: this.abortController.signal.aborted
                        ? AbortSignal.timeout(10000)
                        : AbortSignal.any([this.abortController.signal, AbortSignal.timeout(10000)]),
                });
                return res;
            });
            const latency = Date.now() - start;

            return {
                status: result.ok ? "ok" : "degraded",
                latencyMs: latency,
                lastCheck: new Date().toISOString(),
                error: result.ok ? undefined : `HTTP ${result.status}`,
            };
        } catch (error) {
            return {
                status: "down",
                latencyMs: Date.now() - start,
                lastCheck: new Date().toISOString(),
                error: (error as Error).message,
            };
        }
    }
}

// ============================================================
// ContextRegistry (T-011 applied)
// ============================================================

class ContextRegistry {
    private context: AgentContext = {
        activeFlowShotCount: 0,
        devinSessionIds: [],
        devinSessionStatus: {},
        toneMannerCached: false,
        lastActivity: new Date().toISOString(),
        promptEditIdleMs: 0,
    };

    private lastPromptTimestamp = 0;
    private sessionWindow = new SlidingWindowSet(20, 60 * 60 * 1000);

    get(): AgentContext {
        if (this.lastPromptTimestamp > 0) {
            this.context.promptEditIdleMs = Date.now() - this.lastPromptTimestamp;
        }
        this.context.devinSessionIds = this.sessionWindow.getValues();
        return { ...this.context };
    }

    update(partial: Partial<AgentContext>): void {
        if (partial.devinSessionIds) {
            for (const id of partial.devinSessionIds) {
                this.sessionWindow.add(id);
            }
            delete partial.devinSessionIds;
        }
        Object.assign(this.context, partial);
        this.context.lastActivity = new Date().toISOString();

        if (partial.lastPrompt) {
            this.lastPromptTimestamp = Date.now();
        }
    }
}

// ============================================================
// NudgeEngine (T-009 + T-010 applied)
// ============================================================

class NudgeEngine {
    private nudgeCount = 0;
    private sentNudgeIds = new LRUCache<number>(100);
    private rules: NudgeRule[];

    constructor(rules?: NudgeRule[]) {
        this.rules = rules ?? defaultNudgeRules;
    }

    evaluate(
        context: AgentContext,
        health: HealthStatus | null,
    ): NudgeMessage[] {
        const now = Date.now();
        const nudges: NudgeMessage[] = [];

        for (const rule of this.rules) {
            if (!rule.condition(context, health)) continue;

            if (this.sentNudgeIds.has(rule.id)) {
                const lastSent = this.sentNudgeIds.has(rule.id) ? now : 0;
                if (lastSent > 0) continue;
            }

            nudges.push({
                id: rule.id,
                priority: rule.priority,
                category: rule.category,
                message: rule.message(context, health),
                action: rule.action,
                timestamp: new Date().toISOString(),
            });
        }

        const newNudges = nudges.filter((n) => !this.sentNudgeIds.has(n.id));
        for (const n of newNudges) {
            this.sentNudgeIds.set(n.id, now);
            this.nudgeCount++;
        }

        return newNudges;
    }

    resetNudge(id: string): void {
        this.sentNudgeIds.delete(id);
    }

    resetAll(): void {
        this.sentNudgeIds.clear();
    }

    getNudgeCount(): number {
        return this.nudgeCount;
    }
}

// ============================================================
// Worker メインループ (T-004: Graceful Shutdown)
// ============================================================

if (parentPort) {
    const port = parentPort;

    const abortController = new AbortController();

    const config: AgentConfig = {
        healthIntervalMs: 60_000,
        nudgeIntervalMs: 30_000,
    };

    const healthMonitor: IHealthChecker = new DefaultHealthChecker(config, abortController);
    const contextRegistry = new ContextRegistry();
    const nudgeEngine = new NudgeEngine();
    const startTime = Date.now();

    const timers: ReturnType<typeof setInterval>[] = [];

    function emit(event: AgentEvent): void {
        port.postMessage(event);
    }

    // ヘルスチェックループ
    const healthTimer = setInterval(async () => {
        if (abortController.signal.aborted) return;
        try {
            const health = await healthMonitor.check();
            emit({ type: "health_update", payload: health });

            const ctx = contextRegistry.get();
            const nudges = nudgeEngine.evaluate(ctx, health);
            for (const nudge of nudges) {
                emit({ type: "nudge", payload: nudge });
            }
        } catch (error) {
            emit({ type: "error", payload: (error as Error).message });
        }
    }, config.healthIntervalMs);
    timers.push(healthTimer);

    // ナッジ評価ループ
    const nudgeTimer = setInterval(() => {
        if (abortController.signal.aborted) return;
        const ctx = contextRegistry.get();
        const health = healthMonitor.getCached();
        const nudges = nudgeEngine.evaluate(ctx, health);
        for (const nudge of nudges) {
            emit({ type: "nudge", payload: nudge });
        }
    }, config.nudgeIntervalMs);
    timers.push(nudgeTimer);

    // T-004: Graceful Shutdown
    function shutdown(): void {
        abortController.abort();
        for (const timer of timers) {
            clearInterval(timer);
        }
        timers.length = 0;
        emit({ type: "shutdown_complete" });
    }

    // T-002: Zod バリデーション付きメッセージハンドラ
    port.on("message", async (raw: unknown) => {
        const parsed = AgentCommandSchema.safeParse(raw);
        if (!parsed.success) {
            emit({ type: "error", payload: `Invalid command: ${parsed.error.message}` });
            return;
        }

        const command = parsed.data as AgentCommand;

        switch (command.type) {
            case "check_health": {
                try {
                    const health = await healthMonitor.check();
                    emit({ type: "health_update", payload: health });
                } catch (error) {
                    emit({ type: "error", payload: (error as Error).message });
                }
                break;
            }
            case "update_context": {
                contextRegistry.update(command.payload as Partial<AgentContext>);
                emit({ type: "context_sync", payload: contextRegistry.get() });
                break;
            }
            case "get_status": {
                const status: AgentStatus = {
                    uptime: Date.now() - startTime,
                    healthChecks: healthMonitor.getCheckCount(),
                    nudgesSent: nudgeEngine.getNudgeCount(),
                    lastHealthCheck: healthMonitor.getCached()?.gemini.lastCheck,
                    config,
                    context: contextRegistry.get(),
                    health: healthMonitor.getCached() ?? undefined,
                };
                emit({ type: "status", payload: status });
                break;
            }
            case "configure": {
                Object.assign(config, command.payload);
                healthMonitor.updateConfig(command.payload as Partial<AgentConfig>);
                break;
            }
            case "shutdown": {
                shutdown();
                break;
            }
        }
    });

    emit({ type: "ready" });
}
