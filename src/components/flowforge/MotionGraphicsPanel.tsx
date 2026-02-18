/**
 * MotionGraphicsPanel.tsx
 *
 * モーショングラフィックス設定パネル — MG ベクトル設定
 * タイトル / テロップ / ローワーサード等の MG 要素を管理。
 *
 * FlowForge SDK — GUI Layer (T-416)
 */

import React, { useState, useCallback } from "react";
import type { MotionGraphicsConfig } from "../../lib/flow-prompt-builder";

export interface MotionGraphicsItem extends MotionGraphicsConfig {
    id: string;
    enabled: boolean;
}

export interface MotionGraphicsPanelProps {
    items: MotionGraphicsItem[];
    onChange: (items: MotionGraphicsItem[]) => void;
    disabled?: boolean;
}

const MG_TYPE_OPTIONS = [
    { value: "title", label: "タイトル", icon: "🏷️" },
    { value: "lower_third", label: "ローワーサード", icon: "📋" },
    { value: "caption", label: "キャプション", icon: "💬" },
    { value: "watermark", label: "ウォーターマーク", icon: "💧" },
    { value: "counter", label: "カウンター", icon: "🔢" },
    { value: "progress_bar", label: "プログレスバー", icon: "📊" },
    { value: "custom", label: "カスタム", icon: "🎨" },
];

const POSITION_OPTIONS = [
    { value: "top-left", label: "左上" },
    { value: "top-center", label: "上中央" },
    { value: "top-right", label: "右上" },
    { value: "center-left", label: "左中央" },
    { value: "center", label: "中央" },
    { value: "center-right", label: "右中央" },
    { value: "bottom-left", label: "左下" },
    { value: "bottom-center", label: "下中央" },
    { value: "bottom-right", label: "右下" },
];

const ANIMATION_OPTIONS = [
    { value: "none", label: "なし" },
    { value: "fade", label: "フェード" },
    { value: "slide_left", label: "左からスライド" },
    { value: "slide_right", label: "右からスライド" },
    { value: "slide_up", label: "下からスライド" },
    { value: "slide_down", label: "上からスライド" },
    { value: "scale", label: "スケール" },
    { value: "rotate", label: "回転" },
    { value: "blur", label: "ブラー" },
];

let mgNextId = 1;

export const MotionGraphicsPanel: React.FC<MotionGraphicsPanelProps> = ({
    items,
    onChange,
    disabled = false,
}) => {
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const addItem = useCallback(() => {
        const id = `mg-${Date.now()}-${mgNextId++}`;
        onChange([
            ...items,
            {
                id,
                type: "title",
                content: "",
                position: "center",
                animation: "fade",
                enabled: true,
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
        (id: string, patch: Partial<MotionGraphicsItem>) => {
            onChange(
                items.map((item) => (item.id === id ? { ...item, ...patch } : item)),
            );
        },
        [items, onChange],
    );

    const toggleEnabled = useCallback(
        (id: string) => {
            const item = items.find((i) => i.id === id);
            if (item) {
                updateItem(id, { enabled: !item.enabled });
            }
        },
        [items, updateItem],
    );

    const getTypeIcon = (type: string) => {
        return MG_TYPE_OPTIONS.find((opt) => opt.value === type)?.icon ?? "🎨";
    };

    return (
        <div className="mg-panel">
            <div className="mg-panel__header">
                <h2>モーショングラフィックス</h2>
                <p className="mg-panel__subtitle">
                    タイトル・テロップ・ローワーサード等の MG 要素を設定
                </p>
                <button
                    className="mg-panel__add-btn"
                    onClick={addItem}
                    disabled={disabled}
                >
                    + MG 要素追加
                </button>
            </div>

            {items.length === 0 && (
                <div className="mg-panel__empty">
                    <p>MG 要素がありません。</p>
                    <p style={{ fontSize: "12px", opacity: 0.7 }}>
                        「MG 要素追加」でタイトルやテロップを追加できます。
                    </p>
                </div>
            )}

            {items.map((item) => (
                <div
                    key={item.id}
                    className={`mg-panel__card ${!item.enabled ? "mg-panel__card--disabled" : ""}`}
                >
                    <div className="mg-panel__card-header">
                        <button
                            className="mg-panel__toggle"
                            onClick={() => toggleEnabled(item.id)}
                            disabled={disabled}
                            title={item.enabled ? "無効化" : "有効化"}
                        >
                            {item.enabled ? "🟢" : "⚫"}
                        </button>

                        <span className="mg-panel__type-badge">
                            {getTypeIcon(item.type)} {MG_TYPE_OPTIONS.find(o => o.value === item.type)?.label ?? item.type}
                        </span>

                        <button
                            className="mg-panel__expand-btn"
                            onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                        >
                            {expandedId === item.id ? "▲" : "▼"}
                        </button>

                        <button
                            className="mg-panel__remove-btn"
                            onClick={() => removeItem(item.id)}
                            disabled={disabled}
                            title="削除"
                        >
                            ✕
                        </button>
                    </div>

                    {/* コンテンツ入力 (常時表示) */}
                    <div className="mg-panel__content-row">
                        <input
                            type="text"
                            value={item.content}
                            onChange={(e) => updateItem(item.id, { content: e.target.value })}
                            placeholder="テキスト内容を入力..."
                            disabled={disabled || !item.enabled}
                        />
                    </div>

                    {/* 展開時の詳細設定 */}
                    {expandedId === item.id && (
                        <div className="mg-panel__details">
                            <div className="mg-panel__row">
                                <label>
                                    タイプ
                                    <select
                                        value={item.type}
                                        onChange={(e) => updateItem(item.id, { type: e.target.value })}
                                        disabled={disabled || !item.enabled}
                                    >
                                        {MG_TYPE_OPTIONS.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.icon} {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label>
                                    位置
                                    <select
                                        value={item.position ?? "center"}
                                        onChange={(e) => updateItem(item.id, { position: e.target.value })}
                                        disabled={disabled || !item.enabled}
                                    >
                                        {POSITION_OPTIONS.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label>
                                    アニメーション
                                    <select
                                        value={item.animation ?? "fade"}
                                        onChange={(e) => updateItem(item.id, { animation: e.target.value })}
                                        disabled={disabled || !item.enabled}
                                    >
                                        {ANIMATION_OPTIONS.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                            </div>

                            {/* プレビューヒント */}
                            <div className="mg-panel__preview-hint">
                                <span className="mg-panel__preview-label">プレビュー:</span>
                                <span className="mg-panel__preview-text">
                                    {getTypeIcon(item.type)}{" "}
                                    {item.content || "(テキスト未入力)"}{" "}
                                    @ {POSITION_OPTIONS.find(p => p.value === item.position)?.label ?? item.position}{" "}
                                    [{ANIMATION_OPTIONS.find(a => a.value === item.animation)?.label ?? "なし"}]
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            ))}

            {/* サマリー */}
            {items.length > 0 && (
                <div className="mg-panel__summary">
                    MG 要素: {items.filter(i => i.enabled).length} / {items.length} 有効
                </div>
            )}
        </div>
    );
};
