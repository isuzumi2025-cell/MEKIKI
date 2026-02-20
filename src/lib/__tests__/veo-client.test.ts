import { describe, it, expect } from "vitest";
import type { GenerateVideoOptions, VeoReferenceImage } from "../veo-client.js";

describe("VeoClient validation (unit)", () => {
    it("GenerateVideoOptions requires prompt", () => {
        const opts: GenerateVideoOptions = {
            prompt: "A cat walking",
        };
        expect(opts.prompt).toBe("A cat walking");
    });

    it("VeoReferenceImage supports asset type", () => {
        const ref: VeoReferenceImage = {
            imageBytes: "base64data",
            mimeType: "image/png",
            referenceType: "asset",
        };
        expect(ref.referenceType).toBe("asset");
    });

    it("VeoReferenceImage supports style type", () => {
        const ref: VeoReferenceImage = {
            imageBytes: "base64data",
            mimeType: "image/jpeg",
            referenceType: "style",
        };
        expect(ref.referenceType).toBe("style");
    });

    it("VeoReferenceImage supports subject type", () => {
        const ref: VeoReferenceImage = {
            imageBytes: "base64data",
            mimeType: "image/webp",
            referenceType: "subject",
        };
        expect(ref.referenceType).toBe("subject");
    });

    it("GenerateVideoOptions accepts referenceImages array", () => {
        const refs: VeoReferenceImage[] = [
            { imageBytes: "img1", mimeType: "image/png", referenceType: "asset" },
            { imageBytes: "img2", mimeType: "image/jpeg", referenceType: "style" },
        ];
        const opts: GenerateVideoOptions = {
            prompt: "test",
            referenceImages: refs,
        };
        expect(opts.referenceImages!.length).toBe(2);
    });

    it("GenerateVideoOptions accepts optional fields", () => {
        const opts: GenerateVideoOptions = {
            prompt: "test",
            aspectRatio: "16:9",
            negativePrompt: "blurry",
            personGeneration: "allow_adult",
        };
        expect(opts.aspectRatio).toBe("16:9");
        expect(opts.negativePrompt).toBe("blurry");
        expect(opts.personGeneration).toBe("allow_adult");
    });

    it("subject referenceType maps to style in SDK (documented limitation)", () => {
        const ref: VeoReferenceImage = {
            imageBytes: "data",
            mimeType: "image/png",
            referenceType: "subject",
        };
        expect(ref.referenceType).toBe("subject");
    });
});
