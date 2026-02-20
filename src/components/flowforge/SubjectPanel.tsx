/**
 * SubjectPanel.tsx
 *
 * サブジェクト管理パネル — SubjectRegistry のサブジェクトを一覧・登録・削除・持ち越し切替する UI。
 *
 * FlowForge SDK — GUI Layer
 */

import React, { useState, useCallback } from "react";
import type { Subject, SubjectType, SubjectCreateInput } from "../../lib/subject-registry";

export interface SubjectPanelProps {
    subjects: Subject[];
    onRegister?: (input: SubjectCreateInput) => void;
    onDelete?: (id: string) => void;
    onToggleCarryover?: (id: string, carryover: boolean) => void;
    disabled?: boolean;
}

const TYPE_LABELS: Record<SubjectType, string> = {
    character: "キャラクター",
    animal: "動物",
    object: "物体",
    vehicle: "乗り物",
    background: "背景",
};

const TYPE_OPTIONS: SubjectType[] = ["character", "animal", "object", "vehicle", "background"];

export const SubjectPanel: React.FC<SubjectPanelProps> = ({
    subjects,
    onRegister,
    onDelete,
    onToggleCarryover,
    disabled = false,
}) => {
    const [name, setName] = useState("");
    const [type, setType] = useState<SubjectType>("character");
    const [description, setDescription] = useState("");
    const [keyFeatures, setKeyFeatures] = useState("");

    const handleRegister = useCallback(() => {
        if (!name.trim() || !description.trim() || !keyFeatures.trim()) return;

        const input: SubjectCreateInput = {
            name: name.trim(),
            type,
            description: description.trim(),
            keyFeatures: keyFeatures.split(",").map(f => f.trim()).filter(Boolean),
            originCutId: "manual",
            carryover: true,
            tags: [type],
        };

        onRegister?.(input);
        setName("");
        setDescription("");
        setKeyFeatures("");
    }, [name, type, description, keyFeatures, onRegister]);

    return (
        <div className="subject-panel">
            <h2>サブジェクト管理</h2>

            <div className="subject-panel__form">
                <label>
                    名前
                    <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="サブジェクト名"
                        disabled={disabled}
                    />
                </label>

                <label>
                    タイプ
                    <select
                        value={type}
                        onChange={(e) => setType(e.target.value as SubjectType)}
                        disabled={disabled}
                    >
                        {TYPE_OPTIONS.map(t => (
                            <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                        ))}
                    </select>
                </label>

                <label>
                    外見記述
                    <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="外見の詳細"
                        disabled={disabled}
                        rows={2}
                    />
                </label>

                <label>
                    特徴 (カンマ区切り)
                    <input
                        type="text"
                        value={keyFeatures}
                        onChange={(e) => setKeyFeatures(e.target.value)}
                        placeholder="赤い帽子, 黒髪, 白いワンピース"
                        disabled={disabled}
                    />
                </label>

                <button
                    className="subject-panel__register-btn"
                    onClick={handleRegister}
                    disabled={disabled || !name.trim() || !description.trim() || !keyFeatures.trim()}
                >
                    登録
                </button>
            </div>

            <div className="subject-panel__list">
                <h3>登録済みサブジェクト ({subjects.length})</h3>
                {subjects.length === 0 && (
                    <p className="subject-panel__empty">
                        サブジェクトが登録されていません。
                    </p>
                )}
                {subjects.map(subject => (
                    <div key={subject.id} className="subject-panel__card">
                        <div className="subject-panel__card-header">
                            <span className="subject-panel__card-name">
                                {subject.name}
                            </span>
                            <span className="subject-panel__card-type">
                                {TYPE_LABELS[subject.type]}
                            </span>
                        </div>
                        <p className="subject-panel__card-desc">{subject.description}</p>
                        <div className="subject-panel__card-features">
                            {subject.keyFeatures.map((f, i) => (
                                <span key={i} className="subject-panel__tag">{f}</span>
                            ))}
                        </div>
                        <div className="subject-panel__card-actions">
                            <label className="subject-panel__carryover-toggle">
                                <input
                                    type="checkbox"
                                    checked={subject.carryover}
                                    onChange={(e) => onToggleCarryover?.(subject.id, e.target.checked)}
                                    disabled={disabled}
                                />
                                持ち越し
                            </label>
                            <button
                                className="subject-panel__delete-btn"
                                onClick={() => onDelete?.(subject.id)}
                                disabled={disabled}
                            >
                                削除
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
