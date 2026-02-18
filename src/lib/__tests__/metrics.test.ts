/**
 * metrics.test.ts
 *
 * T-512: Tests for metrics collection module
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
    LatencyHistogram,
    ErrorRateTracker,
    MetricsRegistry,
} from "../metrics.js";

// ============================================================
// LatencyHistogram
// ============================================================

describe("LatencyHistogram", () => {
    it("computes percentiles correctly", () => {
        const h = new LatencyHistogram();
        for (let i = 1; i <= 100; i++) {
            h.record(i);
        }
        expect(h.p50).toBe(50);
        expect(h.p90).toBe(90);
        expect(h.p99).toBe(99);
    });

    it("returns 0 for empty histogram", () => {
        const h = new LatencyHistogram();
        expect(h.p50).toBe(0);
        expect(h.mean).toBe(0);
    });

    it("computes mean correctly", () => {
        const h = new LatencyHistogram();
        h.record(100);
        h.record(200);
        h.record(300);
        expect(h.mean).toBe(200);
    });

    it("evicts old samples beyond maxSamples", () => {
        const h = new LatencyHistogram(5);
        for (let i = 0; i < 10; i++) {
            h.record(i * 100);
        }
        // p50 should be from recent values [500, 600, 700, 800, 900]
        const snap = h.snapshot();
        expect(snap.count).toBe(10); // total count tracks all
        expect(snap.min).toBe(500); // oldest retained
    });

    it("snapshot contains all fields", () => {
        const h = new LatencyHistogram();
        h.record(50);
        h.record(100);
        const snap = h.snapshot();
        expect(snap).toHaveProperty("p50");
        expect(snap).toHaveProperty("p90");
        expect(snap).toHaveProperty("p99");
        expect(snap).toHaveProperty("mean");
        expect(snap).toHaveProperty("count");
        expect(snap).toHaveProperty("min");
        expect(snap).toHaveProperty("max");
        expect(snap.min).toBe(50);
        expect(snap.max).toBe(100);
    });
});

// ============================================================
// ErrorRateTracker
// ============================================================

describe("ErrorRateTracker", () => {
    it("tracks error rate correctly", () => {
        const tracker = new ErrorRateTracker(60_000);
        tracker.recordSuccess();
        tracker.recordSuccess();
        tracker.recordError();
        tracker.recordSuccess();

        expect(tracker.errorRate).toBe(0.25); // 1/4
        expect(tracker.totalRequestCount).toBe(4);
        expect(tracker.totalErrorCount).toBe(1);
    });

    it("returns 0 for no requests", () => {
        const tracker = new ErrorRateTracker();
        expect(tracker.errorRate).toBe(0);
    });

    it("prunes entries outside window", async () => {
        const tracker = new ErrorRateTracker(100); // 100ms window
        tracker.recordError();
        tracker.recordError();

        // Wait for entries to expire
        await new Promise((r) => setTimeout(r, 150));

        tracker.recordSuccess();
        // Old errors should be pruned
        expect(tracker.errorRate).toBe(0); // only the success is in window
    });

    it("snapshot contains all fields", () => {
        const tracker = new ErrorRateTracker();
        tracker.recordSuccess();
        tracker.recordError();
        const snap = tracker.snapshot();
        expect(snap).toHaveProperty("windowErrorRate");
        expect(snap).toHaveProperty("windowSize");
        expect(snap).toHaveProperty("totalRequests");
        expect(snap).toHaveProperty("totalErrors");
        expect(snap).toHaveProperty("allTimeErrorRate");
        expect(snap.totalRequests).toBe(2);
        expect(snap.totalErrors).toBe(1);
        expect(snap.allTimeErrorRate).toBe(0.5);
    });
});

// ============================================================
// MetricsRegistry
// ============================================================

describe("MetricsRegistry", () => {
    it("records latency and error metrics", () => {
        const reg = new MetricsRegistry();
        reg.recordLatency("gemini_check", 100);
        reg.recordLatency("gemini_check", 200);
        reg.recordSuccess("gemini_check");
        reg.recordError("gemini_check");

        const snap = reg.snapshot();
        expect(snap.latencies["gemini_check"]).toBeDefined();
        expect(snap.latencies["gemini_check"].count).toBe(2);
        expect(snap.errors["gemini_check"]).toBeDefined();
        expect(snap.errors["gemini_check"].totalRequests).toBe(2);
    });

    it("increments counters", () => {
        const reg = new MetricsRegistry();
        reg.increment("nudges_sent");
        reg.increment("nudges_sent");
        reg.increment("nudges_sent", 3);
        expect(reg.getCounter("nudges_sent")).toBe(5);
        expect(reg.getCounter("nonexistent")).toBe(0);
    });

    it("reset clears all metrics", () => {
        const reg = new MetricsRegistry();
        reg.recordLatency("op", 100);
        reg.recordError("op");
        reg.increment("c");
        reg.reset();

        const snap = reg.snapshot();
        expect(Object.keys(snap.latencies)).toHaveLength(0);
        expect(Object.keys(snap.errors)).toHaveLength(0);
        expect(Object.keys(snap.counters)).toHaveLength(0);
    });

    it("snapshot includes uptime", () => {
        const reg = new MetricsRegistry();
        const snap = reg.snapshot();
        expect(snap.uptimeMs).toBeGreaterThanOrEqual(0);
    });

    it("handles multiple operations independently", () => {
        const reg = new MetricsRegistry();
        reg.recordLatency("gemini", 100);
        reg.recordLatency("grok", 200);
        reg.recordLatency("devin", 300);

        const snap = reg.snapshot();
        expect(snap.latencies["gemini"].mean).toBe(100);
        expect(snap.latencies["grok"].mean).toBe(200);
        expect(snap.latencies["devin"].mean).toBe(300);
    });
});
