/**
 * client-material-pipeline.test.ts
 *
 * ClientMaterialPipeline のユニットテスト
 * - ディレクトリスキャン (権限エラー、シンボリックリンク、空ディレクトリ等)
 * - ファイル分類 (画像、PDF、動画、不明)
 * - Gemini Vision API 呼び出し (モック)
 * - スタイルプロファイル生成
 * - dominantAspectRatio 自動判定
 * - プロンプト生成
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import {
  ClientMaterialPipeline,
  type MaterialFile,
  type MaterialAnalysisResult,
  type StyleProfile,
} from "../client-material-pipeline.js";

// ============================================================
// モック設定
// ============================================================

vi.mock("../logger.js", () => ({
  createLogger: () => ({
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  }),
}));

const MOCK_API_KEY = "test-api-key-12345";

function createPipeline(
  overrides?: Partial<ConstructorParameters<typeof ClientMaterialPipeline>[0]>
) {
  return new ClientMaterialPipeline({
    apiKey: MOCK_API_KEY,
    ...overrides,
  });
}

// ============================================================
// PNG テストデータ (1x1 pixel)
// ============================================================

function createMinimalPng(): Buffer {
  const header = Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x01,
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
    0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41,
    0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
    0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
    0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,
    0x44, 0xae, 0x42, 0x60, 0x82,
  ]);
  return header;
}

function createPngWithDimensions(width: number, height: number): Buffer {
  const buf = createMinimalPng();
  buf.writeUInt32BE(width, 16);
  buf.writeUInt32BE(height, 20);
  return buf;
}

function createMinimalJpeg(width: number, height: number): Buffer {
  const buf = Buffer.alloc(20);
  buf[0] = 0xff;
  buf[1] = 0xd8;
  buf[2] = 0xff;
  buf[3] = 0xc0;
  buf.writeUInt16BE(17, 4);
  buf[6] = 8;
  buf.writeUInt16BE(height, 7);
  buf.writeUInt16BE(width, 9);
  return buf;
}

// ============================================================
// コンストラクタ
// ============================================================

describe("ClientMaterialPipeline constructor", () => {
  it("API キーなしで例外を投げる", () => {
    const origEnv = process.env.GEMINI_API_KEY;
    delete process.env.GEMINI_API_KEY;
    expect(() => new ClientMaterialPipeline()).toThrow(
      "GEMINI_API_KEY が設定されていません"
    );
    process.env.GEMINI_API_KEY = origEnv;
  });

  it("API キー指定で正常にインスタンス化", () => {
    const pipeline = createPipeline();
    expect(pipeline).toBeInstanceOf(ClientMaterialPipeline);
  });

  it("環境変数から API キーを取得", () => {
    const origEnv = process.env.GEMINI_API_KEY;
    process.env.GEMINI_API_KEY = "env-key-12345";
    const pipeline = new ClientMaterialPipeline();
    expect(pipeline).toBeInstanceOf(ClientMaterialPipeline);
    process.env.GEMINI_API_KEY = origEnv;
  });

  it("カスタムオプションを受け取る", () => {
    const pipeline = createPipeline({
      supportedImageExts: [".png"],
      supportedVideoExts: [".mp4"],
      maxFileSizeMB: 10,
      concurrency: 5,
    });
    expect(pipeline).toBeInstanceOf(ClientMaterialPipeline);
  });
});

// ============================================================
// ディレクトリスキャン
// ============================================================

describe("ClientMaterialPipeline.scanDirectory", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join("/tmp", "cmp-test-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("空ディレクトリをスキャンして空配列を返す", async () => {
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toEqual([]);
  });

  it("画像ファイルを検出", async () => {
    fs.writeFileSync(path.join(tmpDir, "test.png"), createMinimalPng());
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(1);
    expect(files[0].type).toBe("image");
    expect(files[0].name).toBe("test.png");
    expect(files[0].mimeType).toBe("image/png");
  });

  it("PDF ファイルを検出", async () => {
    fs.writeFileSync(path.join(tmpDir, "doc.pdf"), Buffer.from("%PDF-1.4"));
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(1);
    expect(files[0].type).toBe("pdf");
    expect(files[0].mimeType).toBe("application/pdf");
  });

  it("動画ファイルを検出", async () => {
    fs.writeFileSync(path.join(tmpDir, "clip.mp4"), Buffer.from("fake-mp4"));
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(1);
    expect(files[0].type).toBe("video");
    expect(files[0].mimeType).toBe("video/mp4");
  });

  it("未対応ファイルをスキップ", async () => {
    fs.writeFileSync(path.join(tmpDir, "readme.txt"), "hello");
    fs.writeFileSync(path.join(tmpDir, "data.json"), "{}");
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(0);
  });

  it("隠しファイルをスキップ", async () => {
    fs.writeFileSync(path.join(tmpDir, ".hidden.png"), createMinimalPng());
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(0);
  });

  it("サブディレクトリを再帰的にスキャン", async () => {
    const sub = path.join(tmpDir, "sub");
    fs.mkdirSync(sub);
    fs.writeFileSync(path.join(sub, "nested.jpg"), Buffer.from("fake-jpg"));
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(1);
    expect(files[0].name).toBe("nested.jpg");
  });

  it("ファイルサイズ制限を超えるファイルをスキップ", async () => {
    const largeData = Buffer.alloc(2 * 1024 * 1024);
    fs.writeFileSync(path.join(tmpDir, "large.png"), largeData);
    const pipeline = createPipeline({ maxFileSizeMB: 1 });
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(0);
  });

  it("存在しないディレクトリで例外", async () => {
    const pipeline = createPipeline();
    await expect(
      pipeline.scanDirectory("/nonexistent/path")
    ).rejects.toThrow("ディレクトリが見つかりません");
  });

  it("ファイルパスを渡すと例外", async () => {
    const filePath = path.join(tmpDir, "file.txt");
    fs.writeFileSync(filePath, "data");
    const pipeline = createPipeline();
    await expect(pipeline.scanDirectory(filePath)).rejects.toThrow(
      "ディレクトリではありません"
    );
  });

  it("シンボリックリンクを追跡", async () => {
    const sub = path.join(tmpDir, "real");
    fs.mkdirSync(sub);
    fs.writeFileSync(path.join(sub, "photo.png"), createMinimalPng());
    fs.symlinkSync(sub, path.join(tmpDir, "link"));
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files.length).toBeGreaterThanOrEqual(1);
    const names = files.map((f) => f.name);
    expect(names).toContain("photo.png");
  });

  it("循環シンボリックリンクを検出してスキップ", async () => {
    const sub = path.join(tmpDir, "dir");
    fs.mkdirSync(sub);
    fs.symlinkSync(tmpDir, path.join(sub, "loop"));
    fs.writeFileSync(path.join(tmpDir, "ok.png"), createMinimalPng());
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    const names = files.map((f) => f.name);
    expect(names).toContain("ok.png");
  });

  it("複数タイプの素材を正しく分類", async () => {
    fs.writeFileSync(path.join(tmpDir, "a.png"), createMinimalPng());
    fs.writeFileSync(path.join(tmpDir, "b.jpg"), Buffer.from("fake-jpg"));
    fs.writeFileSync(path.join(tmpDir, "c.pdf"), Buffer.from("%PDF-1.4"));
    fs.writeFileSync(path.join(tmpDir, "d.mp4"), Buffer.from("fake-mp4"));
    fs.writeFileSync(path.join(tmpDir, "e.txt"), "skip me");

    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(4);

    const types = files.map((f) => f.type).sort();
    expect(types).toEqual(["image", "image", "pdf", "video"]);
  });

  it("各種画像拡張子を検出", async () => {
    const exts = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"];
    for (const ext of exts) {
      fs.writeFileSync(
        path.join(tmpDir, `img${ext}`),
        createMinimalPng()
      );
    }
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(exts.length);
    for (const f of files) {
      expect(f.type).toBe("image");
    }
  });

  it("各種動画拡張子を検出", async () => {
    const exts = [".mp4", ".mov", ".avi", ".webm", ".mkv"];
    for (const ext of exts) {
      fs.writeFileSync(
        path.join(tmpDir, `vid${ext}`),
        Buffer.from("fake")
      );
    }
    const pipeline = createPipeline();
    const files = await pipeline.scanDirectory(tmpDir);
    expect(files).toHaveLength(exts.length);
    for (const f of files) {
      expect(f.type).toBe("video");
    }
  });
});

// ============================================================
// 画像サイズ取得 (scanDirectory 経由で間接テスト)
// ============================================================

describe("Image dimension detection", () => {
  it("PNG の幅・高さを正しく取得", () => {
    const pipeline = createPipeline();
    const buf = createPngWithDimensions(800, 600);
    const dims = (pipeline as unknown as { getImageDimensions: (data: Buffer, name: string) => { width: number; height: number } }).getImageDimensions(buf, "test.png");
    expect(dims).toEqual({ width: 800, height: 600 });
  });

  it("JPEG の幅・高さを正しく取得", () => {
    const pipeline = createPipeline();
    const buf = createMinimalJpeg(1920, 1080);
    const dims = (pipeline as unknown as { getImageDimensions: (data: Buffer, name: string) => { width: number; height: number } }).getImageDimensions(buf, "test.jpg");
    expect(dims).toEqual({ width: 1920, height: 1080 });
  });

  it("不正データでデフォルト値を返す", () => {
    const pipeline = createPipeline();
    const buf = Buffer.from([0x00, 0x01, 0x02]);
    const dims = (pipeline as unknown as { getImageDimensions: (data: Buffer, name: string) => { width: number; height: number } }).getImageDimensions(buf, "test.png");
    expect(dims).toEqual({ width: 1920, height: 1080 });
  });

  it("GIF の幅・高さを正しく取得", () => {
    const pipeline = createPipeline();
    const buf = Buffer.alloc(20);
    buf.write("GIF89a", 0, "ascii");
    buf.writeUInt16LE(320, 6);
    buf.writeUInt16LE(240, 8);
    const dims = (pipeline as unknown as { getImageDimensions: (data: Buffer, name: string) => { width: number; height: number } }).getImageDimensions(buf, "test.gif");
    expect(dims).toEqual({ width: 320, height: 240 });
  });

  it("BMP の幅・高さを正しく取得", () => {
    const pipeline = createPipeline();
    const buf = Buffer.alloc(30);
    buf.write("BM", 0, "ascii");
    buf.writeInt32LE(640, 18);
    buf.writeInt32LE(480, 22);
    const dims = (pipeline as unknown as { getImageDimensions: (data: Buffer, name: string) => { width: number; height: number } }).getImageDimensions(buf, "test.bmp");
    expect(dims).toEqual({ width: 640, height: 480 });
  });

  it("未対応拡張子でデフォルト値を返す", () => {
    const pipeline = createPipeline();
    const buf = Buffer.from("not-image");
    const dims = (pipeline as unknown as { getImageDimensions: (data: Buffer, name: string) => { width: number; height: number } }).getImageDimensions(buf, "test.tiff");
    expect(dims).toEqual({ width: 1920, height: 1080 });
  });
});

// ============================================================
// スタイルプロファイル生成
// ============================================================

function makeMaterialFile(overrides?: Partial<MaterialFile>): MaterialFile {
  return {
    path: "/tmp/test.png",
    type: "image",
    name: "test.png",
    sizeBytes: 1024,
    mimeType: "image/png",
    ...overrides,
  };
}

function makeAnalysis(
  overrides?: Partial<MaterialAnalysisResult>
): MaterialAnalysisResult {
  return {
    file: makeMaterialFile(),
    description: "テストシーン",
    dominantColors: ["red", "blue"],
    style: "flat design",
    mood: "bright",
    objects: ["object1"],
    textContent: ["BRAND"],
    aspectRatio: { width: 1920, height: 1080 },
    quality: "high",
    ...overrides,
  };
}

describe("ClientMaterialPipeline.generateStyleProfile", () => {
  it("空の解析結果でデフォルトプロファイルを返す", () => {
    const pipeline = createPipeline();
    const profile = pipeline.generateStyleProfile([]);
    expect(profile.dominantColors).toEqual([]);
    expect(profile.dominantStyle).toBe("");
    expect(profile.dominantMood).toBe("");
    expect(profile.dominantAspectRatio).toBe("16:9");
    expect(profile.suggestedPromptPrefix).toBe("");
  });

  it("単一解析結果からプロファイルを生成", () => {
    const pipeline = createPipeline();
    const profile = pipeline.generateStyleProfile([makeAnalysis()]);
    expect(profile.dominantColors).toContain("red");
    expect(profile.dominantColors).toContain("blue");
    expect(profile.dominantStyle).toBe("flat design");
    expect(profile.dominantMood).toBe("bright");
    expect(profile.dominantAspectRatio).toBe("16:9");
    expect(profile.brandElements).toContain("BRAND");
  });

  it("複数解析結果で最頻値を選択", () => {
    const pipeline = createPipeline();
    const analyses = [
      makeAnalysis({ style: "illustration", mood: "calm" }),
      makeAnalysis({ style: "illustration", mood: "energetic" }),
      makeAnalysis({ style: "flat design", mood: "calm" }),
    ];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.dominantStyle).toBe("illustration");
    expect(profile.dominantMood).toBe("calm");
  });

  it("dominantAspectRatio を画像メタデータから判定", () => {
    const pipeline = createPipeline();
    const analyses = [
      makeAnalysis({ aspectRatio: { width: 1080, height: 1920 } }),
      makeAnalysis({ aspectRatio: { width: 1080, height: 1920 } }),
      makeAnalysis({ aspectRatio: { width: 1920, height: 1080 } }),
    ];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.dominantAspectRatio).toBe("9:16");
  });

  it("1:1 アスペクト比を検出", () => {
    const pipeline = createPipeline();
    const analyses = [
      makeAnalysis({ aspectRatio: { width: 1000, height: 1000 } }),
    ];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.dominantAspectRatio).toBe("1:1");
  });

  it("4:3 アスペクト比を検出", () => {
    const pipeline = createPipeline();
    const analyses = [
      makeAnalysis({ aspectRatio: { width: 1024, height: 768 } }),
    ];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.dominantAspectRatio).toBe("4:3");
  });

  it("suggestedPromptPrefix にスタイルとムードが含まれる", () => {
    const pipeline = createPipeline();
    const profile = pipeline.generateStyleProfile([makeAnalysis()]);
    expect(profile.suggestedPromptPrefix).toContain("flat design");
    expect(profile.suggestedPromptPrefix).toContain("bright");
  });

  it("色の出現頻度でソート (上位5色)", () => {
    const pipeline = createPipeline();
    const analyses = [
      makeAnalysis({ dominantColors: ["red", "blue", "green"] }),
      makeAnalysis({ dominantColors: ["red", "yellow", "red"] }),
      makeAnalysis({ dominantColors: ["blue", "purple", "orange"] }),
    ];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.dominantColors[0]).toBe("red");
    expect(profile.dominantColors.length).toBeLessThanOrEqual(5);
  });

  it("brandElements にテキスト内容を抽出", () => {
    const pipeline = createPipeline();
    const analyses = [
      makeAnalysis({ textContent: ["LOGO", "TAGLINE"] }),
      makeAnalysis({ textContent: ["LOGO", "NEW TEXT"] }),
    ];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.brandElements).toContain("LOGO");
    expect(profile.brandElements).toContain("TAGLINE");
    expect(profile.brandElements).toContain("NEW TEXT");
  });

  it("typography フィールドを設定", () => {
    const pipeline = createPipeline();
    const analyses = [makeAnalysis({ textContent: ["SOME TEXT"] })];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.typography).toBe("テキスト要素あり");
  });

  it("テキストなしの場合 typography は undefined", () => {
    const pipeline = createPipeline();
    const analyses = [makeAnalysis({ textContent: [] })];
    const profile = pipeline.generateStyleProfile(analyses);
    expect(profile.typography).toBeUndefined();
  });
});

// ============================================================
// プロンプト生成
// ============================================================

describe("ClientMaterialPipeline.generatePrompts", () => {
  it("シーンごとにプロンプトを生成", () => {
    const pipeline = createPipeline();
    const profile: StyleProfile = {
      dominantColors: ["red", "blue"],
      dominantStyle: "illustration",
      dominantMood: "bright",
      dominantAspectRatio: "16:9",
      brandElements: ["BRAND"],
      suggestedPromptPrefix: "illustration, bright mood",
    };

    const prompts = pipeline.generatePrompts(profile, [
      "Scene 1: A hero walks",
      "Scene 2: The climax",
    ]);

    expect(prompts).toHaveLength(2);
    expect(prompts[0]).toContain("illustration, bright mood");
    expect(prompts[0]).toContain("Scene 1");
    expect(prompts[0]).toContain("BRAND");
    expect(prompts[1]).toContain("Scene 2");
  });

  it("空シーンで空配列を返す", () => {
    const pipeline = createPipeline();
    const profile: StyleProfile = {
      dominantColors: [],
      dominantStyle: "",
      dominantMood: "",
      dominantAspectRatio: "16:9",
      brandElements: [],
      suggestedPromptPrefix: "",
    };

    const prompts = pipeline.generatePrompts(profile, []);
    expect(prompts).toEqual([]);
  });

  it("プロンプト接頭辞なしでもシーンを含む", () => {
    const pipeline = createPipeline();
    const profile: StyleProfile = {
      dominantColors: [],
      dominantStyle: "",
      dominantMood: "",
      dominantAspectRatio: "16:9",
      brandElements: [],
      suggestedPromptPrefix: "",
    };

    const prompts = pipeline.generatePrompts(profile, ["Scene A"]);
    expect(prompts[0]).toContain("Scene A");
  });
});

// ============================================================
// analyzeMaterials (Gemini Vision モック)
// ============================================================

describe("ClientMaterialPipeline.analyzeMaterials", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join("/tmp", "cmp-analyze-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
    vi.restoreAllMocks();
  });

  it("画像ファイルの解析 (Gemini Vision モック)", async () => {
    const imgPath = path.join(tmpDir, "test.png");
    fs.writeFileSync(imgPath, createPngWithDimensions(800, 600));

    const mockResponse = {
      ok: true,
      json: async () => ({
        candidates: [
          {
            content: {
              parts: [
                {
                  text: JSON.stringify({
                    description: "テストシーン描写",
                    dominantColors: ["赤", "青"],
                    style: "illustration",
                    mood: "明るい",
                    objects: ["花", "木"],
                    textContent: ["ロゴ"],
                    quality: "high",
                  }),
                },
              ],
            },
          },
        ],
      }),
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    const pipeline = createPipeline();
    const file: MaterialFile = {
      path: imgPath,
      type: "image",
      name: "test.png",
      sizeBytes: 100,
      mimeType: "image/png",
    };

    const results = await pipeline.analyzeMaterials([file]);
    expect(results).toHaveLength(1);
    expect(results[0].description).toBe("テストシーン描写");
    expect(results[0].dominantColors).toContain("赤");
    expect(results[0].aspectRatio).toEqual({ width: 800, height: 600 });
    expect(results[0].quality).toBe("high");
  });

  it("PDF ファイルの解析 (Gemini Vision モック)", async () => {
    const pdfPath = path.join(tmpDir, "doc.pdf");
    fs.writeFileSync(pdfPath, Buffer.from("%PDF-1.4 fake content"));

    const mockResponse = {
      ok: true,
      json: async () => ({
        candidates: [
          {
            content: {
              parts: [
                {
                  text: JSON.stringify({
                    description: "PDFドキュメント",
                    dominantColors: ["白", "黒"],
                    style: "corporate",
                    mood: "professional",
                    objects: ["ロゴ"],
                    textContent: ["会社名"],
                    quality: "medium",
                  }),
                },
              ],
            },
          },
        ],
      }),
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    const pipeline = createPipeline();
    const file: MaterialFile = {
      path: pdfPath,
      type: "pdf",
      name: "doc.pdf",
      sizeBytes: 100,
      mimeType: "application/pdf",
    };

    const results = await pipeline.analyzeMaterials([file]);
    expect(results).toHaveLength(1);
    expect(results[0].description).toBe("PDFドキュメント");
    expect(results[0].aspectRatio).toEqual({ width: 210, height: 297 });
  });

  it("動画ファイルの解析 (Gemini Vision モック)", async () => {
    const videoPath = path.join(tmpDir, "clip.mp4");
    fs.writeFileSync(videoPath, Buffer.from("fake-video-data"));

    const mockResponse = {
      ok: true,
      json: async () => ({
        candidates: [
          {
            content: {
              parts: [
                {
                  text: JSON.stringify({
                    description: "動画シーン",
                    dominantColors: ["緑"],
                    style: "cinematic",
                    mood: "dramatic",
                    objects: ["車"],
                    textContent: [],
                    quality: "high",
                  }),
                },
              ],
            },
          },
        ],
      }),
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    const pipeline = createPipeline();
    const file: MaterialFile = {
      path: videoPath,
      type: "video",
      name: "clip.mp4",
      sizeBytes: 100,
      mimeType: "video/mp4",
    };

    const results = await pipeline.analyzeMaterials([file]);
    expect(results).toHaveLength(1);
    expect(results[0].description).toBe("動画シーン");
  });

  it("Gemini API エラー時にスキップ", async () => {
    const imgPath = path.join(tmpDir, "bad.png");
    fs.writeFileSync(imgPath, createMinimalPng());

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    } as unknown as Response);

    const pipeline = createPipeline();
    const file: MaterialFile = {
      path: imgPath,
      type: "image",
      name: "bad.png",
      sizeBytes: 100,
      mimeType: "image/png",
    };

    const results = await pipeline.analyzeMaterials([file]);
    expect(results).toHaveLength(0);
  });

  it("並列解析 (concurrency 制御)", async () => {
    const files: MaterialFile[] = [];
    for (let i = 0; i < 5; i++) {
      const imgPath = path.join(tmpDir, `img${i}.png`);
      fs.writeFileSync(imgPath, createMinimalPng());
      files.push({
        path: imgPath,
        type: "image",
        name: `img${i}.png`,
        sizeBytes: 100,
        mimeType: "image/png",
      });
    }

    const mockResponse = {
      ok: true,
      json: async () => ({
        candidates: [
          {
            content: {
              parts: [
                {
                  text: JSON.stringify({
                    description: "画像",
                    dominantColors: [],
                    style: "",
                    mood: "",
                    objects: [],
                    textContent: [],
                    quality: "medium",
                  }),
                },
              ],
            },
          },
        ],
      }),
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    const pipeline = createPipeline({ concurrency: 2 });
    const results = await pipeline.analyzeMaterials(files);
    expect(results).toHaveLength(5);
  });

  it("空のGemini応答でデフォルト値を使用", async () => {
    const imgPath = path.join(tmpDir, "empty.png");
    fs.writeFileSync(imgPath, createMinimalPng());

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        candidates: [{ content: { parts: [{ text: "" }] } }],
      }),
    } as unknown as Response);

    const pipeline = createPipeline();
    const file: MaterialFile = {
      path: imgPath,
      type: "image",
      name: "empty.png",
      sizeBytes: 100,
      mimeType: "image/png",
    };

    const results = await pipeline.analyzeMaterials([file]);
    expect(results).toHaveLength(1);
    expect(results[0].quality).toBe("medium");
  });

  it("不正JSON応答でraw textをdescriptionに使用", async () => {
    const imgPath = path.join(tmpDir, "badjson.png");
    fs.writeFileSync(imgPath, createMinimalPng());

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        candidates: [
          {
            content: {
              parts: [{ text: "This is not JSON at all" }],
            },
          },
        ],
      }),
    } as unknown as Response);

    const pipeline = createPipeline();
    const file: MaterialFile = {
      path: imgPath,
      type: "image",
      name: "badjson.png",
      sizeBytes: 100,
      mimeType: "image/png",
    };

    const results = await pipeline.analyzeMaterials([file]);
    expect(results).toHaveLength(1);
    expect(results[0].description).toBe("This is not JSON at all");
  });
});

// ============================================================
// フルパイプライン (run)
// ============================================================

describe("ClientMaterialPipeline.run", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join("/tmp", "cmp-run-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
    vi.restoreAllMocks();
  });

  it("空ディレクトリでフルパイプラインを実行", async () => {
    const pipeline = createPipeline();
    const result = await pipeline.run(tmpDir);
    expect(result.files).toHaveLength(0);
    expect(result.analyses).toHaveLength(0);
    expect(result.profile.dominantAspectRatio).toBe("16:9");
    expect(result.prompts).toHaveLength(0);
  });

  it("シーン指定でプロンプト生成を含む", async () => {
    const pipeline = createPipeline();
    const result = await pipeline.run(tmpDir, ["Scene 1", "Scene 2"]);
    expect(result.prompts).toHaveLength(2);
  });
});
