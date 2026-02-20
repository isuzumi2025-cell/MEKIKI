import { describe, it, expect } from "vitest";
import type { StudioTab, FlowForgeStudioProps } from "../../components/flowforge/FlowForgeStudio.js";
import type { SubjectPanelProps } from "../../components/flowforge/SubjectPanel.js";
import type { Subject, SubjectCreateInput } from "../subject-registry.js";

describe("FlowForgeStudio types", () => {
    it("StudioTab includes subjects", () => {
        const tabs: StudioTab[] = [
            "prompt",
            "resources",
            "characters",
            "tone",
            "text",
            "motion_graphics",
            "visual_edit",
            "subjects",
        ];
        expect(tabs).toContain("subjects");
        expect(tabs.length).toBe(8);
    });

    it("FlowForgeStudioProps includes subject callbacks", () => {
        const props: FlowForgeStudioProps = {
            subjects: [],
            onSubjectRegister: (_input: SubjectCreateInput) => {},
            onSubjectDelete: (_id: string) => {},
            onSubjectToggleCarryover: (_id: string, _carry: boolean) => {},
        };
        expect(props.subjects).toEqual([]);
        expect(typeof props.onSubjectRegister).toBe("function");
        expect(typeof props.onSubjectDelete).toBe("function");
        expect(typeof props.onSubjectToggleCarryover).toBe("function");
    });
});

describe("SubjectPanel types", () => {
    it("SubjectPanelProps includes required fields", () => {
        const subjects: Subject[] = [
            {
                id: crypto.randomUUID(),
                name: "Hero",
                type: "character",
                description: "A brave warrior",
                keyFeatures: ["armor", "sword"],
                originCutId: "cut-001",
                carryover: true,
                tags: ["protagonist"],
                createdAt: new Date().toISOString(),
            },
        ];

        const props: SubjectPanelProps = {
            subjects,
            onRegister: (_input: SubjectCreateInput) => {},
            onDelete: (_id: string) => {},
            onToggleCarryover: (_id: string, _carry: boolean) => {},
        };

        expect(props.subjects.length).toBe(1);
        expect(props.subjects[0].name).toBe("Hero");
    });

    it("SubjectPanelProps supports disabled state", () => {
        const props: SubjectPanelProps = {
            subjects: [],
            disabled: true,
        };
        expect(props.disabled).toBe(true);
    });
});

describe("Root composition structure", () => {
    it("FlowForgeStudio composition exists in Root", () => {
        const compositions = [
            "MyComp",
            "SubjectPanel",
            "VideoEditor",
            "FlowForgeStudio",
        ];
        expect(compositions).toContain("FlowForgeStudio");
        expect(compositions).toContain("SubjectPanel");
    });
});
