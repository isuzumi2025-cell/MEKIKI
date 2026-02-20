import { describe, it, expect } from "vitest";
import { EditablePrompt } from "../editable-prompt.js";
import type { FlowShot } from "../flow-prompt-builder.js";

describe("EditablePrompt", () => {
    it("adds and retrieves sections", () => {
        const prompt = new EditablePrompt();
        prompt.addSection("scene", "シーン記述", "A sunset over the ocean");

        const section = prompt.getSection("scene");
        expect(section).toBeDefined();
        expect(section!.content).toBe("A sunset over the ocean");
        expect(section!.source).toBe("manual");
        expect(section!.modified).toBe(false);
    });

    it("edits a section and marks it modified", () => {
        const prompt = new EditablePrompt();
        prompt.addSection("scene", "シーン記述", "Original content");
        prompt.editSection("scene", "Updated content");

        const section = prompt.getSection("scene");
        expect(section!.content).toBe("Updated content");
        expect(section!.modified).toBe(true);
    });

    it("throws on editing nonexistent section", () => {
        const prompt = new EditablePrompt();
        expect(() => prompt.editSection("nonexistent", "content")).toThrow();
    });

    it("removes a section", () => {
        const prompt = new EditablePrompt();
        prompt.addSection("scene", "シーン記述", "content");
        expect(prompt.hasSection("scene")).toBe(true);

        prompt.removeSection("scene");
        expect(prompt.hasSection("scene")).toBe(false);
    });

    it("combines sections into a single prompt", () => {
        const prompt = new EditablePrompt();
        prompt.addSection("scene", "シーン記述", "A sunset");
        prompt.addSection("style", "スタイル", "cinematic");

        const combined = prompt.combine();
        expect(combined).toContain("A sunset");
        expect(combined).toContain("cinematic");
        expect(combined).toMatch(/\.$/);
    });

    it("skips empty sections in combine", () => {
        const prompt = new EditablePrompt();
        prompt.addSection("scene", "シーン記述", "A sunset");
        prompt.addSection("empty", "空", "   ");

        const combined = prompt.combine();
        expect(combined).toContain("A sunset");
        expect(combined).not.toContain("空");
    });

    it("getSections returns all sections", () => {
        const prompt = new EditablePrompt();
        prompt.addSection("a", "A", "content-a");
        prompt.addSection("b", "B", "content-b");
        prompt.addSection("c", "C", "content-c");

        expect(prompt.getSections().length).toBe(3);
    });

    it("fromFlowShot populates sections from shot data", () => {
        const shot: FlowShot = {
            subject: "A girl walking",
            action: "running through a field",
            setting: "golden wheat field at sunset",
            style: "cinematic",
            lighting: "golden hour",
        };

        const prompt = new EditablePrompt(shot);
        expect(prompt.hasSection("subject")).toBe(true);
        expect(prompt.hasSection("action")).toBe(true);
        expect(prompt.hasSection("setting")).toBe(true);
        expect(prompt.hasSection("style")).toBe(true);
        expect(prompt.hasSection("lighting")).toBe(true);
    });

    it("fromFlowShot includes characters section", () => {
        const shot: FlowShot = {
            subject: "Scene",
            characters: [
                { name: "Hero", appearance: "tall with armor", role: "protagonist" },
            ],
        };

        const prompt = new EditablePrompt(shot);
        expect(prompt.hasSection("characters")).toBe(true);
        const section = prompt.getSection("characters");
        expect(section!.content).toContain("Hero");
    });

    it("fromFlowShot includes objects section", () => {
        const shot: FlowShot = {
            subject: "Scene",
            objects: [
                { name: "Sword", description: "a glowing magical sword" },
            ],
        };

        const prompt = new EditablePrompt(shot);
        expect(prompt.hasSection("objects")).toBe(true);
        const section = prompt.getSection("objects");
        expect(section!.content).toContain("Sword");
    });

    it("fromFlowShot includes camera section", () => {
        const shot: FlowShot = {
            subject: "Scene",
            camera: "dolly_in",
            angle: "low_angle",
            shotSize: "wide",
        };

        const prompt = new EditablePrompt(shot);
        expect(prompt.hasSection("camera")).toBe(true);
        const section = prompt.getSection("camera");
        expect(section!.content).toContain("wide");
    });

    it("fromFlowShot includes tone section", () => {
        const shot: FlowShot = {
            subject: "Scene",
            toneManner: {
                mood: "melancholic",
                colorGrading: "desaturated",
                filmStyle: "noir",
            },
        };

        const prompt = new EditablePrompt(shot);
        expect(prompt.hasSection("tone")).toBe(true);
        const section = prompt.getSection("tone");
        expect(section!.content).toContain("melancholic");
    });
});

describe("EditablePrompt.toData / fromData", () => {
    it("round-trips via toData and fromData", () => {
        const original = new EditablePrompt();
        original.addSection("scene", "シーン記述", "A sunset", "analysis");
        original.addSection("style", "スタイル", "cinematic", "manual");
        original.editSection("style", "dramatic cinematic");

        const data = original.toData();
        const restored = EditablePrompt.fromData(data);

        expect(restored.getSections().length).toBe(2);
        expect(restored.getSection("style")!.content).toBe("dramatic cinematic");
        expect(restored.getSection("style")!.modified).toBe(true);
        expect(restored.getSection("scene")!.source).toBe("analysis");
    });

    it("toData includes combinedPrompt and updatedAt", () => {
        const prompt = new EditablePrompt();
        prompt.addSection("main", "メイン", "Hello world");

        const data = prompt.toData();
        expect(data.combinedPrompt).toBe("Hello world.");
        expect(data.updatedAt).toBeDefined();
    });

    it("fromData preserves shotRef", () => {
        const shot: FlowShot = { subject: "Test" };
        const original = new EditablePrompt(shot);
        const data = original.toData();
        expect(data.shotRef).toBeDefined();

        const restored = EditablePrompt.fromData(data);
        const restoredData = restored.toData();
        expect(restoredData.shotRef).toBeDefined();
        expect(restoredData.shotRef!.subject).toBe("Test");
    });
});
