/**
 * FlowForgeStudio.tsx
 *
 * FlowForge メインパネル — 全コンポーネントを統合するトップレベル UI
 * PromptEditor / ResourceUploader / VisualEditPanel / GenerationProgress を配置。
 *
 * FlowForge SDK — GUI Layer (T-411)
 */

import React, { useState, useCallback } from "react";
import { PromptEditor } from "./PromptEditor";
import { ResourceUploader } from "./ResourceUploader";
import { VisualEditPanel } from "./VisualEditPanel";
import { CharacterPanel } from "./CharacterPanel";
import { ToneMannerPanel } from "./ToneMannerPanel";
import { TextProcessingPanel, type TextItem } from "./TextProcessingPanel";
import { MotionGraphicsPanel, type MotionGraphicsItem } from "./MotionGraphicsPanel";
import { GenerationProgress } from "./GenerationProgress";
import type { EditablePromptData, PromptSection } from "../../lib/editable-prompt";
import type { GenerationJobResult } from "../../lib/resource-video-generator";
import type { VisualEditInstruction } from "../../lib/visual-edit-engine";
import type { CharacterDetail } from "../../lib/flow-prompt-builder";

export type StudioTab = "prompt" | "resources" | "characters" | "tone" | "text" | "motion_graphics" | "visual_edit";

export interface FlowForgeStudioProps {
    onGenerate?: (prompt: EditablePromptData) => void;
    onVisualEdit?: (instruction: VisualEditInstruction) => void;
    generationResult?: GenerationJobResult;
    isGenerating?: boolean;
    progressMessage?: string;
}

export const FlowForgeStudio: React.FC<FlowForgeStudioProps> = ({
    onGenerate,
    onVisualEdit,
    generationResult,
    isGenerating = false,
    progressMessage,
}) => {
    const [activeTab, setActiveTab] = useState<StudioTab>("prompt");
    const [sections, setSections] = useState<PromptSection[]>([]);
    const [characters, setCharacters] = useState<CharacterDetail[]>([]);
    const [toneConfig, setToneConfig] = useState<{ urls: string[]; colorPalette: string[] }>({
        urls: [],
        colorPalette: [],
    });
    const [textItems, setTextItems] = useState<TextItem[]>([]);
    const [mgItems, setMgItems] = useState<MotionGraphicsItem[]>([]);

    const handleSectionEdit = useCallback((id: string, content: string) => {
        setSections(prev =>
            prev.map(s => (s.id === id ? { ...s, content, modified: true } : s)),
        );
    }, []);

    const handleGenerate = useCallback(() => {
        const data: EditablePromptData = {
            sections,
            combinedPrompt: sections.map(s => s.content.trim()).filter(Boolean).join(". ") + ".",
            updatedAt: new Date().toISOString(),
        };
        onGenerate?.(data);
    }, [sections, onGenerate]);

    const tabs: { key: StudioTab; label: string }[] = [
        { key: "prompt", label: "プロンプト" },
        { key: "resources", label: "リソース" },
        { key: "characters", label: "キャラクター" },
        { key: "tone", label: "トンマナ" },
        { key: "text", label: "テキスト処理" },
        { key: "motion_graphics", label: "MG" },
        { key: "visual_edit", label: "画像参照修正" },
    ];

    return (
        <div className="flowforge-studio">
            <header className="flowforge-studio__header">
                <h1>FlowForge Studio</h1>
            </header>

            <nav className="flowforge-studio__tabs">
                {tabs.map(tab => (
                    <button
                        key={tab.key}
                        className={`flowforge-studio__tab ${activeTab === tab.key ? "flowforge-studio__tab--active" : ""}`}
                        onClick={() => setActiveTab(tab.key)}
                    >
                        {tab.label}
                    </button>
                ))}
            </nav>

            <main className="flowforge-studio__content">
                {activeTab === "prompt" && (
                    <PromptEditor
                        sections={sections}
                        onEdit={handleSectionEdit}
                        onGenerate={handleGenerate}
                        isGenerating={isGenerating}
                    />
                )}

                {activeTab === "resources" && (
                    <ResourceUploader
                        onResourceAnalyzed={(analyzedSections) => {
                            setSections(prev => [...prev, ...analyzedSections]);
                        }}
                    />
                )}

                {activeTab === "characters" && (
                    <CharacterPanel
                        characters={characters}
                        onChange={setCharacters}
                    />
                )}

                {activeTab === "tone" && (
                    <ToneMannerPanel
                        urls={toneConfig.urls}
                        colorPalette={toneConfig.colorPalette}
                        onUrlsChange={(urls) => setToneConfig(prev => ({ ...prev, urls }))}
                        onPaletteChange={(colorPalette) => setToneConfig(prev => ({ ...prev, colorPalette }))}
                    />
                )}

                {activeTab === "text" && (
                    <TextProcessingPanel
                        items={textItems}
                        onChange={setTextItems}
                    />
                )}

                {activeTab === "motion_graphics" && (
                    <MotionGraphicsPanel
                        items={mgItems}
                        onChange={setMgItems}
                    />
                )}

                {activeTab === "visual_edit" && (
                    <VisualEditPanel
                        previousResult={generationResult}
                        onEdit={onVisualEdit}
                    />
                )}
            </main>

            {(isGenerating || generationResult) && (
                <footer className="flowforge-studio__progress">
                    <GenerationProgress
                        result={generationResult}
                        isGenerating={isGenerating}
                        message={progressMessage}
                    />
                </footer>
            )}
        </div>
    );
};
