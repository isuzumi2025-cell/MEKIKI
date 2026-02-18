/**
 * load-test-agent.ts
 *
 * T-503: FlowForge Agent 繝ｭ繝ｼ繝峨ユ繧ｹ繝医せ繧ｯ繝ｪ繝励ヨ
 *
 * 謖・ｮ壹＠縺・duration・医ョ繝輔か繝ｫ繝・3600s・峨・髢・FlowForge Agent 繧定ｵｷ蜍輔＠縲・ * 60 遘偵＃縺ｨ縺ｫ process.memoryUsage() 繧定ｨ倬鹸縲・ * heapUsed 縺悟・譛溷､縺ｮ 2 蛟阪ｒ雜・∴縺溷ｴ蜷医↓隴ｦ蜻翫ｒ蜃ｺ蜉帙・ * 邨ゆｺ・凾縺ｫ繧ｵ繝槭Μ繝ｼ・亥・譛・譛邨・譛螟ｧ繝偵・繝励∵・蜉溽紫縲√リ繝・ず謨ｰ・峨ｒ陦ｨ遉ｺ縲・ */

import { FlowForgeAgent } from "../src/lib/flowforge-agent.js";
import type { HealthStatus, NudgeMessage } from "../src/lib/flowforge-agent-types.js";

// 笏笏笏 CLI Argument Parsing 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏

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

// 笏笏笏 Types 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏

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

// 笏笏笏 State 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏

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

// 笏笏笏 Main 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏

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
