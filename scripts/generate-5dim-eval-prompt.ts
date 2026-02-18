/**
 * generate-5dim-eval-prompt.ts
 *
 * T-521: 5次元評価プロンプトジェネレーター
 *
 * src/lib/*.ts の全モジュールを読み取り、
 * 各モジュールの行数・テスト数・公開API数を集計して、
 * 5次元（優越性・革新性・合理性・一貫性・処理精度）の
 * 評価プロンプトを output/5dim-eval-prompt.txt に出力する。
 */

import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, basename } from "node:path";

// ─── Types ──────────────────────────────────────────

interface ModuleStats {
    filename: string;
    lines: number;
    exportedFunctions: number;
    exportedClasses: number;
    exportedInterfaces: number;
    exportedTypes: number;
    totalPublicAPIs: number;
    testCount: number;
}

interface ProjectSummary {
    totalModules: number;
    totalLines: number;
    totalPublicAPIs: number;
    totalTests: number;
    modules: ModuleStats[];
}

// ─── Analysis ───────────────────────────────────────

function countExports(content: string): Pick<ModuleStats, "exportedFunctions" | "exportedClasses" | "exportedInterfaces" | "exportedTypes"> {
    const exportedFunctions = (content.match(/^export\s+(async\s+)?function\s+/gm) ?? []).length;
    const exportedClasses = (content.match(/^export\s+class\s+/gm) ?? []).length;
    const exportedInterfaces = (content.match(/^export\s+interface\s+/gm) ?? []).length;
    const exportedTypes = (content.match(/^export\s+type\s+/gm) ?? []).length;
    return { exportedFunctions, exportedClasses, exportedInterfaces, exportedTypes };
}

function countTestsForModule(testDir: string, moduleName: string): number {
    const testFile = join(testDir, `${moduleName}.test.ts`);
    if (!existsSync(testFile)) return 0;

    const content = readFileSync(testFile, "utf-8");
    const itMatches = content.match(/\b(it|test)\s*\(/g) ?? [];
    return itMatches.length;
}

function analyzeModule(filePath: string, testDir: string): ModuleStats {
    const content = readFileSync(filePath, "utf-8");
    const filename = basename(filePath);
    const moduleName = filename.replace(/\.ts$/, "");
    const lines = content.split("\n").length;
    const exports = countExports(content);
    const testCount = countTestsForModule(testDir, moduleName);

    return {
        filename,
        lines,
        ...exports,
        totalPublicAPIs: exports.exportedFunctions + exports.exportedClasses + exports.exportedInterfaces + exports.exportedTypes,
        testCount,
    };
}

function analyzeProject(libDir: string, testDir: string): ProjectSummary {
    const tsFiles = readdirSync(libDir)
        .filter((f) => f.endsWith(".ts") && !f.endsWith(".test.ts") && !f.endsWith(".d.ts"))
        .sort();

    const modules = tsFiles.map((f) => analyzeModule(join(libDir, f), testDir));

    return {
        totalModules: modules.length,
        totalLines: modules.reduce((sum, m) => sum + m.lines, 0),
        totalPublicAPIs: modules.reduce((sum, m) => sum + m.totalPublicAPIs, 0),
        totalTests: modules.reduce((sum, m) => sum + m.testCount, 0),
        modules,
    };
}

// ─── Prompt Generation ──────────────────────────────

function generatePrompt(summary: ProjectSummary): string {
    const now = new Date().toISOString();

    const moduleTable = summary.modules
        .map(
            (m) =>
                `| ${m.filename.padEnd(40)} | ${String(m.lines).padStart(5)} | ${String(m.totalPublicAPIs).padStart(4)} | ${String(m.testCount).padStart(5)} |`,
        )
        .join("\n");

    return `# FlowForge SDK — 5-Dimensional Evaluation Prompt
Generated: ${now}

## Project Overview

| Metric          | Value |
|:----------------|------:|
| Total modules   | ${summary.totalModules} |
| Total lines     | ${summary.totalLines} |
| Total public APIs | ${summary.totalPublicAPIs} |
| Total tests     | ${summary.totalTests} |
| Test coverage ratio (tests/APIs) | ${summary.totalPublicAPIs > 0 ? (summary.totalTests / summary.totalPublicAPIs).toFixed(2) : "N/A"} |

## Module Breakdown

| Module${" ".repeat(34)} | Lines | APIs | Tests |
|:-${"-".repeat(39)}|------:|-----:|------:|
${moduleTable}

---

## 5-Dimensional Evaluation Criteria

Evaluate the FlowForge SDK codebase against the following five dimensions.
For each dimension, assign a score from 1 (lowest) to 5 (highest) and provide justification.

### 1. Superiority (優越性)

Evaluate whether the SDK provides capabilities that surpass existing alternatives.

- Does the agent architecture (Worker Thread + MessagePort) offer advantages over simpler approaches?
- Are the health monitoring, circuit breaker, and auto-restart patterns best-in-class?
- How does the nudge system compare to conventional notification approaches?
- Module count: ${summary.totalModules}, Total public APIs: ${summary.totalPublicAPIs}

**Evaluation points:**
- Architecture sophistication vs. complexity trade-off
- Breadth and depth of functionality
- Unique value propositions

### 2. Innovation (革新性)

Evaluate the novelty and originality of the design and implementation.

- Is the declarative nudge-rule engine a novel approach for agent-based systems?
- How innovative is the strategy pattern for generation (nano-banana, veo)?
- Does the visual-edit engine introduce new paradigms?
- Are Zod-based runtime validations applied innovatively?

**Evaluation points:**
- Novel design patterns and abstractions
- Creative use of TypeScript type system
- Originality in problem-solving approach

### 3. Rationality (合理性)

Evaluate the logical soundness and justifiability of design decisions.

- Are the module boundaries well-justified? (${summary.totalModules} modules, ${summary.totalLines} total lines)
- Is the separation between agent proxy and worker thread rational?
- Are the resilience patterns (CircuitBreaker, LRUCache, SlidingWindow) appropriate for the use case?
- Is the DI interface (IHealthChecker) a rational abstraction?

**Evaluation points:**
- Separation of concerns
- Appropriate use of design patterns
- Configuration vs. convention balance

### 4. Coherence (一貫性)

Evaluate the consistency across the codebase.

- Are naming conventions consistent across all ${summary.totalModules} modules?
- Is the error handling approach uniform (typed errors, circuit breaker integration)?
- Are export patterns consistent (types vs. runtime exports)?
- Is the event system consistently structured across agent components?
- Test coverage distribution: ${summary.modules.filter((m) => m.testCount > 0).length}/${summary.totalModules} modules have tests

**Evaluation points:**
- Naming and coding style consistency
- Uniform error handling strategy
- Consistent module structure and export patterns

### 5. Processing Accuracy (処理精度)

Evaluate the correctness and reliability of data processing.

- Are runtime validations (Zod schemas) comprehensive?
- Does the circuit breaker correctly handle state transitions (closed -> open -> half_open)?
- Are race conditions properly handled (e.g., health check mutex)?
- Is memory management sound for long-running agent processes?
- Test count: ${summary.totalTests} tests covering ${summary.modules.filter((m) => m.testCount > 0).length} modules

**Evaluation points:**
- Input validation completeness
- State machine correctness
- Concurrency safety
- Resource cleanup on shutdown

---

## Scoring Template

| Dimension             | Score (1-5) | Justification |
|:----------------------|:-----------:|:--------------|
| 1. Superiority        |             |               |
| 2. Innovation         |             |               |
| 3. Rationality        |             |               |
| 4. Coherence          |             |               |
| 5. Processing Accuracy|             |               |
| **Overall**           |             |               |

## Instructions

1. Read the module breakdown above to understand the scope.
2. For each dimension, review the relevant modules and their public APIs.
3. Assign a score and write 2-3 sentences of justification.
4. Calculate the overall score as the average of all five dimensions.
5. Identify the top 3 strengths and top 3 areas for improvement.
`;
}

// ─── Main ───────────────────────────────────────────

function main(): void {
    const projectRoot = join(import.meta.dirname ?? process.cwd(), "..");
    const libDir = join(projectRoot, "src", "lib");
    const testDir = join(projectRoot, "src", "lib", "__tests__");
    const outputDir = join(projectRoot, "output");
    const outputFile = join(outputDir, "5dim-eval-prompt.txt");

    if (!existsSync(libDir)) {
        console.error(`Error: ${libDir} does not exist`);
        process.exit(1);
    }

    console.log("=== 5-Dimensional Evaluation Prompt Generator ===");
    console.log(`Scanning: ${libDir}`);

    const summary = analyzeProject(libDir, testDir);

    console.log(`Found ${summary.totalModules} modules, ${summary.totalLines} lines, ${summary.totalPublicAPIs} public APIs, ${summary.totalTests} tests`);

    const prompt = generatePrompt(summary);

    if (!existsSync(outputDir)) {
        mkdirSync(outputDir, { recursive: true });
    }

    writeFileSync(outputFile, prompt, "utf-8");
    console.log(`Output written to: ${outputFile}`);
    console.log("Done.");
}

main();
