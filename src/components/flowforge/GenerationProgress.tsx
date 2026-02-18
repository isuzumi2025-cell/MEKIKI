/**
 * GenerationProgress.tsx
 *
 * 進捗表示コンポーネント — 動画生成の進行状況を表示
 * ステージ（画像生成→動画生成→レンダリング）の進捗を可視化。
 *
 * FlowForge SDK — GUI Layer (T-417)
 */

import React from "react";
import type { GenerationJobResult } from "../../lib/resource-video-generator";

export interface GenerationProgressProps {
    result?: GenerationJobResult;
    isGenerating?: boolean;
    message?: string;
    stages?: ProgressStage[];
}

export interface ProgressStage {
    id: string;
    label: string;
    status: "pending" | "in_progress" | "completed" | "error";
    detail?: string;
}

const DEFAULT_STAGES: ProgressStage[] = [
    { id: "analyze", label: "プロンプト解析", status: "pending" },
    { id: "image", label: "コンテ画像生成", status: "pending" },
    { id: "video", label: "動画生成 (Veo)", status: "pending" },
    { id: "render", label: "Remotion レンダリング", status: "pending" },
];

function getStatusIcon(status: ProgressStage["status"]): string {
    switch (status) {
        case "pending": return "-";
        case "in_progress": return "...";
        case "completed": return "OK";
        case "error": return "ERR";
    }
}

export const GenerationProgress: React.FC<GenerationProgressProps> = ({
    result,
    isGenerating = false,
    message,
    stages = DEFAULT_STAGES,
}) => {
    if (!isGenerating && !result) return null;

    return (
        <div className="generation-progress">
            <h3>生成進捗</h3>

            {message && (
                <p className="generation-progress__message">{message}</p>
            )}

            <div className="generation-progress__stages">
                {stages.map(stage => (
                    <div
                        key={stage.id}
                        className={`generation-progress__stage generation-progress__stage--${stage.status}`}
                    >
                        <span className="generation-progress__stage-icon">
                            [{getStatusIcon(stage.status)}]
                        </span>
                        <span className="generation-progress__stage-label">
                            {stage.label}
                        </span>
                        {stage.detail && (
                            <span className="generation-progress__stage-detail">
                                {stage.detail}
                            </span>
                        )}
                    </div>
                ))}
            </div>

            {result && (
                <div className="generation-progress__result">
                    {result.status === "completed" ? (
                        <p className="generation-progress__success">
                            生成完了
                        </p>
                    ) : result.status === "failed" ? (
                        <p className="generation-progress__error">
                            生成失敗
                        </p>
                    ) : (
                        <p className="generation-progress__status">
                            ステータス: {result.status}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};
