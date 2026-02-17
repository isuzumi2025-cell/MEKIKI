/**
 * flowforge-agent-types.ts
 *
 * FlowForge Agent 共有型定義
 * AgentCommand / AgentEvent / AgentConfig / AgentContext を集約。
 *
 * FlowForge SDK — Agent Layer (Types)
 */

// ============================================================
// メッセージプロトコル
// ============================================================

/** メインスレッド → Worker */
export type AgentCommand =
    | { type: "check_health" }
    | { type: "update_context"; payload: Partial<AgentContext> }
    | { type: "get_status" }
    | { type: "configure"; payload: Partial<AgentConfig> }
    | { type: "shutdown" };

/** Worker → メインスレッド */
export type AgentEvent =
    | { type: "health_update"; payload: HealthStatus }
    | { type: "nudge"; payload: NudgeMessage }
    | { type: "context_sync"; payload: AgentContext }
    | { type: "status"; payload: AgentStatus }
    | { type: "error"; payload: string }
    | { type: "ready" }
    | { type: "shutdown_complete" };

// ============================================================
// 型定義
// ============================================================

export interface AgentConfig {
    /** ヘルスチェック間隔 (ms) */
    healthIntervalMs: number;
    /** ナッジ評価間隔 (ms) */
    nudgeIntervalMs: number;
    /** API キー */
    geminiApiKey?: string;
    grokApiKey?: string;
    devinApiKey?: string;
    devinBaseUrl?: string;
}

export type ApiServiceName = "gemini" | "grok" | "devin";

export interface ServiceHealth {
    status: "ok" | "degraded" | "down" | "unconfigured";
    latencyMs: number;
    lastCheck: string;
    error?: string;
}

export interface HealthStatus {
    gemini: ServiceHealth;
    grok: ServiceHealth;
    devin: ServiceHealth;
    overall: "all_ok" | "partial" | "all_down";
}

export interface AgentContext {
    lastPrompt?: string;
    lastRefinedPrompt?: string;
    activeFlowShotCount: number;
    devinSessionIds: string[];
    devinSessionStatus: Record<string, string>;
    toneMannerCached: boolean;
    lastActivity: string;
    promptEditIdleMs: number;
}

export interface NudgeMessage {
    id: string;
    priority: "low" | "medium" | "high";
    category: "prompt" | "health" | "devin" | "optimization";
    message: string;
    action?: string;
    timestamp: string;
}

export interface AgentStatus {
    uptime: number;
    healthChecks: number;
    nudgesSent: number;
    lastHealthCheck?: string;
    config: AgentConfig;
    context: AgentContext;
    health?: HealthStatus;
}

// ============================================================
// DI インターフェース (T-008)
// ============================================================

export interface IHealthChecker {
    check(): Promise<HealthStatus>;
    getCached(): HealthStatus | null;
    updateConfig(config: Partial<AgentConfig>): void;
    getCheckCount(): number;
}
