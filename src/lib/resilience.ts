/**
 * resilience.ts
 *
 * 回路ブレーカー (Circuit Breaker) パターン実装。
 * 連続失敗時に回路を開放し、下流サービスへの過負荷を防ぐ。
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
