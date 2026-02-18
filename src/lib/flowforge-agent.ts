/**
 * flowforge-agent.ts
 *
 * メインスレッド側の AgentProxy — Worker Thread と MessagePort で通信
 *
 * シングルトンパターンで1インスタンスのみ起動。
 * イベントエミッターで nudge やヘルス更新を受信可能。
 *
 * FlowForge SDK — Agent Layer (Main Thread Proxy)
 */

import { Worker } from "node:worker_threads";
import { EventEmitter } from "node:events";
import { join } from "node:path";

import type {
    AgentCommand,
    AgentEvent,
    AgentConfig,
    AgentContext,
    AgentStatus,
    HealthStatus,
    NudgeMessage,
} from "./flowforge-agent-types.js";

// ============================================================
// FlowForgeAgent (Singleton Proxy)
// ============================================================

export interface FlowForgeAgentEvents {
    ready: [];
    health_update: [HealthStatus];
    nudge: [NudgeMessage];
    context_sync: [AgentContext];
    status: [AgentStatus];
    error: [string];
    worker_exit: [number];
    shutdown_complete: [];
}

export class FlowForgeAgent extends EventEmitter {
    private static instance: FlowForgeAgent | null = null;

    private worker: Worker | null = null;
    private isRunning = false;
    private lastHealth: HealthStatus | null = null;
    private lastContext: AgentContext | null = null;

    // T-005: Worker 自動再起動
    private restartCount = 0;
    private readonly maxRestarts = 3;
    private pendingConfig: Partial<AgentConfig> | undefined;
    private isShuttingDown = false;

    private constructor() {
        super();
    }

    // ─── シングルトン ─────────────────────────

    static getInstance(): FlowForgeAgent {
        if (!FlowForgeAgent.instance) {
            FlowForgeAgent.instance = new FlowForgeAgent();
        }
        return FlowForgeAgent.instance;
    }

    // ─── ライフサイクル ───────────────────────

    start(config?: Partial<AgentConfig>): void {
        if (this.isRunning) {
            return;
        }

        this.isShuttingDown = false;
        this.pendingConfig = config;
        this.spawnWorker(config);
    }

    stop(): void {
        if (this.worker) {
            this.isShuttingDown = true;
            this.send({ type: "shutdown" });
        }
    }

    get running(): boolean {
        return this.isRunning;
    }

    // ─── コマンド API ─────────────────────────

    checkHealth(): void {
        this.send({ type: "check_health" });
    }

    updateContext(context: Partial<AgentContext>): void {
        this.send({ type: "update_context", payload: context });
    }

    requestStatus(): void {
        this.send({ type: "get_status" });
    }

    configure(config: Partial<AgentConfig>): void {
        this.send({ type: "configure", payload: config });
    }

    // ─── キャッシュ取得（同期） ───────────────

    getLastHealth(): HealthStatus | null {
        return this.lastHealth;
    }

    getLastContext(): AgentContext | null {
        return this.lastContext;
    }

    // ─── Promise ベース API（便利メソッド） ──

    getHealth(): Promise<HealthStatus> {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error("Health check timed out (15s)"));
            }, 15000);

            this.once("health_update", (health: HealthStatus) => {
                clearTimeout(timeout);
                resolve(health);
            });

            this.checkHealth();
        });
    }

    getStatus(): Promise<AgentStatus> {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error("Status request timed out (5s)"));
            }, 5000);

            this.once("status", (status: AgentStatus) => {
                clearTimeout(timeout);
                resolve(status);
            });

            this.requestStatus();
        });
    }

    // ─── 内部処理 ─────────────────────────────

    private send(command: AgentCommand): void {
        if (this.worker) {
            this.worker.postMessage(command);
        }
    }

    private spawnWorker(config?: Partial<AgentConfig>): void {
        const workerPath = this.resolveWorkerPath();

        this.worker = new Worker(workerPath, {
            execArgv: ["--require", "tsx/cjs"],
            env: {
                ...process.env,
            },
        });

        this.worker.on("message", (event: AgentEvent) => {
            this.handleEvent(event);
        });

        this.worker.on("error", (error: Error) => {
            this.emit("error", error.message);
        });

        // T-005: exit イベントで自動再起動 (最大3回 + backoff)
        this.worker.on("exit", (code) => {
            this.isRunning = false;
            this.worker = null;
            this.emit("worker_exit", code);

            if (!this.isShuttingDown && code !== 0 && this.restartCount < this.maxRestarts) {
                this.restartCount++;
                const backoffMs = 1000 * Math.pow(2, this.restartCount - 1);
                setTimeout(() => {
                    if (!this.isShuttingDown) {
                        this.spawnWorker(this.pendingConfig);
                    }
                }, backoffMs);
            }
        });

        this.isRunning = true;

        if (config) {
            this.send({ type: "configure", payload: config });
        }
    }

    private handleEvent(event: AgentEvent): void {
        switch (event.type) {
            case "ready":
                this.restartCount = 0;
                this.emit("ready");
                break;
            case "health_update":
                this.lastHealth = event.payload;
                this.emit("health_update", event.payload);
                break;
            case "nudge":
                this.emit("nudge", event.payload);
                break;
            case "context_sync":
                this.lastContext = event.payload;
                this.emit("context_sync", event.payload);
                break;
            case "status":
                this.emit("status", event.payload);
                break;
            case "error":
                this.emit("error", event.payload);
                break;
            case "shutdown_complete":
                this.emit("shutdown_complete");
                break;
        }
    }

    private resolveWorkerPath(): string {
        const currentDir = typeof __dirname !== "undefined"
            ? __dirname
            : new URL(".", import.meta.url).pathname;
        return join(currentDir, "flowforge-agent-worker.ts");
    }
}
