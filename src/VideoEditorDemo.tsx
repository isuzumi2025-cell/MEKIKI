/**
 * VideoEditorDemo.tsx
 *
 * 動画エディタ — カットナビゲーション + SubjectPanel サイドバー
 * public/cuts/ に置いた動画ファイルを分析し、サブジェクト自動抽出 → プロンプト生成。
 */

import React, { useState, useCallback, useMemo, useRef } from "react";
import { AbsoluteFill, Video, staticFile } from "remotion";
import { SubjectPanel } from "./lib/components/SubjectPanel";
import type { Subject } from "./lib/types/subject";

// ============================================================
// Types
// ============================================================

interface CutData {
    id: string;
    label: string;
    videoFile: string | null;
    subjects: Subject[];
    generatedPrompt: string;
    analyzed: boolean;
}

// ============================================================
// サンプルカットデータ
// ============================================================

const INITIAL_CUTS: CutData[] = [
    {
        id: "cut-001",
        label: "カット 1",
        videoFile: null,
        subjects: [],
        generatedPrompt: "",
        analyzed: false,
    },
    {
        id: "cut-002",
        label: "カット 2",
        videoFile: null,
        subjects: [],
        generatedPrompt: "",
        analyzed: false,
    },
    {
        id: "cut-003",
        label: "カット 3",
        videoFile: null,
        subjects: [],
        generatedPrompt: "",
        analyzed: false,
    },
];

// ============================================================
// Gemini Vision 分析 (シミュレーション)
// 実際はGEMINI_API_KEY があれば Gemini 2.5 Flash で分析。
// ここではデモ用にフレームから色やシーン情報を模擬抽出。
// ============================================================

function generateMockAnalysis(cutId: string): {
    subjects: Subject[];
    prompt: string;
} {
    const analyses: Record<string, { subjects: Subject[]; prompt: string }> = {
        "cut-001": {
            subjects: [
                {
                    id: `${cutId}-subj-1`,
                    name: "赤い帽子の少女",
                    description: "赤い帽子を被った少女。長い黒髪で白いワンピースを着ている。",
                    keyFeatures: ["赤い帽子", "長い黒髪", "白いワンピース", "茶色い靴"],
                    sourceJobId: cutId,
                    carryover: true,
                    createdAt: new Date(),
                },
                {
                    id: `${cutId}-subj-2`,
                    name: "白い猫",
                    description: "ふわふわの白い毛並みの猫。大きな青い目をしている。",
                    keyFeatures: ["白い毛並み", "青い目", "ピンクの鼻"],
                    sourceJobId: cutId,
                    carryover: true,
                    createdAt: new Date(),
                },
            ],
            prompt: [
                "## 生成プロンプト (Cut 1 分析結果)",
                "",
                "森の中を歩く赤い帽子の少女と白い猫のシーン。",
                "",
                "### 検出サブジェクト:",
                "- 👤 赤い帽子の少女: 赤い帽子、長い黒髪、白いワンピース、茶色い靴",
                "- 🐾 白い猫: 白い毛並み、青い目、ピンクの鼻",
                "",
                "### 推奨スタイル:",
                "- カメラ: ミディアムショット、追従",
                "- ライティング: 木漏れ日、暖色系",
                "- ムード: 穏やか、冒険の始まり",
            ].join("\n"),
        },
        "cut-002": {
            subjects: [
                {
                    id: `${cutId}-subj-1`,
                    name: "赤いスポーツカー",
                    description: "光沢のある赤いスポーツカー。低いフォルムでリアスポイラー付き。",
                    keyFeatures: ["赤い塗装", "スポイラー", "低いフォルム", "LEDヘッドライト"],
                    sourceJobId: cutId,
                    carryover: false,
                    createdAt: new Date(),
                },
            ],
            prompt: [
                "## 生成プロンプト (Cut 2 分析結果)",
                "",
                "夕焼けの丘を走る赤いスポーツカーのシーン。",
                "",
                "### 検出サブジェクト:",
                "- 🚗 赤いスポーツカー: 赤い塗装、スポイラー、低いフォルム",
                "",
                "### 推奨スタイル:",
                "- カメラ: ワイドショット、パン",
                "- ライティング: 夕焼け、ゴールデンアワー",
                "- ムード: スピード感、解放感",
            ].join("\n"),
        },
        "cut-003": {
            subjects: [
                {
                    id: `${cutId}-subj-1`,
                    name: "魔法の杖",
                    description: "先端に青い宝石がついた木製の魔法の杖。ルーン文字が刻まれている。",
                    keyFeatures: ["木製", "青い宝石", "ルーン文字", "30cm"],
                    sourceJobId: cutId,
                    carryover: false,
                    createdAt: new Date(),
                },
                {
                    id: `${cutId}-subj-2`,
                    name: "光る蝶",
                    description: "淡い青紫色に発光する蝶。翅に星座のような模様がある。",
                    keyFeatures: ["発光", "青紫色", "星座模様", "透明な翅"],
                    sourceJobId: cutId,
                    carryover: true,
                    createdAt: new Date(),
                },
            ],
            prompt: [
                "## 生成プロンプト (Cut 3 分析結果)",
                "",
                "薄暗い魔法の森で光る蝶と魔法の杖のシーン。",
                "",
                "### 検出サブジェクト:",
                "- 📦 魔法の杖: 木製、青い宝石、ルーン文字",
                "- 🐾 光る蝶: 発光、青紫色、星座模様",
                "",
                "### 推奨スタイル:",
                "- カメラ: クローズアップ → プルバック",
                "- ライティング: 生物発光、暗い森",
                "- ムード: 神秘的、静寂",
            ].join("\n"),
        },
    };

    return analyses[cutId] ?? { subjects: [], prompt: "分析データなし" };
}

function buildCarryoverPromptBlock(subjects: Subject[]): string {
    if (subjects.length === 0) return "";
    const lines = ["## 持越しサブジェクト (前カットから引き継ぎ)", ""];
    for (const s of subjects) {
        const icon = s.keyFeatures.some((f) => f.includes("毛") || f.includes("猫"))
            ? "🐾"
            : "👤";
        lines.push(`### ${icon} ${s.name}`);
        lines.push(`- 外見: ${s.description}`);
        lines.push(`- 特徴: ${s.keyFeatures.join(", ")}`);
        lines.push("");
    }
    return lines.join("\n");
}

// ============================================================
// Styles
// ============================================================

const containerStyle: React.CSSProperties = {
    display: "flex",
    width: "100%",
    height: "100%",
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    backgroundColor: "#0f0f1a",
};

const videoAreaStyle: React.CSSProperties = {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    padding: 16,
    gap: 8,
};

const sidebarStyle: React.CSSProperties = {
    width: 380,
    backgroundColor: "#151528",
    borderLeft: "1px solid #2a2a4a",
    overflow: "auto",
    padding: 12,
    display: "flex",
    flexDirection: "column",
    gap: 12,
};

const videoContainerStyle: React.CSSProperties = {
    flex: 1,
    backgroundColor: "#000",
    borderRadius: 10,
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    border: "1px solid #2a2a4a",
};

const cutNavStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    padding: "8px 0",
};

const navBtnStyle: React.CSSProperties = {
    padding: "8px 20px",
    borderRadius: 6,
    border: "1px solid #3a3a6a",
    backgroundColor: "#1e1e3a",
    color: "#c0c0e0",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
};

const navBtnDisabledStyle: React.CSSProperties = {
    ...navBtnStyle,
    opacity: 0.3,
    cursor: "not-allowed",
};

const analyzeBtnStyle: React.CSSProperties = {
    padding: "10px 24px",
    borderRadius: 8,
    border: "none",
    background: "linear-gradient(135deg, #667eea, #764ba2)",
    color: "#fff",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 700,
    boxShadow: "0 4px 12px rgba(102,126,234,0.3)",
    transition: "all 0.2s ease",
};

const analyzeBtnDoneStyle: React.CSSProperties = {
    ...analyzeBtnStyle,
    background: "linear-gradient(135deg, #43a047, #2e7d32)",
    boxShadow: "0 4px 12px rgba(67,160,71,0.3)",
    cursor: "default",
};

const promptBoxStyle: React.CSSProperties = {
    backgroundColor: "#1a1a30",
    border: "1px solid #2a2a4a",
    borderRadius: 8,
    padding: 12,
    fontSize: 12,
    color: "#c0c0e0",
    lineHeight: 1.6,
    whiteSpace: "pre-wrap",
    maxHeight: 280,
    overflow: "auto",
    fontFamily: "'JetBrains Mono', 'Consolas', monospace",
};

const sectionTitleStyle: React.CSSProperties = {
    color: "#a0a0d0",
    fontSize: 13,
    fontWeight: 700,
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
};

const carryoverBannerStyle: React.CSSProperties = {
    backgroundColor: "#1b2e1b",
    border: "1px solid #3a6a3a",
    borderRadius: 6,
    padding: "8px 12px",
    fontSize: 12,
    color: "#8fd88f",
};

const dropZoneStyle: React.CSSProperties = {
    border: "2px dashed #3a3a6a",
    borderRadius: 12,
    padding: 32,
    textAlign: "center",
    color: "#5a5a8a",
    fontSize: 13,
    lineHeight: 1.8,
};

const statusBadgeStyle: React.CSSProperties = {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 600,
};

// ============================================================
// Component
// ============================================================

export const VideoEditorDemo: React.FC = () => {
    const [currentCutIndex, setCurrentCutIndex] = useState(0);
    const [cuts, setCuts] = useState<CutData[]>(INITIAL_CUTS);
    const [analyzing, setAnalyzing] = useState(false);

    const currentCut = cuts[currentCutIndex];

    // 前のカットから carryover ON のサブジェクトを収集
    const carryoverSubjects = useMemo(() => {
        if (currentCutIndex === 0) return [];
        const carried: Subject[] = [];
        for (let i = 0; i < currentCutIndex; i++) {
            for (const subj of cuts[i].subjects) {
                if (subj.carryover && !carried.some((c) => c.id === subj.id)) {
                    carried.push(subj);
                }
            }
        }
        return carried;
    }, [currentCutIndex, cuts]);

    // 現在のカットのサブジェクト + carryover
    const allSubjects = useMemo(() => {
        const merged = [...currentCut.subjects];
        for (const carried of carryoverSubjects) {
            if (!merged.some((s) => s.id === carried.id)) {
                merged.push(carried);
            }
        }
        return merged;
    }, [currentCut.subjects, carryoverSubjects]);

    // 持ち越しプロンプト + 当カットプロンプト
    const fullPrompt = useMemo(() => {
        const parts: string[] = [];
        const carryBlock = buildCarryoverPromptBlock(carryoverSubjects);
        if (carryBlock) parts.push(carryBlock);
        if (currentCut.generatedPrompt) parts.push(currentCut.generatedPrompt);
        return parts.join("\n---\n\n");
    }, [carryoverSubjects, currentCut.generatedPrompt]);

    const handleToggleCarryover = useCallback(
        (id: string, carryover: boolean) => {
            setCuts((prev) =>
                prev.map((cut) => ({
                    ...cut,
                    subjects: cut.subjects.map((s) =>
                        s.id === id ? { ...s, carryover } : s
                    ),
                }))
            );
        },
        []
    );

    const handleAnalyze = useCallback(() => {
        setAnalyzing(true);
        // 分析シミュレーション (実働では Gemini Vision API を呼ぶ)
        setTimeout(() => {
            const result = generateMockAnalysis(currentCut.id);
            setCuts((prev) =>
                prev.map((cut) =>
                    cut.id === currentCut.id
                        ? {
                            ...cut,
                            subjects: result.subjects,
                            generatedPrompt: result.prompt,
                            analyzed: true,
                        }
                        : cut
                )
            );
            setAnalyzing(false);
        }, 1500);
    }, [currentCut.id]);

    return (
        <AbsoluteFill style={containerStyle}>
            {/* === 左: 動画エリア === */}
            <div style={videoAreaStyle}>
                <div style={videoContainerStyle}>
                    {currentCut.videoFile ? (
                        <Video
                            src={staticFile(`cuts/${currentCut.videoFile}`)}
                            style={{ width: "100%", height: "100%", objectFit: "contain" }}
                        />
                    ) : (
                        <div style={dropZoneStyle}>
                            <div style={{ fontSize: 40, marginBottom: 8 }}>🎬</div>
                            <div style={{ fontWeight: 700, color: "#7b7bba", marginBottom: 4 }}>
                                動画ファイルを配置してください
                            </div>
                            <code style={{ color: "#6b6baa" }}>
                                public/cuts/{currentCut.id}.mp4
                            </code>
                            <div style={{ marginTop: 12, fontSize: 12, color: "#4a4a7a" }}>
                                配置後リロードで自動表示 ・ 分析ボタンで Gemini Vision が解析
                            </div>
                        </div>
                    )}
                </div>

                {/* カットナビ + 分析ボタン */}
                <div style={cutNavStyle}>
                    <button
                        style={currentCutIndex === 0 ? navBtnDisabledStyle : navBtnStyle}
                        onClick={() => setCurrentCutIndex((i) => Math.max(0, i - 1))}
                        disabled={currentCutIndex === 0}
                    >
                        ◀ 前
                    </button>

                    <span style={{ color: "#c0c0e0", fontSize: 14, fontWeight: 600 }}>
                        {currentCutIndex + 1} / {cuts.length} — {currentCut.label}
                    </span>

                    <button
                        style={
                            currentCutIndex === cuts.length - 1
                                ? navBtnDisabledStyle
                                : navBtnStyle
                        }
                        onClick={() =>
                            setCurrentCutIndex((i) => Math.min(cuts.length - 1, i + 1))
                        }
                        disabled={currentCutIndex === cuts.length - 1}
                    >
                        次 ▶
                    </button>

                    <div style={{ width: 16 }} />

                    <button
                        style={
                            currentCut.analyzed
                                ? analyzeBtnDoneStyle
                                : analyzeBtnStyle
                        }
                        onClick={currentCut.analyzed ? undefined : handleAnalyze}
                        disabled={analyzing}
                    >
                        {analyzing
                            ? "🔍 分析中..."
                            : currentCut.analyzed
                                ? "✅ 分析済み"
                                : "🔍 Gemini Vision で分析"}
                    </button>
                </div>
            </div>

            {/* === 右: サイドバー === */}
            <div style={sidebarStyle}>
                {/* ステータス */}
                <div>
                    <span
                        style={{
                            ...statusBadgeStyle,
                            backgroundColor: currentCut.analyzed ? "#1b4332" : "#3a2a1a",
                            color: currentCut.analyzed ? "#95d5b2" : "#e09850",
                        }}
                    >
                        {currentCut.analyzed ? "✅ 分析完了" : "⏳ 未分析"}
                    </span>
                </div>

                {/* Carryover バナー */}
                {carryoverSubjects.length > 0 && (
                    <div style={carryoverBannerStyle}>
                        ↗ 前のカットから <strong>{carryoverSubjects.length}</strong> 件を持ち越し中
                    </div>
                )}

                {/* サブジェクトパネル */}
                <div>
                    <div style={sectionTitleStyle}>🎯 Detected Subjects</div>
                    {allSubjects.length > 0 ? (
                        <SubjectPanel
                            subjects={allSubjects}
                            onToggleCarryover={handleToggleCarryover}
                        />
                    ) : (
                        <div style={{ color: "#5a5a8a", fontSize: 12, padding: 12 }}>
                            「Gemini Vision で分析」ボタンを押すとサブジェクトが自動検出されます
                        </div>
                    )}
                </div>

                {/* 生成プロンプト */}
                <div>
                    <div style={sectionTitleStyle}>📝 Generated Prompt</div>
                    {fullPrompt ? (
                        <div style={promptBoxStyle}>{fullPrompt}</div>
                    ) : (
                        <div style={{ color: "#5a5a8a", fontSize: 12, padding: 12 }}>
                            分析するとプロンプトが自動生成されます
                        </div>
                    )}
                </div>
            </div>
        </AbsoluteFill>
    );
};
