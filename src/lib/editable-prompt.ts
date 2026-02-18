/**
 * editable-prompt.ts
 *
 * エディタブルプロンプト — セクション別に編集可能なプロンプト構造
 *
 * リソース解析結果や手動入力を統一的なプロンプト形式に変換し、
 * セクション単位での編集→再生成を可能にする。
 *
 * FlowForge SDK — Data Model Layer
 */

import type {
    FlowShot,
    CharacterDetail,
    ObjectDetail,
} from "./flow-prompt-builder.js";

export interface PromptSection {
    id: string;
    label: string;
    content: string;
    source: "manual" | "analysis" | "refined";
    modified: boolean;
}

export interface EditablePromptData {
    sections: PromptSection[];
    combinedPrompt: string;
    shotRef?: FlowShot;
    updatedAt: string;
}

export class EditablePrompt {
    private sections: Map<string, PromptSection> = new Map();
    private shotRef?: FlowShot;

    constructor(shot?: FlowShot) {
        this.shotRef = shot;
        if (shot) {
            this.fromFlowShot(shot);
        }
    }

    fromFlowShot(shot: FlowShot): void {
        this.shotRef = shot;
        this.sections.clear();

        this.addSection("subject", "被写体", shot.subject);

        if (shot.action) {
            this.addSection("action", "アクション", shot.action);
        }

        if (shot.setting) {
            this.addSection("setting", "環境・背景", shot.setting);
        }

        if (shot.characters?.length) {
            const desc = shot.characters
                .map(c => this.describeCharacter(c))
                .join("; ");
            this.addSection("characters", "登場人物", desc);
        }

        if (shot.objects?.length) {
            const desc = shot.objects
                .map(o => this.describeObject(o))
                .join("; ");
            this.addSection("objects", "小道具・物体", desc);
        }

        if (shot.camera || shot.angle || shot.shotSize) {
            const parts = [
                shot.shotSize && `${shot.shotSize} shot`,
                shot.camera && `${shot.camera} movement`,
                shot.angle && `${shot.angle} angle`,
            ].filter(Boolean);
            this.addSection("camera", "カメラワーク", parts.join(", "));
        }

        if (shot.lighting) {
            this.addSection("lighting", "ライティング", shot.lighting);
        }

        if (shot.toneManner) {
            const tm = shot.toneManner;
            const parts = [tm.mood];
            if (tm.colorGrading) parts.push(tm.colorGrading);
            if (tm.filmStyle) parts.push(tm.filmStyle);
            if (tm.era) parts.push(`${tm.era} era`);
            this.addSection("tone", "トーン＆マナー", parts.join(", "));
        }

        if (shot.style) {
            this.addSection("style", "スタイル", shot.style);
        }
    }

    addSection(
        id: string,
        label: string,
        content: string,
        source: "manual" | "analysis" | "refined" = "manual",
    ): void {
        this.sections.set(id, {
            id,
            label,
            content,
            source,
            modified: false,
        });
    }

    editSection(id: string, content: string): void {
        const section = this.sections.get(id);
        if (!section) {
            throw new Error(`セクション "${id}" が見つかりません`);
        }
        section.content = content;
        section.modified = true;
    }

    getSection(id: string): PromptSection | undefined {
        return this.sections.get(id);
    }

    getSections(): PromptSection[] {
        return Array.from(this.sections.values());
    }

    hasSection(id: string): boolean {
        return this.sections.has(id);
    }

    removeSection(id: string): boolean {
        return this.sections.delete(id);
    }

    combine(): string {
        const parts: string[] = [];
        for (const section of this.sections.values()) {
            if (section.content.trim()) {
                parts.push(section.content.trim());
            }
        }
        return parts.join(". ") + ".";
    }

    toData(): EditablePromptData {
        return {
            sections: Array.from(this.sections.values()),
            combinedPrompt: this.combine(),
            shotRef: this.shotRef,
            updatedAt: new Date().toISOString(),
        };
    }

    static fromData(data: EditablePromptData): EditablePrompt {
        const prompt = new EditablePrompt();
        for (const section of data.sections) {
            prompt.addSection(section.id, section.label, section.content, section.source);
            if (section.modified) {
                const s = prompt.sections.get(section.id);
                if (s) s.modified = true;
            }
        }
        if (data.shotRef) {
            prompt.shotRef = data.shotRef;
        }
        return prompt;
    }

    private describeCharacter(c: CharacterDetail): string {
        const parts = [c.name];
        if (c.role) parts.push(`(${c.role})`);
        parts.push(c.appearance);
        if (c.clothing) parts.push(`wearing ${c.clothing}`);
        if (c.action) parts.push(c.action);
        if (c.position) parts.push(`positioned ${c.position}`);
        return parts.join(", ");
    }

    private describeObject(o: ObjectDetail): string {
        const parts = [o.name];
        parts.push(o.description);
        if (o.material) parts.push(`made of ${o.material}`);
        if (o.color) parts.push(o.color);
        if (o.scale) parts.push(`${o.scale} scale`);
        if (o.position) parts.push(`at ${o.position}`);
        return parts.join(", ");
    }
}
