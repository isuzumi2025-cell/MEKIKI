/**
 * resilience.test.ts — Unit tests for CircuitBreaker, LRUCache, SlidingWindow
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { CircuitBreaker, CircuitBreakerOpenError, LRUCache, SlidingWindow } from "../resilience.js";

// ============================================================
// CircuitBreaker
// ============================================================

describe("CircuitBreaker", () => {
    it("executes successfully in closed state", async () => {
        const cb = new CircuitBreaker();
        const result = await cb.execute(async () => 42);
        expect(result).toBe(42);
    });

    it("opens after reaching failure threshold", async () => {
        const cb = new CircuitBreaker({ failureThreshold: 2, resetTimeoutMs: 1000 });

        const fail = async () => {
            throw new Error("fail");
        };

        await expect(cb.execute(fail)).rejects.toThrow("fail");
        await expect(cb.execute(fail)).rejects.toThrow("fail");
        await expect(cb.execute(fail)).rejects.toThrow(CircuitBreakerOpenError);
    });

    it("transitions to half-open after reset timeout", async () => {
        vi.useFakeTimers();
        const cb = new CircuitBreaker({ failureThreshold: 1, resetTimeoutMs: 500 });

        await expect(cb.execute(async () => { throw new Error("fail"); })).rejects.toThrow("fail");
        await expect(cb.execute(async () => 1)).rejects.toThrow(CircuitBreakerOpenError);

        vi.advanceTimersByTime(600);

        const result = await cb.execute(async () => "recovered");
        expect(result).toBe("recovered");

        vi.useRealTimers();
    });
});

// ============================================================
// LRUCache
// ============================================================

describe("LRUCache", () => {
    let cache: LRUCache<string, number>;

    beforeEach(() => {
        cache = new LRUCache<string, number>(3);
    });

    it("stores and retrieves values", () => {
        cache.set("a", 1);
        cache.set("b", 2);
        expect(cache.get("a")).toBe(1);
        expect(cache.get("b")).toBe(2);
    });

    it("returns undefined for missing keys", () => {
        expect(cache.get("missing")).toBeUndefined();
    });

    it("evicts oldest entry when capacity exceeded", () => {
        cache.set("a", 1);
        cache.set("b", 2);
        cache.set("c", 3);
        cache.set("d", 4);
        expect(cache.has("a")).toBe(false);
        expect(cache.has("d")).toBe(true);
        expect(cache.size).toBe(3);
    });

    it("refreshes entry on get (moves to most recent)", () => {
        cache.set("a", 1);
        cache.set("b", 2);
        cache.set("c", 3);
        cache.get("a");
        cache.set("d", 4);
        expect(cache.has("a")).toBe(true);
        expect(cache.has("b")).toBe(false);
    });

    it("updates existing key without eviction", () => {
        cache.set("a", 1);
        cache.set("b", 2);
        cache.set("c", 3);
        cache.set("a", 10);
        expect(cache.get("a")).toBe(10);
        expect(cache.size).toBe(3);
    });

    it("deletes entries", () => {
        cache.set("a", 1);
        expect(cache.delete("a")).toBe(true);
        expect(cache.has("a")).toBe(false);
        expect(cache.size).toBe(0);
    });

    it("clears all entries", () => {
        cache.set("a", 1);
        cache.set("b", 2);
        cache.clear();
        expect(cache.size).toBe(0);
    });

    it("throws on invalid capacity", () => {
        expect(() => new LRUCache(0)).toThrow("LRU capacity must be >= 1");
    });
});

// ============================================================
// SlidingWindow
// ============================================================

describe("SlidingWindow", () => {
    it("adds and retrieves entries", () => {
        const sw = new SlidingWindow<string>({ maxEntries: 5, maxAgeMs: 60000 });
        sw.add("k1", "v1");
        sw.add("k2", "v2");
        expect(sw.has("k1")).toBe(true);
        expect(sw.get("k1")).toBe("v1");
        expect(sw.size).toBe(2);
    });

    it("evicts oldest when maxEntries exceeded", () => {
        const sw = new SlidingWindow<string>({ maxEntries: 2, maxAgeMs: 60000 });
        sw.add("k1", "v1");
        sw.add("k2", "v2");
        sw.add("k3", "v3");
        expect(sw.has("k1")).toBe(false);
        expect(sw.has("k3")).toBe(true);
        expect(sw.size).toBe(2);
    });

    it("prunes expired entries", () => {
        vi.useFakeTimers();
        const sw = new SlidingWindow<string>({ maxEntries: 10, maxAgeMs: 1000 });
        sw.add("k1", "v1");
        vi.advanceTimersByTime(1500);
        expect(sw.has("k1")).toBe(false);
        expect(sw.size).toBe(0);
        vi.useRealTimers();
    });

    it("returns keys and values", () => {
        const sw = new SlidingWindow<number>({ maxEntries: 5, maxAgeMs: 60000 });
        sw.add("a", 1);
        sw.add("b", 2);
        expect(sw.getKeys()).toEqual(["a", "b"]);
        expect(sw.getValues()).toEqual([1, 2]);
    });

    it("clears all entries", () => {
        const sw = new SlidingWindow<string>({ maxEntries: 5, maxAgeMs: 60000 });
        sw.add("k1", "v1");
        sw.clear();
        expect(sw.size).toBe(0);
    });

    it("updates existing key timestamp", () => {
        vi.useFakeTimers();
        const sw = new SlidingWindow<string>({ maxEntries: 5, maxAgeMs: 2000 });
        sw.add("k1", "v1");
        vi.advanceTimersByTime(1500);
        sw.add("k1", "v1_updated");
        vi.advanceTimersByTime(1000);
        expect(sw.has("k1")).toBe(true);
        expect(sw.get("k1")).toBe("v1_updated");
        vi.useRealTimers();
    });
});
