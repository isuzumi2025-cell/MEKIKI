/**
 * load-test-agent.ts
 *
 * T-503: FlowForge Agent ロードテストスクリプト
 *
 * 指定した duration（デフォルト 3600s）の間 FlowForge Agent を起動し、
 * 60 秒ごとに process.memoryUsage() を記録。
 * heapUsed が初期値の 2 倍を超えた場合に警告を出力。
 * 終了時にサマリー（初期/最終/最大ヒープ、成功率、ナッジ数）を表示。
 */

import { FlowForgeAgent } from "../src/lib/flowforge-agent.js";
import type { HealthStatus, NudgeMessage } from "../src/lib/flowforge-agent-types.js";

// ─── CLI Argument Parsing ───────────────────────────

function parseDuration(args: string[]): number {
    const idx = args.indexOf("--duration");
    if (idx !== -1 && idx + 1 < args.length) {
        const val = Number(args[idx + 1]);
        if (!Number.isNaN(val) && val > 0) return val;
    }
    return 3600;
}

const durationSeconds = parseDuration(process.argv);
const MEMORY_SAMPLE_INTERVAL_MS = 60_000;

// ─── Types ──────────────────────────────────────────

interface MemorySample {
    timestampMs: number;
    rss: number;
    heapTotal: number;
    heapUsed: number;
    external: number;
}

interface LoadTestSummary {
    durationSeconds: number;
    actualDurationMs: number;
    initialHeap: number;
    finalHeap: number;
    maxHeap: number;
    heapWarnings: number;
    healthChecks: number;
    healthSuccessRate: number;
    nudgeCount: number;
    memorySamples: number;
}

// ─── State ──────────────────────────────────────────

const memorySamples: MemorySample[] = [];
let healthCheckTotal = 0;
let healthCheckSuccess = 0;
let nudgeTotal = 0;
let heapWarningCount = 0;
let initialHeapUsed = 0;

function sampleMemory(): MemorySample {
    const mem = process.memoryUsage();
    return {
        timestampMs: Date.now(),
        rss: mem.rss,
        heapTotal: mem.heapTotal,
        heapUsed: mem.heapUsed,
        external: mem.external,
    };
}

function formatBytes(bytes: number): string {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
}

// ─── Main ───────────────────────────────────────────

async function main(): Promise<void> {
    console.log("=== FlowForge Agent Load Test ===");
    console.log(`Duration: ${durationSeconds}s`);
    console.log(`Memory sample interval: ${MEMORY_SAMPLE_INTERVAL_MS / 1000}s`);
    console.log("");

    const agent = FlowForgeAgent.getInstance();
    const startTime = Date.now();

    const initial = sampleMemory();
    memorySamples.push(initial);
    initialHeapUsed = initial.heapUsed;

    console.log(`[${new Date().toISOString()}] Initial heap: ${formatBytes(initialHeapUsed)}`);

    agent.on("health_update", (health: HealthStatus) => {
        healthCheckTotal++;
        if (health.overall === "all_ok" || health.overall === "partial") {
            healthCheckSuccess++;
        }
    });

    agent.on("nudge", (_nudge: NudgeMessage) => {
        nudgeTotal++;
    });

    agent.on("error", (msg: string) => {
        console.error(`[${new Date().toISOString()}] Agent error: ${msg}`);
    });

    agent.on("ready", () => {
        console.log(`[${new Date().toISOString()}] Agent ready`);
    });

    agent.start({
        healthIntervalMs: 60_000,
        nudgeIntervalMs: 30_000,
    });

    const memoryTimer = setInterval(() => {
        const sample = sampleMemory();
        memorySamples.push(sample);

        const ratio = sample.heapUsed / initialHeapUsed;
        if (ratio > 2) {
            heapWarningCount++;
            console.warn(
                `[${new Date().toISOString()}] WARNING: heapUsed ${formatBytes(sample.heapUsed)} ` +
                `exceeds 2x initial (${formatBytes(initialHeapUsed)}), ratio=${ratio.toFixed(2)}`,
            );
        } else {
            console.log(
                `[${new Date().toISOString()}] Memory sample: heap=${formatBytes(sample.heapUsed)} ` +
                `(ratio=${ratio.toFixed(2)})`,
            );
        }
    }, MEMORY_SAMPLE_INTERVAL_MS);

    await new Promise<void>((resolve) => {
        setTimeout(() => {
            resolve();
        }, durationSeconds * 1000);
    });

    clearInterval(memoryTimer);

    agent.stop();

    await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
            resolve();
        }, 5000);
        agent.once("shutdown_complete", () => {
            clearTimeout(timeout);
            resolve();
        });
    });

    const finalSample = sampleMemory();
    memorySamples.push(finalSample);

    const maxHeap = Math.max(...memorySamples.map((s) => s.heapUsed));
    const actualDurationMs = Date.now() - startTime;

    const summary: LoadTestSummary = {
        durationSeconds,
        actualDurationMs,
        initialHeap: initialHeapUsed,
        finalHeap: finalSample.heapUsed,
        maxHeap,
        heapWarnings: heapWarningCount,
        healthChecks: healthCheckTotal,
        healthSuccessRate: healthCheckTotal > 0 ? healthCheckSuccess / healthCheckTotal : 0,
        nudgeCount: nudgeTotal,
        memorySamples: memorySamples.length,
    };

    console.log("");
    console.log("=== Load Test Summary ===");
    console.log(`Duration (configured): ${summary.durationSeconds}s`);
    console.log(`Duration (actual):     ${(summary.actualDurationMs / 1000).toFixed(1)}s`);
    console.log(`Initial heap:          ${formatBytes(summary.initialHeap)}`);
    console.log(`Final heap:            ${formatBytes(summary.finalHeap)}`);
    console.log(`Max heap:              ${formatBytes(summary.maxHeap)}`);
    console.log(`Heap warnings (>2x):   ${summary.heapWarnings}`);
    console.log(`Health checks:         ${summary.healthChecks}`);
    console.log(`Success rate:          ${(summary.healthSuccessRate * 100).toFixed(1)}%`);
    console.log(`Nudge count:           ${summary.nudgeCount}`);
    console.log(`Memory samples:        ${summary.memorySamples}`);
    console.log("=========================");

    process.exit(0);
}

main().catch((err) => {
    console.error("Load test failed:", err);
    process.exit(1);
});
