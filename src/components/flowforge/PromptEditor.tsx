/**
 * PromptEditor.tsx
 *
 * セクション別プロンプトエディタ — 各セクションを個別に編集可能な UI
 * 自動強化ボタンで PromptRefiner を呼び出し。
 *
 * FlowForge SDK — GUI Layer (T-412)
 */

import React, { useCallback } from "react";
import type { PromptSection } from "../../lib/editable-prompt";

export interface PromptEditorProps {
    sections: PromptSection[];
    onEdit: (sectionId: string, content: string) => void;
    onGenerate?: () => void;
    onRefine?: (sectionId: string) => void;
    isGenerating?: boolean;
}

export const PromptEditor: React.FC<PromptEditorProps> = ({
    sections,
    onEdit,
    onGenerate,
    onRefine,
    isGenerating = false,
}) => {
    const handleChange = useCallback(
        (id: string, value: string) => {
            onEdit(id, value);
        },
        [onEdit],
    );

    const combinedPreview = sections
        .map(s => s.content.trim())
        .filter(Boolean)
        .join(". ") + ".";

    return (
        <div className="prompt-editor">
            <div className="prompt-editor__sections">
                {sections.length === 0 && (
                    <p className="prompt-editor__empty">
                        セクションがありません。リソースをアップロードするか、手動で追加してください。
                    </p>
                )}

                {sections.map(section => (
                    <div
                        key={section.id}
                        className={`prompt-editor__section ${section.modified ? "prompt-editor__section--modified" : ""}`}
                    >
                        <div className="prompt-editor__section-header">
                            <label className="prompt-editor__label">
                                {section.label}
                            </label>
                            <span className="prompt-editor__source">
                                {section.source}
                            </span>
                            {onRefine && (
                                <button
                                    className="prompt-editor__refine-btn"
                                    onClick={() => onRefine(section.id)}
                                    disabled={isGenerating}
                                >
                                    自動強化
                                </button>
                            )}
                        </div>
                        <textarea
                            className="prompt-editor__textarea"
                            value={section.content}
                            onChange={(e) => handleChange(section.id, e.target.value)}
                            disabled={isGenerating}
                            rows={3}
                        />
                    </div>
                ))}
            </div>

            {sections.length > 0 && (
                <div className="prompt-editor__preview">
                    <h3>結合プレビュー</h3>
                    <p className="prompt-editor__preview-text">{combinedPreview}</p>
                </div>
            )}

            {onGenerate && (
                <div className="prompt-editor__actions">
                    <button
                        className="prompt-editor__generate-btn"
                        onClick={onGenerate}
                        disabled={isGenerating || sections.length === 0}
                    >
                        {isGenerating ? "生成中..." : "動画を生成"}
                    </button>
                </div>
            )}
        </div>
    );
};
