/**
 * ToneMannerPanel.tsx
 *
 * トーン＆マナー設定パネル — URL 参照 + カラーパレット設定
 * ToneMannerCrawler と連携してスタイル参照を管理。
 *
 * FlowForge SDK — GUI Layer (T-416)
 */

import React, { useState, useCallback } from "react";

export interface ToneMannerPanelProps {
    urls: string[];
    colorPalette: string[];
    onUrlsChange: (urls: string[]) => void;
    onPaletteChange: (colors: string[]) => void;
    disabled?: boolean;
}

export const ToneMannerPanel: React.FC<ToneMannerPanelProps> = ({
    urls,
    colorPalette,
    onUrlsChange,
    onPaletteChange,
    disabled = false,
}) => {
    const [newUrl, setNewUrl] = useState("");
    const [newColor, setNewColor] = useState("#000000");

    const addUrl = useCallback(() => {
        const trimmed = newUrl.trim();
        if (!trimmed) return;
        try {
            new URL(trimmed);
        } catch {
            return;
        }
        onUrlsChange([...urls, trimmed]);
        setNewUrl("");
    }, [newUrl, urls, onUrlsChange]);

    const removeUrl = useCallback(
        (index: number) => {
            onUrlsChange(urls.filter((_, i) => i !== index));
        },
        [urls, onUrlsChange],
    );

    const addColor = useCallback(() => {
        if (colorPalette.includes(newColor)) return;
        onPaletteChange([...colorPalette, newColor]);
    }, [newColor, colorPalette, onPaletteChange]);

    const removeColor = useCallback(
        (index: number) => {
            onPaletteChange(colorPalette.filter((_, i) => i !== index));
        },
        [colorPalette, onPaletteChange],
    );

    return (
        <div className="tone-manner-panel">
            <h2>トーン＆マナー</h2>

            <section className="tone-manner-panel__urls">
                <h3>参照 URL</h3>
                <div className="tone-manner-panel__input-row">
                    <input
                        type="url"
                        value={newUrl}
                        onChange={(e) => setNewUrl(e.target.value)}
                        placeholder="https://example.com/style-reference"
                        disabled={disabled}
                    />
                    <button onClick={addUrl} disabled={disabled || !newUrl.trim()}>
                        追加
                    </button>
                </div>

                {urls.length === 0 && (
                    <p className="tone-manner-panel__empty">
                        参照 URL が登録されていません。
                    </p>
                )}

                <ul className="tone-manner-panel__url-list">
                    {urls.map((url, index) => (
                        <li key={index} className="tone-manner-panel__url-item">
                            <a href={url} target="_blank" rel="noopener noreferrer">
                                {url}
                            </a>
                            <button
                                onClick={() => removeUrl(index)}
                                disabled={disabled}
                            >
                                削除
                            </button>
                        </li>
                    ))}
                </ul>
            </section>

            <section className="tone-manner-panel__palette">
                <h3>カラーパレット</h3>
                <div className="tone-manner-panel__input-row">
                    <input
                        type="color"
                        value={newColor}
                        onChange={(e) => setNewColor(e.target.value)}
                        disabled={disabled}
                    />
                    <span className="tone-manner-panel__color-hex">{newColor}</span>
                    <button onClick={addColor} disabled={disabled}>
                        追加
                    </button>
                </div>

                <div className="tone-manner-panel__swatches">
                    {colorPalette.map((color, index) => (
                        <div
                            key={index}
                            className="tone-manner-panel__swatch"
                        >
                            <div
                                className="tone-manner-panel__swatch-color"
                                style={{ backgroundColor: color }}
                            />
                            <span>{color}</span>
                            <button
                                onClick={() => removeColor(index)}
                                disabled={disabled}
                            >
                                x
                            </button>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
};
