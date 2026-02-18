/**
 * FlowForgeStudioDemo.tsx
 *
 * FlowForgeStudio の Remotion Studio プレビュー用ラッパー。
 * サンプルデータで全タブ (プロンプト/リソース/キャラクター/トンマナ/画像参照修正) を操作可能。
 */

import React, { useState, useCallback } from "react";
import { AbsoluteFill } from "remotion";
import { FlowForgeStudio } from "./components/flowforge/FlowForgeStudio";
import type { EditablePromptData } from "./lib/editable-prompt";

export const FlowForgeStudioDemo: React.FC = () => {
    const [isGenerating, setIsGenerating] = useState(false);
    const [progressMessage, setProgressMessage] = useState<string>();

    const handleGenerate = useCallback((prompt: EditablePromptData) => {
        setIsGenerating(true);
        setProgressMessage("プロンプト構築中...");

        // 生成シミュレーション
        setTimeout(() => {
            setProgressMessage("Nano Banana で画像生成中...");
            setTimeout(() => {
                setProgressMessage("Veo 3.1 で動画変換中...");
                setTimeout(() => {
                    setIsGenerating(false);
                    setProgressMessage(undefined);
                    console.log("[FlowForgeStudioDemo] 生成完了 (simulation)", prompt);
                }, 2000);
            }, 2000);
        }, 1000);
    }, []);

    return (
        <AbsoluteFill
            style={{
                backgroundColor: "#1a1a2e",
                fontFamily: "'Inter', 'Segoe UI', sans-serif",
                padding: 16,
                overflow: "auto",
            }}
        >
            <style>{`
                .flowforge-studio {
                    max-width: 1400px;
                    margin: 0 auto;
                    color: #e0e0e0;
                }
                .flowforge-studio__header h1 {
                    font-size: 24px;
                    font-weight: 700;
                    margin: 0 0 16px 0;
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                .flowforge-studio__tabs {
                    display: flex;
                    gap: 4px;
                    margin-bottom: 16px;
                    border-bottom: 1px solid #2a2a4a;
                    padding-bottom: 4px;
                }
                .flowforge-studio__tab {
                    padding: 8px 16px;
                    border: none;
                    background: transparent;
                    color: #888;
                    cursor: pointer;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px 6px 0 0;
                    transition: all 0.15s;
                }
                .flowforge-studio__tab:hover {
                    color: #c0c0e0;
                    background: #1e1e3a;
                }
                .flowforge-studio__tab--active {
                    color: #e0e0ff;
                    background: #1e1e3a;
                    border-bottom: 2px solid #667eea;
                }
                .flowforge-studio__content {
                    background: #16213e;
                    border-radius: 8px;
                    padding: 16px;
                    min-height: 400px;
                }
                .flowforge-studio__progress {
                    margin-top: 12px;
                }
                input, textarea, select, button {
                    font-family: inherit;
                }
                input, textarea {
                    background: #1a1a30;
                    border: 1px solid #2a2a4a;
                    color: #e0e0e0;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 13px;
                    width: 100%;
                    box-sizing: border-box;
                }
                button {
                    cursor: pointer;
                }
            `}</style>
            <FlowForgeStudio
                onGenerate={handleGenerate}
                isGenerating={isGenerating}
                progressMessage={progressMessage}
            />
        </AbsoluteFill>
    );
};
