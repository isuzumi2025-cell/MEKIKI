/**
 * e2e-verify.ts — 全モジュール統合検証スクリプト
 */

import { SubjectRegistry } from "../src/lib/subject-registry.js";
import { CircuitBreaker, LRUCache } from "../src/lib/resilience.js";
import { LatencyHistogram } from "../src/lib/metrics.js";
import { EmotionAxisSchema, calculateConfidenceScore } from "../src/lib/prompt-understanding-schemas.js";
import { StreamingAxisPipeline } from "../src/lib/streaming-axis-output.js";

(async () => {
    let passed = 0;
    let failed = 0;
    const results: string[] = [];

    function check(name: string, fn: () => void): void {
        try { fn(); results.push("✅ " + name); passed++; }
        catch (e: any) { results.push("❌ " + name + ": " + e.message); failed++; }
    }

    // === 1. SubjectRegistry ===
    console.log("=== 1. SubjectRegistry ===");
    const registry = new SubjectRegistry();

    const girl = registry.register({
        name: "赤い帽子の少女", type: "character",
        description: "赤い帽子を被った少女。黒髪ロング。",
        keyFeatures: ["赤い帽子", "黒髪ロング", "白ワンピース"],
        originCutId: "cut-001", carryover: true, tags: ["主人公"],
    });

    const cat = registry.register({
        name: "白い猫", type: "animal",
        description: "ふわふわの白猫。青い目。",
        keyFeatures: ["白い毛", "青い目"],
        originCutId: "cut-001", carryover: true, tags: ["ペット"],
    });

    const car = registry.register({
        name: "赤いスポーツカー", type: "vehicle",
        description: "低いフォルムの赤いスポーツカー。",
        keyFeatures: ["赤い塗装", "スポイラー"],
        originCutId: "cut-002", carryover: false, tags: ["乗り物"],
    });

    check("Register 3 subjects", () => { if (registry.size !== 3) throw new Error("size=" + registry.size); });
    check("Recall by ID", () => { if (registry.recall(girl.id)?.name !== "赤い帽子の少女") throw new Error("fail"); });
    check("Recall by name (partial)", () => { if (!registry.recallByName("帽子")) throw new Error("not found"); });
    check("Search by type=animal", () => { if (registry.search({ type: "animal" }).length !== 1) throw new Error("fail"); });
    check("Search by tag", () => { if (registry.search({ tag: "主人公" }).length !== 1) throw new Error("fail"); });
    check("Carryover subjects (2)", () => { if (registry.getCarryoverSubjects().length !== 2) throw new Error("fail"); });

    registry.setCarryover(car.id, true);
    check("Toggle carryover ON", () => { if (registry.getCarryoverSubjects().length !== 3) throw new Error("fail"); });
    registry.setCarryover(car.id, false);
    check("Toggle carryover OFF", () => { if (registry.getCarryoverSubjects().length !== 2) throw new Error("fail"); });

    const prompt = registry.buildCarryoverPrompt();
    check("Prompt has content", () => { if (!prompt.includes("Persistent Subjects")) throw new Error("fail"); });
    check("Prompt has 👤", () => { if (!prompt.includes("👤")) throw new Error("fail"); });
    check("Prompt has 🐾", () => { if (!prompt.includes("🐾")) throw new Error("fail"); });

    registry.markUsedInCut(girl.id, "cut-003");
    check("Track usage", () => { if (registry.recall(girl.id)?.lastUsedInCutId !== "cut-003") throw new Error("fail"); });

    const json = registry.toJSON();
    const restored = SubjectRegistry.fromJSON(json);
    check("Serialize + restore", () => { if (restored.size !== 3) throw new Error("size=" + restored.size); });

    registry.delete(car.id);
    check("Delete", () => { if (registry.size !== 2) throw new Error("size=" + registry.size); });

    // === 2. Resilience ===
    console.log("\n=== 2. Resilience ===");
    const breaker = new CircuitBreaker();
    const r1 = await breaker.execute(async () => 42);
    check("CircuitBreaker", () => { if (r1 !== 42) throw new Error("fail"); });

    const lru = new LRUCache<string, number>(2);
    lru.set("a", 1); lru.set("b", 2); lru.set("c", 3);
    check("LRU eviction", () => { if (lru.get("a") !== undefined) throw new Error("a not evicted"); });

    // === 3. Metrics ===
    console.log("\n=== 3. Metrics ===");
    const hist = new LatencyHistogram();
    [10, 20, 30, 40, 50, 60, 70, 80, 90, 100].forEach((v) => hist.record(v));
    check("Histogram mean ~55", () => { if (Math.abs(hist.mean - 55) > 1) throw new Error("mean=" + hist.mean); });

    // === 4. Schema ===
    console.log("\n=== 4. Schema ===");
    check("EmotionAxis valid", () => {
        const r = EmotionAxisSchema.safeParse({
            emotionCurve: [{ position: 0, intensity: 0.5, emotion: "joy" }],
            palette: { primary: "joy", colorMapping: { joy: "#FFD700" }, overallMood: "uplifting" },
            visualImpact: 0.7, reasoning: "test",
        });
        if (!r.success) throw new Error(JSON.stringify(r.error));
    });

    check("Confidence score", () => {
        const c = calculateConfidenceScore({ coverage: 85, depth: 80, coherence: 90, specificity: 75 });
        if (c.total < 70 || c.total > 95) throw new Error("total=" + c.total);
    });

    // === 5. Streaming Pipeline ===
    console.log("\n=== 5. Streaming Pipeline ===");
    const mockGrok = async () => ({
        A1_trendWords: [{ originalTerm: "sunset", interpretation: "golden", confidence: 0.9, relatedTerms: [], source: "general" as const }],
        A2_culturalContext: { references: [], implicitMeaning: "warm" },
        A3_visualTrends: { matchedTrends: [], suggestedStyle: "warm" },
    });
    const pipeline = new StreamingAxisPipeline({ grok: mockGrok }, ["A1", "A2", "A3"]);
    let eventCount = 0;
    let finalResult: any = null;
    for await (const ev of pipeline.analyze({ prompt: "sunset", language: "ja" })) {
        eventCount++;
        if (ev.type === "final") finalResult = ev.finalResult;
    }
    check("Stream events", () => { if (eventCount < 2) throw new Error("events=" + eventCount); });
    check("Final has grokAxes", () => { if (!finalResult?.grokAxes) throw new Error("no grokAxes"); });
    check("Confidence calculated", () => { if (!finalResult?.confidence?.total) throw new Error("no confidence"); });

    // === Summary ===
    console.log("\n" + "=".repeat(50));
    results.forEach((r) => console.log(r));
    console.log("=".repeat(50));
    console.log(`\nTotal: ${passed}/${passed + failed} passed`);
    if (failed > 0) process.exit(1);
    console.log("\n🎉 All E2E integration checks passed!");
})();
