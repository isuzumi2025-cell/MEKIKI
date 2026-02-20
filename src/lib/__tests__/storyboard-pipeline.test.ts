import { describe, it, expect } from "vitest";
import type { FlowShot } from "../flow-prompt-builder.js";
import type { StoryboardPipelineOptions } from "../storyboard-pipeline.js";
import { SubjectRegistry } from "../subject-registry.js";

describe("StoryboardPipeline options", () => {
    it("StoryboardPipelineOptions includes subjectRegistry", () => {
        const registry = new SubjectRegistry();
        const opts: StoryboardPipelineOptions = {
            subjectRegistry: registry,
        };
        expect(opts.subjectRegistry).toBe(registry);
    });

    it("StoryboardPipelineOptions includes referenceImages", () => {
        const opts: StoryboardPipelineOptions = {
            referenceImages: [
                {
                    imageBytes: "base64data",
                    mimeType: "image/png",
                    referenceType: "style",
                },
            ],
        };
        expect(opts.referenceImages!.length).toBe(1);
    });

    it("StoryboardPipelineOptions supports parallelShots", () => {
        const opts: StoryboardPipelineOptions = {
            parallelShots: 3,
            aspectRatio: "16:9",
        };
        expect(opts.parallelShots).toBe(3);
    });
});

describe("subject carryover prompt injection", () => {
    it("builds carryover prompt from registry", () => {
        const registry = new SubjectRegistry();
        registry.register({
            name: "Hero",
            type: "character",
            description: "A tall warrior with silver armor",
            keyFeatures: ["silver armor", "tall", "sword"],
            originCutId: "cut-001",
            carryover: true,
            tags: ["protagonist"],
        });
        registry.register({
            name: "Dragon",
            type: "animal",
            description: "A large red dragon",
            keyFeatures: ["red scales", "large wings"],
            originCutId: "cut-001",
            carryover: true,
            tags: ["antagonist"],
        });

        const prompt = registry.buildCarryoverPrompt();
        expect(prompt).toContain("Persistent Subjects");
        expect(prompt).toContain("Hero");
        expect(prompt).toContain("Dragon");
    });

    it("carryover prompt is empty when no carryover subjects", () => {
        const registry = new SubjectRegistry();
        registry.register({
            name: "BG",
            type: "background",
            description: "Forest",
            keyFeatures: ["trees"],
            originCutId: "cut-001",
            carryover: false,
            tags: [],
        });

        const prompt = registry.buildCarryoverPrompt();
        expect(prompt).toBe("");
    });

    it("carryover block appends to base prompt", () => {
        const basePrompt = "A warrior stands on a cliff";
        const registry = new SubjectRegistry();
        registry.register({
            name: "Warrior",
            type: "character",
            description: "Silver-armored warrior",
            keyFeatures: ["silver armor"],
            originCutId: "cut-001",
            carryover: true,
            tags: [],
        });

        const carryoverBlock = registry.buildCarryoverPrompt();
        const finalPrompt = carryoverBlock
            ? `${basePrompt}\n\n${carryoverBlock}`
            : basePrompt;

        expect(finalPrompt).toContain(basePrompt);
        expect(finalPrompt).toContain("Persistent Subjects");
    });
});

describe("chunk array utility", () => {
    it("splits array into chunks", () => {
        const arr = [1, 2, 3, 4, 5];
        const chunkSize = 2;
        const chunks: number[][] = [];
        for (let i = 0; i < arr.length; i += chunkSize) {
            chunks.push(arr.slice(i, i + chunkSize));
        }
        expect(chunks).toEqual([[1, 2], [3, 4], [5]]);
    });

    it("single chunk for small array", () => {
        const arr = [1, 2];
        const chunkSize = 5;
        const chunks: number[][] = [];
        for (let i = 0; i < arr.length; i += chunkSize) {
            chunks.push(arr.slice(i, i + chunkSize));
        }
        expect(chunks).toEqual([[1, 2]]);
    });

    it("empty array returns no chunks", () => {
        const arr: number[] = [];
        const chunkSize = 3;
        const chunks: number[][] = [];
        for (let i = 0; i < arr.length; i += chunkSize) {
            chunks.push(arr.slice(i, i + chunkSize));
        }
        expect(chunks).toEqual([]);
    });
});

describe("FlowShot structure for storyboard", () => {
    it("FlowShot has required subject field", () => {
        const shot: FlowShot = {
            subject: "A girl running through a field",
        };
        expect(shot.subject).toBeTruthy();
    });

    it("FlowShot supports all optional fields", () => {
        const shot: FlowShot = {
            subject: "Hero",
            action: "fighting",
            setting: "dark castle",
            camera: "tracking",
            angle: "low_angle",
            shotSize: "medium",
            lighting: "dramatic",
            style: "cinematic",
            negativePrompt: "blurry",
            characters: [
                { name: "Hero", appearance: "armored", role: "protagonist" },
            ],
            objects: [
                { name: "Sword", description: "glowing blade" },
            ],
            toneManner: {
                mood: "intense",
            },
        };
        expect(shot.action).toBe("fighting");
        expect(shot.characters!.length).toBe(1);
        expect(shot.objects!.length).toBe(1);
    });
});
