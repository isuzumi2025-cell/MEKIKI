/**
 * resilience.ts
 *
 * 耐障害性ユーティリティ — 回路ブレーカー + LRU キャッシュ + スライディングウィンドウ
 *
 * FlowForge SDK — Resilience Layer
 */

export type CircuitState = "closed" | "open" | "half_open";

export interface CircuitBreakerOptions {
    failureThreshold: number;
    resetTimeoutMs: number;
}

const DEFAULT_OPTIONS: CircuitBreakerOptions = {
    failureThreshold: 5,
    resetTimeoutMs: 60_000,
};

export class CircuitBreakerOpenError extends Error {
    constructor() {
        super("Circuit breaker is open");
        this.name = "CircuitBreakerOpenError";
    }
}

export class CircuitBreaker {
    private state: CircuitState = "closed";
    private failureCount = 0;
    private lastFailureTime = 0;
    private readonly options: CircuitBreakerOptions;

    constructor(options?: Partial<CircuitBreakerOptions>) {
        this.options = { ...DEFAULT_OPTIONS, ...options };
    }

    getState(): CircuitState {
        this.evaluateState();
        return this.state;
    }

    async execute<T>(fn: () => Promise<T>): Promise<T> {
        this.evaluateState();

        if (this.state === "open") {
            throw new CircuitBreakerOpenError();
        }

        try {
            const result = await fn();
            this.onSuccess();
            return result;
        } catch (error) {
            this.onFailure();
            throw error;
        }
    }

    reset(): void {
        this.state = "closed";
        this.failureCount = 0;
        this.lastFailureTime = 0;
    }

    private evaluateState(): void {
        if (this.state === "open") {
            const elapsed = Date.now() - this.lastFailureTime;
            if (elapsed >= this.options.resetTimeoutMs) {
                this.state = "half_open";
            }
        }
    }

    private onSuccess(): void {
        this.failureCount = 0;
        this.state = "closed";
    }

    private onFailure(): void {
        this.failureCount++;
        this.lastFailureTime = Date.now();
        if (this.failureCount >= this.options.failureThreshold) {
            this.state = "open";
        }
    }
}

// ============================================================
// LRU キャッシュ
// ============================================================

export class LRUCache<K, V> {
    private readonly capacity: number;
    private readonly cache: Map<K, V>;

    constructor(capacity: number) {
        if (capacity < 1) throw new Error("LRU capacity must be >= 1");
        this.capacity = capacity;
        this.cache = new Map();
    }

    get(key: K): V | undefined {
        if (!this.cache.has(key)) return undefined;
        const value = this.cache.get(key)!;
        this.cache.delete(key);
        this.cache.set(key, value);
        return value;
    }

    set(key: K, value: V): void {
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

    has(key: K): boolean {
        return this.cache.has(key);
    }

    delete(key: K): boolean {
        return this.cache.delete(key);
    }

    get size(): number {
        return this.cache.size;
    }

    clear(): void {
        this.cache.clear();
    }
}

// ============================================================
// スライディングウィンドウ
// ============================================================

export interface SlidingWindowOptions {
    maxEntries: number;
    maxAgeMs: number;
}

const DEFAULT_SW_OPTIONS: SlidingWindowOptions = {
    maxEntries: 20,
    maxAgeMs: 3_600_000,
};

interface TimestampedEntry<T> {
    value: T;
    timestamp: number;
}

export class SlidingWindow<T> {
    private readonly options: SlidingWindowOptions;
    private entries: Map<string, TimestampedEntry<T>>;

    constructor(options?: Partial<SlidingWindowOptions>) {
        this.options = { ...DEFAULT_SW_OPTIONS, ...options };
        this.entries = new Map();
    }

    add(key: string, value: T): void {
        this.prune();
        if (this.entries.has(key)) {
            this.entries.delete(key);
        } else if (this.entries.size >= this.options.maxEntries) {
            const oldest = this.entries.keys().next().value;
            if (oldest !== undefined) {
                this.entries.delete(oldest);
            }
        }
        this.entries.set(key, { value, timestamp: Date.now() });
    }

    get(key: string): T | undefined {
        this.prune();
        return this.entries.get(key)?.value;
    }

    has(key: string): boolean {
        this.prune();
        return this.entries.has(key);
    }

    getValues(): T[] {
        this.prune();
        return [...this.entries.values()].map(e => e.value);
    }

    getKeys(): string[] {
        this.prune();
        return [...this.entries.keys()];
    }

    get size(): number {
        this.prune();
        return this.entries.size;
    }

    clear(): void {
        this.entries.clear();
    }

    private prune(): void {
        const now = Date.now();
        for (const [key, entry] of this.entries) {
            if (now - entry.timestamp >= this.options.maxAgeMs) {
                this.entries.delete(key);
            }
        }
    }
}
