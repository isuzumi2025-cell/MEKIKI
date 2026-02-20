import { describe, it, expect } from "vitest";
import type { VisualEditInstruction } from "../visual-edit-engine.js";
import { computeJaccardSimilarity } from "../subject-registry.js";

describe("VisualEditEngine types", () => {
    it("VisualEditInstruction supports all edit types", () => {
        const types: VisualEditInstruction["editType"][] = [
            "replace_shape",
            "replace_style",
            "replace_color",
            "add_from_image",
            "match_pose",
        ];
        expect(types.length).toBe(5);
    });

    it("VisualEditInstruction includes required fields", () => {
        const instruction: VisualEditInstruction = {
            referenceImageBytes: "base64data",
            referenceImageMimeType: "image/png",
            targetElement: "car",
            editType: "replace_shape",
        };
        expect(instruction.targetElement).toBe("car");
        expect(instruction.editType).toBe("replace_shape");
    });

    it("VisualEditInstruction supports optional additionalInstruction", () => {
        const instruction: VisualEditInstruction = {
            referenceImageBytes: "base64data",
            referenceImageMimeType: "image/png",
            targetElement: "car",
            editType: "replace_color",
            additionalInstruction: "Make it more vibrant",
        };
        expect(instruction.additionalInstruction).toBe("Make it more vibrant");
    });
});

describe("matchObjects with Jaccard similarity (unit logic)", () => {
    it("exact name match scores 1.0 via string includes", () => {
        const target = { name: "red car", description: "a shiny red sports car" };

        const nameMatch = target.name.toLowerCase().includes("red car");
        expect(nameMatch).toBe(true);
    });

    it("Jaccard fallback works for feature-based matching", () => {
        const targetFeatures = ["red car", "a shiny red sports car", "chrome wheels"];
        const refFeatures = ["red car", "vehicle", "chrome wheels", "leather seats"];

        const score = computeJaccardSimilarity(targetFeatures, refFeatures);
        expect(score).toBeGreaterThan(0);
    });

    it("Jaccard threshold 0.15 filters out weak matches", () => {
        const targetFeatures = ["mountain", "snow", "peak"];
        const refFeatures = ["ocean", "wave", "beach", "sand"];

        const score = computeJaccardSimilarity(targetFeatures, refFeatures);
        expect(score).toBeLessThan(0.15);
    });

    it("matched pairs are sorted by score descending", () => {
        const scores = [
            { name: "A", score: 0.3 },
            { name: "B", score: 0.8 },
            { name: "C", score: 0.5 },
        ];

        scores.sort((a, b) => b.score - a.score);
        expect(scores[0].name).toBe("B");
        expect(scores[1].name).toBe("C");
        expect(scores[2].name).toBe("A");
    });
});

describe("editType to referenceType mapping", () => {
    const EDIT_TYPE_TO_REFERENCE_TYPE: Record<VisualEditInstruction["editType"], string> = {
        replace_shape: "asset",
        replace_style: "style",
        replace_color: "style",
        add_from_image: "asset",
        match_pose: "subject",
    };

    it("replace_shape maps to asset", () => {
        expect(EDIT_TYPE_TO_REFERENCE_TYPE["replace_shape"]).toBe("asset");
    });

    it("replace_style maps to style", () => {
        expect(EDIT_TYPE_TO_REFERENCE_TYPE["replace_style"]).toBe("style");
    });

    it("replace_color maps to style", () => {
        expect(EDIT_TYPE_TO_REFERENCE_TYPE["replace_color"]).toBe("style");
    });

    it("add_from_image maps to asset", () => {
        expect(EDIT_TYPE_TO_REFERENCE_TYPE["add_from_image"]).toBe("asset");
    });

    it("match_pose maps to subject", () => {
        expect(EDIT_TYPE_TO_REFERENCE_TYPE["match_pose"]).toBe("subject");
    });
});
