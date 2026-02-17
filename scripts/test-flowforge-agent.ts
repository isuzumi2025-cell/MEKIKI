/**
 * test-flowforge-agent.ts
 *
 * FlowForge Agent Phase 2 の基本検証スクリプト。
 * 型チェック・インスタンス生成・回路ブレーカー動作を確認。
 */

import { CircuitBreaker, CircuitBreakerOpenError } from "../src/lib/resilience.js";
import { defaultNudgeRules } from "../src/lib/nudge-rules.js";
import type {
    AgentCommand,
    AgentConfig,
    AgentContext,
    HealthStatus,
    IHealthChecker,
} from "../src/lib/flowforge-agent-types.js";

function assert(condition: boolean, msg: string): void {
    if (!condition) {
        throw new Error(`FAIL: ${msg}`);
    }
    console.log(`  PASS: ${msg}`);
}

async function testCircuitBreaker(): Promise<void> {
    console.log("\n=== CircuitBreaker ===");

    const cb = new CircuitBreaker({ failureThreshold: 3, resetTimeoutMs: 500 });

    assert(cb.getState() === "closed", "initial state is closed");

    const ok = await cb.execute(async () => 42);
    assert(ok === 42, "execute returns value on success");

    for (let i = 0; i < 3; i++) {
        try {
            await cb.execute(async () => {
                throw new Error("fail");
            });
        } catch {
            // expected
        }
    }
    assert(cb.getState() === "open", "state is open after threshold failures");

    try {
        await cb.execute(async () => 1);
        assert(false, "should not reach here");
    } catch (e) {
        assert(e instanceof CircuitBreakerOpenError, "throws CircuitBreakerOpenError when open");
    }

    await new Promise((r) => setTimeout(r, 600));
    assert(cb.getState() === "half_open", "state transitions to half_open after timeout");

    const recovered = await cb.execute(async () => 99);
    assert(recovered === 99, "successful call in half_open closes the circuit");
    assert(cb.getState() === "closed", "state is closed after recovery");
}

function testNudgeRules(): void {
    console.log("\n=== NudgeRules ===");

    assert(defaultNudgeRules.length >= 5, `has ${defaultNudgeRules.length} default rules`);

    for (const rule of defaultNudgeRules) {
        assert(typeof rule.id === "string" && rule.id.length > 0, `rule ${rule.id} has id`);
        assert(typeof rule.condition === "function", `rule ${rule.id} has condition`);
        assert(typeof rule.message === "function", `rule ${rule.id} has message`);
        assert(rule.cooldownMs > 0, `rule ${rule.id} has positive cooldown`);
    }
}

function testTypes(): void {
    console.log("\n=== Types ===");

    const cmd: AgentCommand = { type: "check_health" };
    assert(cmd.type === "check_health", "AgentCommand type works");

    const config: AgentConfig = {
        healthIntervalMs: 60000,
        nudgeIntervalMs: 30000,
        geminiApiKey: "test",
    };
    assert(config.healthIntervalMs === 60000, "AgentConfig works");

    const ctx: AgentContext = {
        activeFlowShotCount: 0,
        devinSessionIds: [],
        devinSessionStatus: {},
        toneMannerCached: false,
        lastActivity: new Date().toISOString(),
        promptEditIdleMs: 0,
    };
    assert(Array.isArray(ctx.devinSessionIds), "AgentContext works");

    const checker: IHealthChecker = {
        check: async () => ({
            gemini: { status: "ok", latencyMs: 100, lastCheck: "" },
            grok: { status: "unconfigured", latencyMs: 0, lastCheck: "" },
            devin: { status: "unconfigured", latencyMs: 0, lastCheck: "" },
            overall: "all_ok",
        }),
        getCached: () => null,
        updateConfig: () => {},
        getCheckCount: () => 0,
    };
    assert(typeof checker.check === "function", "IHealthChecker interface works");
}

async function main(): Promise<void> {
    console.log("FlowForge Agent Phase 2 — Test Suite");

    testTypes();
    testNudgeRules();
    await testCircuitBreaker();

    console.log("\n All tests passed!");
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
