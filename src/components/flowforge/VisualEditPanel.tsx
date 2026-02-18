/**
 * VisualEditPanel.tsx
 *
 * 参照画像修正パネル — 参照画像をアップロードし、修正対象と修正タイプを選択して
 * VisualEditInstruction を発行する UI。
 *
 * FlowForge SDK — GUI Layer (T-414)
 */

import React, { useState, useCallback, useRef } from "react";
import type { VisualEditInstruction } from "../../lib/visual-edit-engine";
import type { GenerationJobResult } from "../../lib/resource-video-generator";

export interface VisualEditPanelProps {
    previousResult?: GenerationJobResult;
    onEdit?: (instruction: VisualEditInstruction) => void;
    isProcessing?: boolean;
}

type EditType = VisualEditInstruction["editType"];

const EDIT_TYPE_LABELS: Record<EditType, string> = {
    replace_shape: "形状を差替",
    replace_style: "スタイルを差替",
    replace_color: "色を差替",
    add_from_image: "オブジェクト追加",
    match_pose: "ポーズ合わせ",
};

export const VisualEditPanel: React.FC<VisualEditPanelProps> = ({
    previousResult,
    onEdit,
    isProcessing = false,
}) => {
    const [referenceImage, setReferenceImage] = useState<string | null>(null);
    const [referenceMimeType, setReferenceMimeType] = useState<VisualEditInstruction["referenceImageMimeType"]>("image/png");
    const [targetElement, setTargetElement] = useState("");
    const [editType, setEditType] = useState<EditType>("replace_shape");
    const [additionalInstruction, setAdditionalInstruction] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            const base64 = (reader.result as string).split(",")[1];
            if (base64) {
                setReferenceImage(base64);
                setReferenceMimeType(file.type as VisualEditInstruction["referenceImageMimeType"]);
            }
        };
        reader.readAsDataURL(file);
    }, []);

    const handleSubmit = useCallback(() => {
        if (!referenceImage || !targetElement.trim()) return;

        const instruction: VisualEditInstruction = {
            referenceImageBytes: referenceImage,
            referenceImageMimeType: referenceMimeType,
            targetElement: targetElement.trim(),
            editType,
            additionalInstruction: additionalInstruction.trim() || undefined,
        };

        onEdit?.(instruction);
    }, [referenceImage, referenceMimeType, targetElement, editType, additionalInstruction, onEdit]);

    if (!previousResult) {
        return (
            <div className="visual-edit-panel">
                <p className="visual-edit-panel__empty">
                    画像参照修正を使用するには、まず動画を生成してください。
                </p>
            </div>
        );
    }

    return (
        <div className="visual-edit-panel">
            <h2>画像参照修正</h2>

            <div className="visual-edit-panel__reference">
                <label>参照画像</label>
                <div
                    className="visual-edit-panel__upload"
                    onClick={() => fileInputRef.current?.click()}
                >
                    {referenceImage ? (
                        <img
                            src={`data:${referenceMimeType};base64,${referenceImage}`}
                            alt="参照画像"
                            className="visual-edit-panel__preview"
                        />
                    ) : (
                        <p>クリックして参照画像を選択</p>
                    )}
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        onChange={handleFileChange}
                        style={{ display: "none" }}
                    />
                </div>
            </div>

            <div className="visual-edit-panel__target">
                <label>修正対象</label>
                <input
                    type="text"
                    value={targetElement}
                    onChange={(e) => setTargetElement(e.target.value)}
                    placeholder="例: リーダーの棒、背景の建物"
                    disabled={isProcessing}
                />
            </div>

            <div className="visual-edit-panel__edit-type">
                <label>修正タイプ</label>
                <div className="visual-edit-panel__type-options">
                    {(Object.entries(EDIT_TYPE_LABELS) as [EditType, string][]).map(([type, label]) => (
                        <button
                            key={type}
                            className={`visual-edit-panel__type-btn ${editType === type ? "visual-edit-panel__type-btn--active" : ""}`}
                            onClick={() => setEditType(type)}
                            disabled={isProcessing}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="visual-edit-panel__additional">
                <label>追加指示 (任意)</label>
                <textarea
                    value={additionalInstruction}
                    onChange={(e) => setAdditionalInstruction(e.target.value)}
                    placeholder="追加の修正指示があれば入力"
                    disabled={isProcessing}
                    rows={2}
                />
            </div>

            <button
                className="visual-edit-panel__submit"
                onClick={handleSubmit}
                disabled={isProcessing || !referenceImage || !targetElement.trim()}
            >
                {isProcessing ? "処理中..." : "修正を実行"}
            </button>
        </div>
    );
};
