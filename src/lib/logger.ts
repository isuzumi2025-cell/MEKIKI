/**
 * logger.ts
 *
 * 構造化ロギング (T-511) — pino ベースの JSON ログ出力
 * レベル制御 + コンテキスト付きロガー生成を提供。
 *
 * FlowForge SDK — Observability Layer
 */

import pino from "pino";

export type LogLevel = "trace" | "debug" | "info" | "warn" | "error" | "fatal";

const DEFAULT_LEVEL: LogLevel = (process.env.LOG_LEVEL as LogLevel) ?? "info";

const rootLogger = pino({
    level: DEFAULT_LEVEL,
    name: "flowforge-sdk",
    timestamp: pino.stdTimeFunctions.isoTime,
    formatters: {
        level(label: string) {
            return { level: label };
        },
    },
});

export function createLogger(module: string): pino.Logger {
    return rootLogger.child({ module });
}

export function setLogLevel(level: LogLevel): void {
    rootLogger.level = level;
}

export const logger = rootLogger;
