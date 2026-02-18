/**
 * TextProcessingPanel.tsx
 *
 * テキスト処理パネル — 動画内テキストの3モード制御
 *   preserve: テキストをそのまま保持
 *   erase:    テキストを除去
 *   animate:  テキストをアニメーション化 (テロップ等)
 *
 * FlowForge SDK — GUI Layer (T-414)
 */

import React, { useState, useCallback } from "react";

export type TextProcessingMode = "preserve" | "erase" | "animate";

export interface TextItem {
    id: string;
    content: string;
    mode: TextProcessingMode;
    animationType?: "fade_in" | "typewriter" | "slide_up" | "bounce" | "glow";
    duration?: number;
    delay?: number;
    position?: "top" | "center" | "bottom" | "custom";
    fontSize?: "small" | "medium" | "large";
}

export interface TextProcessingPanelProps {
    items: TextItem[];
    onChange: (items: TextItem[]) => void;
    disabled?: boolean;
}

const MODE_LABELS: Record<TextProcessingMode, { label: string; description: string; icon: string }> = {
    preserve: { label: "保持", description: "テキストをそのまま動画に含める", icon: "📝" },
    erase: { label: "除去", description: "テキストを動画から除去する", icon: "🗑️" },
    animate: { label: "アニメーション", description: "テキストにアニメーション効果を付与", icon: "✨" },
};

const ANIMATION_OPTIONS = [
    { value: "fade_in", label: "フェードイン" },
    { value: "typewriter", label: "タイプライター" },
    { value: "slide_up", label: "スライドアップ" },
    { value: "bounce", label: "バウンス" },
    { value: "glow", label: "グロー" },
];

const POSITION_OPTIONS = [
    { value: "top", label: "上部" },
    { value: "center", label: "中央" },
    { value: "bottom", label: "下部" },
    { value: "custom", label: "カスタム" },
];

const FONT_SIZE_OPTIONS = [
    { value: "small", label: "小" },
    { value: "medium", label: "中" },
    { value: "large", label: "大" },
];

let nextId = 1;

export const TextProcessingPanel: React.FC<TextProcessingPanelProps> = ({
    items,
    onChange,
    disabled = false,
}) => {
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const addItem = useCallback(() => {
        const id = `text-${Date.now()}-${nextId++}`;
        onChange([
            ...items,
            {
                id,
                content: "",
                mode: "preserve",
                animationType: "fade_in",
                duration: 2,
                delay: 0,
                position: "bottom",
                fontSize: "medium",
            },
        ]);
        setExpandedId(id);
    }, [items, onChange]);

    const removeItem = useCallback(
        (id: string) => {
            onChange(items.filter((item) => item.id !== id));
            if (expandedId === id) setExpandedId(null);
        },
        [items, onChange, expandedId],
    );

    const updateItem = useCallback(
        (id: string, patch: Partial<TextItem>) => {
            onChange(
                items.map((item) => (item.id === id ? { ...item, ...patch } : item)),
            );
        },
        [items, onChange],
    );

    return (
        <div className="text-processing-panel">
            <div className="text-processing-panel__header">
                <h2>テキスト処理</h2>
                <p className="text-processing-panel__subtitle">
                    動画内テキストの表示方法を制御
                </p>
                <button
                    className="text-processing-panel__add-btn"
                    onClick={addItem}
                    disabled={disabled}
                >
                    + テキスト追加
                </button>
            </div>

            {items.length === 0 && (
                <div className="text-processing-panel__empty">
                    <p>テキスト要素がありません。</p>
                    <p style={{ fontSize: "12px", opacity: 0.7 }}>
                        「テキスト追加」でテロップやキャプションを追加できます。
                    </p>
                </div>
            )}

            {items.map((item) => (
                <div
                    key={item.id}
                    className={`text-processing-panel__card ${item.mode === "erase" ? "text-processing-panel__card--erased" : ""
                        }`}
                >
                    <div className="text-processing-panel__card-header">
                        <textarea
                            className="text-processing-panel__content-input"
                            value={item.content}
                            onChange={(e) => updateItem(item.id, { content: e.target.value })}
                            placeholder="テキスト内容を入力..."
                            disabled={disabled}
                            rows={2}
                        />
                        <button
                            className="text-processing-panel__remove-btn"
                            onClick={() => removeItem(item.id)}
                            disabled={disabled}
                            title="削除"
                        >
                            ✕
                        </button>
                    </div>

                    {/* モード選択 */}
                    <div className="text-processing-panel__modes">
                        {(Object.entries(MODE_LABELS) as [TextProcessingMode, typeof MODE_LABELS["preserve"]][]).map(
                            ([mode, info]) => (
                                <button
                                    key={mode}
                                    className={`text-processing-panel__mode-btn ${item.mode === mode ? "text-processing-panel__mode-btn--active" : ""
                                        }`}
                                    onClick={() => updateItem(item.id, { mode })}
                                    disabled={disabled}
                                    title={info.description}
                                >
                                    {info.icon} {info.label}
                                </button>
                            ),
                        )}
                    </div>

                    {/* アニメーション設定 (animate モードのみ) */}
                    {item.mode === "animate" && (
                        <div className="text-processing-panel__animate-settings">
                            <div className="text-processing-panel__row">
                                <label>
                                    アニメーション
                                    <select
                                        value={item.animationType ?? "fade_in"}
                                        onChange={(e) =>
                                            updateItem(item.id, {
                                                animationType: e.target.value as TextItem["animationType"],
                                            })
                                        }
                                        disabled={disabled}
                                    >
                                        {ANIMATION_OPTIONS.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label>
                                    表示位置
                                    <select
                                        value={item.position ?? "bottom"}
                                        onChange={(e) =>
                                            updateItem(item.id, {
                                                position: e.target.value as TextItem["position"],
                                            })
                                        }
                                        disabled={disabled}
                                    >
                                        {POSITION_OPTIONS.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label>
                                    文字サイズ
                                    <select
                                        value={item.fontSize ?? "medium"}
                                        onChange={(e) =>
                                            updateItem(item.id, {
                                                fontSize: e.target.value as TextItem["fontSize"],
                                            })
                                        }
                                        disabled={disabled}
                                    >
                                        {FONT_SIZE_OPTIONS.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                            </div>

                            <div className="text-processing-panel__row">
                                <label>
                                    表示時間 (秒)
                                    <input
                                        type="number"
                                        value={item.duration ?? 2}
                                        onChange={(e) =>
                                            updateItem(item.id, { duration: Number(e.target.value) })
                                        }
                                        min={0.5}
                                        max={30}
                                        step={0.5}
                                        disabled={disabled}
                                    />
                                </label>

                                <label>
                                    遅延 (秒)
                                    <input
                                        type="number"
                                        value={item.delay ?? 0}
                                        onChange={(e) =>
                                            updateItem(item.id, { delay: Number(e.target.value) })
                                        }
                                        min={0}
                                        max={30}
                                        step={0.5}
                                        disabled={disabled}
                                    />
                                </label>
                            </div>
                        </div>
                    )}

                    {/* preserve モードの注釈 */}
                    {item.mode === "preserve" && (
                        <p className="text-processing-panel__note">
                            このテキストはそのまま動画プロンプトに含まれます。
                        </p>
                    )}

                    {/* erase モードの注釈 */}
                    {item.mode === "erase" && (
                        <p className="text-processing-panel__note text-processing-panel__note--warning">
                            このテキストは動画生成時に除去されます。
                        </p>
                    )}
                </div>
            ))}
        </div>
    );
};
