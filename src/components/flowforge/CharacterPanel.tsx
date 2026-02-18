/**
 * CharacterPanel.tsx
 *
 * キャラクター詳細エディタ — 登場人物の名前・役割・外見・衣装等を編集
 * FlowShot.characters 配列を直接操作する UI。
 *
 * FlowForge SDK — GUI Layer (T-415)
 */

import React, { useCallback } from "react";
import type { CharacterDetail } from "../../lib/flow-prompt-builder";

export interface CharacterPanelProps {
    characters: CharacterDetail[];
    onChange: (characters: CharacterDetail[]) => void;
    disabled?: boolean;
}

const EMPTY_CHARACTER: CharacterDetail = {
    name: "",
    role: "",
    appearance: "",
    clothing: "",
    action: "",
    position: "",
};

export const CharacterPanel: React.FC<CharacterPanelProps> = ({
    characters,
    onChange,
    disabled = false,
}) => {
    const addCharacter = useCallback(() => {
        onChange([...characters, { ...EMPTY_CHARACTER }]);
    }, [characters, onChange]);

    const removeCharacter = useCallback(
        (index: number) => {
            onChange(characters.filter((_, i) => i !== index));
        },
        [characters, onChange],
    );

    const updateField = useCallback(
        (index: number, field: keyof CharacterDetail, value: string) => {
            onChange(
                characters.map((c, i) =>
                    i === index ? { ...c, [field]: value } : c,
                ),
            );
        },
        [characters, onChange],
    );

    return (
        <div className="character-panel">
            <div className="character-panel__header">
                <h2>キャラクター設定</h2>
                <button
                    className="character-panel__add-btn"
                    onClick={addCharacter}
                    disabled={disabled}
                >
                    キャラクター追加
                </button>
            </div>

            {characters.length === 0 && (
                <p className="character-panel__empty">
                    キャラクターが登録されていません。
                </p>
            )}

            {characters.map((character, index) => (
                <div key={index} className="character-panel__card">
                    <div className="character-panel__card-header">
                        <span>キャラクター {index + 1}</span>
                        <button
                            className="character-panel__remove-btn"
                            onClick={() => removeCharacter(index)}
                            disabled={disabled}
                        >
                            削除
                        </button>
                    </div>

                    <div className="character-panel__fields">
                        <label>
                            名前
                            <input
                                type="text"
                                value={character.name}
                                onChange={(e) => updateField(index, "name", e.target.value)}
                                placeholder="キャラクター名"
                                disabled={disabled}
                            />
                        </label>

                        <label>
                            役割
                            <input
                                type="text"
                                value={character.role ?? ""}
                                onChange={(e) => updateField(index, "role", e.target.value)}
                                placeholder="例: 主人公、敵役"
                                disabled={disabled}
                            />
                        </label>

                        <label>
                            外見
                            <textarea
                                value={character.appearance}
                                onChange={(e) => updateField(index, "appearance", e.target.value)}
                                placeholder="外見の詳細"
                                disabled={disabled}
                                rows={2}
                            />
                        </label>

                        <label>
                            衣装
                            <input
                                type="text"
                                value={character.clothing ?? ""}
                                onChange={(e) => updateField(index, "clothing", e.target.value)}
                                placeholder="衣装の詳細"
                                disabled={disabled}
                            />
                        </label>

                        <label>
                            アクション
                            <input
                                type="text"
                                value={character.action ?? ""}
                                onChange={(e) => updateField(index, "action", e.target.value)}
                                placeholder="動作・アクション"
                                disabled={disabled}
                            />
                        </label>

                        <label>
                            配置
                            <input
                                type="text"
                                value={character.position ?? ""}
                                onChange={(e) => updateField(index, "position", e.target.value)}
                                placeholder="画面上の位置"
                                disabled={disabled}
                            />
                        </label>
                    </div>
                </div>
            ))}
        </div>
    );
};
