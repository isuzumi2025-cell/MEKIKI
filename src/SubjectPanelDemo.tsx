/**
 * SubjectPanelDemo.tsx
 *
 * SubjectPanel を Remotion Studio でプレビューするためのデモコンポジション。
 * サンプルデータでサブジェクトの一覧・検索・carryover トグルを表示する。
 */

import React, { useState, useCallback } from "react";
import { AbsoluteFill } from "remotion";
import { SubjectPanel } from "./lib/components/SubjectPanel";
import type { Subject } from "./lib/types/subject";

// サンプルサブジェクトデータ
const INITIAL_SUBJECTS: Subject[] = [
    {
        id: "subj-001",
        name: "赤い帽子の少女",
        description: "赤い帽子を被った10歳くらいの少女。長い黒髪でワンピースを着ている。",
        keyFeatures: ["赤い帽子", "長い黒髪", "白いワンピース", "茶色い靴"],
        sourceJobId: "job-a1b2c3",
        carryover: true,
        createdAt: new Date("2026-02-18T10:00:00Z"),
    },
    {
        id: "subj-002",
        name: "白い猫",
        description: "ふわふわの白い毛並みの猫。大きな青い目をしている。",
        keyFeatures: ["白い毛並み", "青い目", "ピンクの鼻"],
        sourceJobId: "job-a1b2c3",
        carryover: true,
        createdAt: new Date("2026-02-18T10:00:00Z"),
    },
    {
        id: "subj-003",
        name: "赤いスポーツカー",
        description: "光沢のある赤いスポーツカー。低いフォルムでリアスポイラー付き。",
        keyFeatures: ["赤い塗装", "スポイラー", "低いフォルム", "LEDヘッドライト"],
        sourceJobId: "job-d4e5f6",
        carryover: false,
        createdAt: new Date("2026-02-18T11:00:00Z"),
    },
    {
        id: "subj-004",
        name: "夕焼けの丘",
        description: "オレンジと紫のグラデーションが美しい夕焼けの丘。風車が遠くに見える。",
        keyFeatures: ["夕焼け", "丘", "風車", "オレンジグラデーション"],
        carryover: true,
        createdAt: new Date("2026-02-18T11:30:00Z"),
    },
    {
        id: "subj-005",
        name: "魔法の杖",
        description: "先端に青い宝石がついた木製の魔法の杖。",
        keyFeatures: ["木製", "青い宝石", "30cm"],
        sourceJobId: "job-g7h8i9",
        carryover: false,
        createdAt: new Date("2026-02-18T12:00:00Z"),
    },
];

export const SubjectPanelDemo: React.FC = () => {
    const [subjects, setSubjects] = useState<Subject[]>(INITIAL_SUBJECTS);

    const handleToggleCarryover = useCallback((id: string, carryover: boolean) => {
        setSubjects((prev) =>
            prev.map((s) => (s.id === id ? { ...s, carryover } : s))
        );
    }, []);

    return (
        <AbsoluteFill
            style={{
                background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                padding: 40,
                fontFamily: "'Inter', 'Segoe UI', sans-serif",
            }}
        >
            <div style={{ width: "100%", maxWidth: 480 }}>
                <h2
                    style={{
                        color: "#fff",
                        fontSize: 24,
                        fontWeight: 700,
                        marginBottom: 16,
                        textAlign: "center",
                        textShadow: "0 2px 4px rgba(0,0,0,0.3)",
                    }}
                >
                    🎬 Subject Registry
                </h2>
                <SubjectPanel
                    subjects={subjects}
                    onToggleCarryover={handleToggleCarryover}
                />
            </div>
        </AbsoluteFill>
    );
};
