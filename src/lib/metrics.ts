/**
 * metrics.ts
 *
 * T-512: Metrics collection for FlowForge SDK
 *
 * Provides:
 * - LatencyHistogram: P50/P90/P99 latency tracking per operation
 * - ErrorRateTracker: Sliding-window error rate calculation
 * - MetricsRegistry: Central registry for all metrics
 *
 * Usage:
 *   const registry = new MetricsRegistry();
 *   registry.recordLatency("gemini_health_check", 150);
 *   registry.recordError("grok_health_check");
 *   const snapshot = registry.snapshot();
 */

// ============================================================
// LatencyHistogram
// ============================================================

export class LatencyHistogram {
    private readonly values: number[] = [];
    private readonly maxSamples: number;
    private count = 0;
    private sum = 0;

    constructor(maxSamples = 1000) {
        this.maxSamples = maxSamples;
    }

    record(latencyMs: number): void {
        this.values.push(latencyMs);
        this.count++;
        this.sum += latencyMs;
        if (this.values.length > this.maxSamples) {
            const removed = this.values.shift()!;
            this.sum -= removed;
        }
    }

    percentile(p: number): number {
        if (this.values.length === 0) return 0;
        const sorted = [...this.values].sort((a, b) => a - b);
        const idx = Math.ceil((p / 100) * sorted.length) - 1;
        return sorted[Math.max(0, idx)];
    }

    get p50(): number {
        return this.percentile(50);
    }
    get p90(): number {
        return this.percentile(90);
    }
    get p99(): number {
        return this.percentile(99);
    }

    get mean(): number {
        return this.values.length > 0 ? this.sum / this.values.length : 0;
    }

    get totalCount(): number {
        return this.count;
    }

    snapshot(): LatencySnapshot {
        return {
            p50: this.p50,
            p90: this.p90,
            p99: this.p99,
            mean: Math.round(this.mean * 100) / 100,
            count: this.count,
            min: this.values.length > 0 ? Math.min(...this.values) : 0,
            max: this.values.length > 0 ? Math.max(...this.values) : 0,
        };
    }
}

export interface LatencySnapshot {
    p50: number;
    p90: number;
    p99: number;
    mean: number;
    count: number;
    min: number;
    max: number;
}

// ============================================================
// ErrorRateTracker
// ============================================================

export class ErrorRateTracker {
    private readonly windowMs: number;
    private readonly entries: { timestamp: number; isError: boolean }[] = [];
    private totalRequests = 0;
    private totalErrors = 0;

    constructor(windowMs = 60_000) {
        this.windowMs = windowMs;
    }

    recordSuccess(): void {
        this.entries.push({ timestamp: Date.now(), isError: false });
        this.totalRequests++;
        this.prune();
    }

    recordError(): void {
        this.entries.push({ timestamp: Date.now(), isError: true });
        this.totalRequests++;
        this.totalErrors++;
        this.prune();
    }

    /** Current error rate within the sliding window (0-1) */
    get errorRate(): number {
        this.prune();
        if (this.entries.length === 0) return 0;
        const errors = this.entries.filter((e) => e.isError).length;
        return errors / this.entries.length;
    }

    /** Total requests seen (all time) */
    get totalRequestCount(): number {
        return this.totalRequests;
    }

    /** Total errors seen (all time) */
    get totalErrorCount(): number {
        return this.totalErrors;
    }

    snapshot(): ErrorRateSnapshot {
        return {
            windowErrorRate: Math.round(this.errorRate * 10000) / 10000,
            windowSize: this.entries.length,
            totalRequests: this.totalRequests,
            totalErrors: this.totalErrors,
            allTimeErrorRate:
                this.totalRequests > 0
                    ? Math.round((this.totalErrors / this.totalRequests) * 10000) / 10000
                    : 0,
        };
    }

    private prune(): void {
        const cutoff = Date.now() - this.windowMs;
        while (this.entries.length > 0 && this.entries[0].timestamp < cutoff) {
            this.entries.shift();
        }
    }
}

export interface ErrorRateSnapshot {
    windowErrorRate: number;
    windowSize: number;
    totalRequests: number;
    totalErrors: number;
    allTimeErrorRate: number;
}

// ============================================================
// MetricsRegistry
// ============================================================

export class MetricsRegistry {
    private readonly latencies = new Map<string, LatencyHistogram>();
    private readonly errors = new Map<string, ErrorRateTracker>();
    private readonly counters = new Map<string, number>();
    private readonly startTime = Date.now();

    recordLatency(operation: string, latencyMs: number): void {
        if (!this.latencies.has(operation)) {
            this.latencies.set(operation, new LatencyHistogram());
        }
        this.latencies.get(operation)!.record(latencyMs);
    }

    recordSuccess(operation: string): void {
        if (!this.errors.has(operation)) {
            this.errors.set(operation, new ErrorRateTracker());
        }
        this.errors.get(operation)!.recordSuccess();
    }

    recordError(operation: string): void {
        if (!this.errors.has(operation)) {
            this.errors.set(operation, new ErrorRateTracker());
        }
        this.errors.get(operation)!.recordError();
    }

    increment(counter: string, amount = 1): void {
        this.counters.set(
            counter,
            (this.counters.get(counter) ?? 0) + amount,
        );
    }

    getCounter(counter: string): number {
        return this.counters.get(counter) ?? 0;
    }

    snapshot(): MetricsSnapshot {
        const latencies: Record<string, LatencySnapshot> = {};
        for (const [k, v] of this.latencies) {
            latencies[k] = v.snapshot();
        }

        const errors: Record<string, ErrorRateSnapshot> = {};
        for (const [k, v] of this.errors) {
            errors[k] = v.snapshot();
        }

        const counters: Record<string, number> = {};
        for (const [k, v] of this.counters) {
            counters[k] = v;
        }

        return {
            uptimeMs: Date.now() - this.startTime,
            latencies,
            errors,
            counters,
        };
    }

    reset(): void {
        this.latencies.clear();
        this.errors.clear();
        this.counters.clear();
    }
}

export interface MetricsSnapshot {
    uptimeMs: number;
    latencies: Record<string, LatencySnapshot>;
    errors: Record<string, ErrorRateSnapshot>;
    counters: Record<string, number>;
}
