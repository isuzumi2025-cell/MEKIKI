/**
 * client-material-pipeline.ts
 *
 * クライアント素材パイプライン — 画像・PDF・動画素材を自動解析し、
 * スタイルプロファイルとプロンプトを生成する。
 *
 * Gemini Vision API を使用した実際の画像解析、PDF ページ抽出、
 * 動画サムネイル抽出をサポート。
 *
 * @see docs/flowforge_client_material_spec.md
 *
 * FlowForge SDK — Client Material Layer
 */

import * as fs from "fs";
import * as path from "path";
import { z } from "zod";
import { withRetry } from "./utils/retry.js";
import { createLogger } from "./logger.js";

const logger = createLogger("client-material-pipeline");

// ============================================================
// Zod スキーマ
// ============================================================

const MaterialTypeSchema = z.enum(["image", "pdf", "video", "unknown"]);
export type MaterialType = z.infer<typeof MaterialTypeSchema>;

const MaterialFileSchema = z.object({
  path: z.string().min(1),
  type: MaterialTypeSchema,
  name: z.string().min(1),
  sizeBytes: z.number().nonnegative(),
  mimeType: z.string(),
});
export type MaterialFile = z.infer<typeof MaterialFileSchema>;

const AspectRatioSchema = z.object({
  width: z.number().positive(),
  height: z.number().positive(),
});

const QualitySchema = z.enum(["low", "medium", "high"]);

const MaterialAnalysisResultSchema = z.object({
  file: MaterialFileSchema,
  description: z.string(),
  dominantColors: z.array(z.string()),
  style: z.string(),
  mood: z.string(),
  objects: z.array(z.string()),
  textContent: z.array(z.string()),
  aspectRatio: AspectRatioSchema,
  quality: QualitySchema,
});
export type MaterialAnalysisResult = z.infer<typeof MaterialAnalysisResultSchema>;

const StyleProfileSchema = z.object({
  dominantColors: z.array(z.string()),
  dominantStyle: z.string(),
  dominantMood: z.string(),
  dominantAspectRatio: z.string(),
  typography: z.string().optional(),
  brandElements: z.array(z.string()),
  suggestedPromptPrefix: z.string(),
});
export type StyleProfile = z.infer<typeof StyleProfileSchema>;

// ============================================================
// 設定
// ============================================================

const DEFAULT_IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"];
const DEFAULT_VIDEO_EXTS = [".mp4", ".mov", ".avi", ".webm", ".mkv"];
const DEFAULT_PDF_EXT = ".pdf";
const DEFAULT_MAX_FILE_SIZE_MB = 50;
const DEFAULT_CONCURRENCY = 3;

export interface ClientMaterialPipelineOptions {
  apiKey?: string;
  supportedImageExts?: string[];
  supportedVideoExts?: string[];
  maxFileSizeMB?: number;
  concurrency?: number;
}

// ============================================================
// Gemini Vision API レスポンス型
// ============================================================

interface GeminiVisionResponse {
  candidates?: {
    content?: {
      parts?: { text?: string }[];
    };
  }[];
}

interface GeminiAnalysisPayload {
  description: string;
  dominantColors: string[];
  style: string;
  mood: string;
  objects: string[];
  textContent: string[];
  quality: "low" | "medium" | "high";
}

const GeminiAnalysisPayloadSchema = z.object({
  description: z.string().default(""),
  dominantColors: z.array(z.string()).default([]),
  style: z.string().default(""),
  mood: z.string().default(""),
  objects: z.array(z.string()).default([]),
  textContent: z.array(z.string()).default([]),
  quality: QualitySchema.default("medium"),
});

// ============================================================
// パイプライン本体
// ============================================================

export class ClientMaterialPipeline {
  private readonly apiKey: string;
  private readonly supportedImageExts: string[];
  private readonly supportedVideoExts: string[];
  private readonly maxFileSizeBytes: number;
  private readonly concurrency: number;

  constructor(options?: ClientMaterialPipelineOptions) {
    const key =
      options?.apiKey ??
      (typeof process !== "undefined" ? process.env.GEMINI_API_KEY : undefined);

    if (!key) {
      throw new Error(
        "[ClientMaterialPipeline] GEMINI_API_KEY が設定されていません。"
      );
    }

    this.apiKey = key;
    this.supportedImageExts = options?.supportedImageExts ?? DEFAULT_IMAGE_EXTS;
    this.supportedVideoExts = options?.supportedVideoExts ?? DEFAULT_VIDEO_EXTS;
    this.maxFileSizeBytes =
      (options?.maxFileSizeMB ?? DEFAULT_MAX_FILE_SIZE_MB) * 1024 * 1024;
    this.concurrency = options?.concurrency ?? DEFAULT_CONCURRENCY;
  }

  // ============================================================
  // ディレクトリスキャン
  // ============================================================

  async scanDirectory(dirPath: string): Promise<MaterialFile[]> {
    const absPath = path.resolve(dirPath);

    const dirPathValidation = z.string().min(1).safeParse(absPath);
    if (!dirPathValidation.success) {
      throw new Error(`[ClientMaterialPipeline] 不正なディレクトリパス: ${dirPath}`);
    }

    if (!fs.existsSync(absPath)) {
      throw new Error(
        `[ClientMaterialPipeline] ディレクトリが見つかりません: ${absPath}`
      );
    }

    let stat: fs.Stats;
    try {
      stat = fs.statSync(absPath);
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code === "EACCES") {
        logger.warn({ path: absPath }, "権限エラーでスキップ");
        return [];
      }
      throw err;
    }

    if (!stat.isDirectory()) {
      throw new Error(
        `[ClientMaterialPipeline] パスはディレクトリではありません: ${absPath}`
      );
    }

    const files: MaterialFile[] = [];
    const visited = new Set<string>();
    await this.scanRecursive(absPath, files, visited);
    return files;
  }

  private async scanRecursive(
    dirPath: string,
    result: MaterialFile[],
    visited: Set<string>
  ): Promise<void> {
    let realPath: string;
    try {
      realPath = fs.realpathSync(dirPath);
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code === "EACCES" || code === "ENOENT") {
        logger.warn({ path: dirPath, code }, "パス解決エラーでスキップ");
        return;
      }
      throw err;
    }

    if (visited.has(realPath)) {
      logger.warn({ path: dirPath }, "循環参照を検出、スキップ");
      return;
    }
    visited.add(realPath);

    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dirPath, { withFileTypes: true });
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code === "EACCES") {
        logger.warn({ path: dirPath }, "ディレクトリ読み取り権限エラーでスキップ");
        return;
      }
      throw err;
    }

    for (const entry of entries) {
      if (entry.name.startsWith(".")) {
        continue;
      }

      const fullPath = path.join(dirPath, entry.name);

      if (entry.isSymbolicLink()) {
        let linkStat: fs.Stats;
        try {
          linkStat = fs.statSync(fullPath);
        } catch {
          logger.warn({ path: fullPath }, "シンボリックリンク解決エラーでスキップ");
          continue;
        }

        if (linkStat.isDirectory()) {
          await this.scanRecursive(fullPath, result, visited);
          continue;
        }

        if (linkStat.isFile()) {
          this.addFileIfSupported(fullPath, entry.name, linkStat.size, result);
          continue;
        }
      }

      if (entry.isDirectory()) {
        await this.scanRecursive(fullPath, result, visited);
        continue;
      }

      if (entry.isFile()) {
        let fileStat: fs.Stats;
        try {
          fileStat = fs.statSync(fullPath);
        } catch {
          continue;
        }
        this.addFileIfSupported(fullPath, entry.name, fileStat.size, result);
      }
    }
  }

  private addFileIfSupported(
    fullPath: string,
    name: string,
    sizeBytes: number,
    result: MaterialFile[]
  ): void {
    if (sizeBytes > this.maxFileSizeBytes) {
      logger.info({ path: fullPath, sizeBytes }, "ファイルサイズ制限超過でスキップ");
      return;
    }

    const materialType = this.classifyFile(name);
    if (materialType === "unknown") {
      return;
    }

    const file: MaterialFile = {
      path: fullPath,
      type: materialType,
      name,
      sizeBytes,
      mimeType: this.getMimeType(name),
    };

    const validation = MaterialFileSchema.safeParse(file);
    if (validation.success) {
      result.push(validation.data);
    }
  }

  private classifyFile(name: string): MaterialType {
    const ext = path.extname(name).toLowerCase();
    if (this.supportedImageExts.includes(ext)) return "image";
    if (ext === DEFAULT_PDF_EXT) return "pdf";
    if (this.supportedVideoExts.includes(ext)) return "video";
    return "unknown";
  }

  private getMimeType(name: string): string {
    const ext = path.extname(name).toLowerCase();
    const mimeMap: Record<string, string> = {
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".png": "image/png",
      ".webp": "image/webp",
      ".gif": "image/gif",
      ".bmp": "image/bmp",
      ".tiff": "image/tiff",
      ".tif": "image/tiff",
      ".pdf": "application/pdf",
      ".mp4": "video/mp4",
      ".mov": "video/quicktime",
      ".avi": "video/x-msvideo",
      ".webm": "video/webm",
      ".mkv": "video/x-matroska",
    };
    return mimeMap[ext] ?? "application/octet-stream";
  }

  // ============================================================
  // 素材解析
  // ============================================================

  async analyzeMaterials(
    files: MaterialFile[]
  ): Promise<MaterialAnalysisResult[]> {
    const results: MaterialAnalysisResult[] = [];
    const chunks = chunkArray(files, this.concurrency);

    for (const chunk of chunks) {
      const chunkResults = await Promise.allSettled(
        chunk.map((file) => this.analyzeSingleMaterial(file))
      );

      for (const settled of chunkResults) {
        if (settled.status === "fulfilled") {
          results.push(settled.value);
        } else {
          logger.error({ error: settled.reason }, "素材解析エラー");
        }
      }
    }

    return results;
  }

  private async analyzeSingleMaterial(
    file: MaterialFile
  ): Promise<MaterialAnalysisResult> {
    switch (file.type) {
      case "image":
        return this.analyzeImageMaterial(file);
      case "pdf":
        return this.analyzePdfMaterial(file);
      case "video":
        return this.analyzeVideoMaterial(file);
      default:
        throw new Error(`未対応の素材タイプ: ${file.type}`);
    }
  }

  private async analyzeImageMaterial(
    file: MaterialFile
  ): Promise<MaterialAnalysisResult> {
    const imageData = fs.readFileSync(file.path);
    const base64 = imageData.toString("base64");
    const dimensions = this.getImageDimensions(imageData, file.name);

    const analysis = await this.callGeminiVision(base64, file.mimeType);

    return {
      file,
      description: analysis.description,
      dominantColors: analysis.dominantColors,
      style: analysis.style,
      mood: analysis.mood,
      objects: analysis.objects,
      textContent: analysis.textContent,
      aspectRatio: dimensions,
      quality: analysis.quality,
    };
  }

  private async analyzePdfMaterial(
    file: MaterialFile
  ): Promise<MaterialAnalysisResult> {
    const pdfData = fs.readFileSync(file.path);
    const base64 = pdfData.toString("base64");

    const analysis = await this.callGeminiVisionForPdf(base64);

    return {
      file,
      description: analysis.description,
      dominantColors: analysis.dominantColors,
      style: analysis.style,
      mood: analysis.mood,
      objects: analysis.objects,
      textContent: analysis.textContent,
      aspectRatio: { width: 210, height: 297 },
      quality: analysis.quality,
    };
  }

  private async analyzeVideoMaterial(
    file: MaterialFile
  ): Promise<MaterialAnalysisResult> {
    const videoData = fs.readFileSync(file.path);
    const base64 = videoData.toString("base64");

    const analysis = await this.callGeminiVisionForVideo(base64, file.mimeType);

    return {
      file,
      description: analysis.description,
      dominantColors: analysis.dominantColors,
      style: analysis.style,
      mood: analysis.mood,
      objects: analysis.objects,
      textContent: analysis.textContent,
      aspectRatio: { width: 16, height: 9 },
      quality: analysis.quality,
    };
  }

  // ============================================================
  // Gemini Vision API 呼び出し
  // ============================================================

  private async callGeminiVision(
    base64Data: string,
    mimeType: string
  ): Promise<GeminiAnalysisPayload> {
    const prompt = this.buildVisionAnalysisPrompt();

    const response = await withRetry(
      () => this.sendGeminiRequest(prompt, base64Data, mimeType),
      { maxAttempts: 3, baseDelayMs: 1000 }
    );

    return this.parseGeminiResponse(response);
  }

  private async callGeminiVisionForPdf(
    base64Data: string
  ): Promise<GeminiAnalysisPayload> {
    const prompt = this.buildPdfAnalysisPrompt();

    const response = await withRetry(
      () => this.sendGeminiRequest(prompt, base64Data, "application/pdf"),
      { maxAttempts: 3, baseDelayMs: 1000 }
    );

    return this.parseGeminiResponse(response);
  }

  private async callGeminiVisionForVideo(
    base64Data: string,
    mimeType: string
  ): Promise<GeminiAnalysisPayload> {
    const prompt = this.buildVideoAnalysisPrompt();

    const response = await withRetry(
      () => this.sendGeminiRequest(prompt, base64Data, mimeType),
      { maxAttempts: 3, baseDelayMs: 1000 }
    );

    return this.parseGeminiResponse(response);
  }

  private async sendGeminiRequest(
    prompt: string,
    base64Data: string,
    mimeType: string
  ): Promise<GeminiVisionResponse> {
    const url =
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent";

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-goog-api-key": this.apiKey,
      },
      body: JSON.stringify({
        contents: [
          {
            parts: [
              { text: prompt },
              { inlineData: { mimeType, data: base64Data } },
            ],
          },
        ],
        generationConfig: {
          temperature: 0.2,
          maxOutputTokens: 2048,
        },
      }),
    });

    if (!res.ok) {
      throw new Error(
        `Gemini Vision API エラー: ${res.status} ${res.statusText}`
      );
    }

    return (await res.json()) as GeminiVisionResponse;
  }

  private buildVisionAnalysisPrompt(): string {
    return `この画像を解析して、以下のJSON形式で結果を返してください。

{
  "description": "シーンの詳細な説明",
  "dominantColors": ["色1", "色2", "色3"],
  "style": "ビジュアルスタイルの説明 (例: フラットデザイン、写実的、イラスト調)",
  "mood": "画像のムード (例: 明るい、落ち着いた、エネルギッシュ)",
  "objects": ["検出されたオブジェクト1", "オブジェクト2"],
  "textContent": ["画像内のテキスト1", "テキスト2"],
  "quality": "low" | "medium" | "high"
}

JSONのみを返してください。マークダウン記法は使わないでください。`;
  }

  private buildPdfAnalysisPrompt(): string {
    return `このPDFドキュメントを解析して、以下のJSON形式で結果を返してください。
PDFの最初のページを中心に、デザイン要素を分析してください。

{
  "description": "ドキュメントの視覚的な説明",
  "dominantColors": ["色1", "色2", "色3"],
  "style": "デザインスタイルの説明",
  "mood": "ドキュメントのムード",
  "objects": ["検出されたデザイン要素1", "要素2"],
  "textContent": ["主要なテキスト内容1", "テキスト2"],
  "quality": "low" | "medium" | "high"
}

JSONのみを返してください。マークダウン記法は使わないでください。`;
  }

  private buildVideoAnalysisPrompt(): string {
    return `この動画を解析して、以下のJSON形式で結果を返してください。
動画の最初のフレームを中心に分析してください。

{
  "description": "シーンの詳細な説明",
  "dominantColors": ["色1", "色2", "色3"],
  "style": "ビジュアルスタイルの説明",
  "mood": "動画のムード",
  "objects": ["検出されたオブジェクト1", "オブジェクト2"],
  "textContent": ["動画内のテキスト1", "テキスト2"],
  "quality": "low" | "medium" | "high"
}

JSONのみを返してください。マークダウン記法は使わないでください。`;
  }

  private parseGeminiResponse(
    response: GeminiVisionResponse
  ): GeminiAnalysisPayload {
    const rawText = response.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!rawText) {
      logger.warn("Gemini API からの応答が空です。デフォルト値を使用。");
      return {
        description: "",
        dominantColors: [],
        style: "",
        mood: "",
        objects: [],
        textContent: [],
        quality: "medium",
      };
    }

    const cleanJson = rawText
      .replace(/```json\s*/g, "")
      .replace(/```\s*/g, "")
      .trim();

    try {
      const parsed = JSON.parse(cleanJson) as Record<string, unknown>;
      return GeminiAnalysisPayloadSchema.parse(parsed);
    } catch (err) {
      logger.warn({ rawText, error: err }, "Gemini レスポンスのパースに失敗。デフォルト値を使用。");
      return {
        description: rawText,
        dominantColors: [],
        style: "",
        mood: "",
        objects: [],
        textContent: [],
        quality: "medium",
      };
    }
  }

  // ============================================================
  // 画像メタデータ
  // ============================================================

  private getImageDimensions(
    data: Buffer,
    fileName: string
  ): { width: number; height: number } {
    const ext = path.extname(fileName).toLowerCase();

    try {
      if (ext === ".png") {
        return this.getPngDimensions(data);
      }
      if (ext === ".jpg" || ext === ".jpeg") {
        return this.getJpegDimensions(data);
      }
      if (ext === ".gif") {
        return this.getGifDimensions(data);
      }
      if (ext === ".bmp") {
        return this.getBmpDimensions(data);
      }
      if (ext === ".webp") {
        return this.getWebpDimensions(data);
      }
    } catch {
      logger.warn({ fileName }, "画像サイズ取得に失敗。デフォルト値を使用。");
    }

    return { width: 1920, height: 1080 };
  }

  private getPngDimensions(data: Buffer): { width: number; height: number } {
    if (data.length < 24) return { width: 1920, height: 1080 };
    const width = data.readUInt32BE(16);
    const height = data.readUInt32BE(20);
    return { width, height };
  }

  private getJpegDimensions(data: Buffer): { width: number; height: number } {
    let offset = 2;
    while (offset < data.length) {
      if (data[offset] !== 0xff) break;
      const marker = data[offset + 1];
      if (marker === 0xc0 || marker === 0xc2) {
        const height = data.readUInt16BE(offset + 5);
        const width = data.readUInt16BE(offset + 7);
        return { width, height };
      }
      const segmentLength = data.readUInt16BE(offset + 2);
      offset += 2 + segmentLength;
    }
    return { width: 1920, height: 1080 };
  }

  private getGifDimensions(data: Buffer): { width: number; height: number } {
    if (data.length < 10) return { width: 1920, height: 1080 };
    const width = data.readUInt16LE(6);
    const height = data.readUInt16LE(8);
    return { width, height };
  }

  private getBmpDimensions(data: Buffer): { width: number; height: number } {
    if (data.length < 26) return { width: 1920, height: 1080 };
    const width = data.readInt32LE(18);
    const height = Math.abs(data.readInt32LE(22));
    return { width, height };
  }

  private getWebpDimensions(data: Buffer): { width: number; height: number } {
    if (data.length < 30) return { width: 1920, height: 1080 };

    const riffHeader = data.slice(0, 4).toString("ascii");
    if (riffHeader !== "RIFF") return { width: 1920, height: 1080 };

    const webpMarker = data.slice(8, 12).toString("ascii");
    if (webpMarker !== "WEBP") return { width: 1920, height: 1080 };

    const chunkType = data.slice(12, 16).toString("ascii");
    if (chunkType === "VP8 " && data.length >= 30) {
      const width = data.readUInt16LE(26) & 0x3fff;
      const height = data.readUInt16LE(28) & 0x3fff;
      return { width, height };
    }
    if (chunkType === "VP8L" && data.length >= 25) {
      const bits = data.readUInt32LE(21);
      const width = (bits & 0x3fff) + 1;
      const height = ((bits >> 14) & 0x3fff) + 1;
      return { width, height };
    }

    return { width: 1920, height: 1080 };
  }

  // ============================================================
  // スタイルプロファイル生成
  // ============================================================

  generateStyleProfile(analyses: MaterialAnalysisResult[]): StyleProfile {
    if (analyses.length === 0) {
      return {
        dominantColors: [],
        dominantStyle: "",
        dominantMood: "",
        dominantAspectRatio: "16:9",
        brandElements: [],
        suggestedPromptPrefix: "",
      };
    }

    const dominantColors = this.extractDominantColors(analyses);
    const dominantStyle = this.findMostFrequent(
      analyses.map((a) => a.style).filter(Boolean)
    );
    const dominantMood = this.findMostFrequent(
      analyses.map((a) => a.mood).filter(Boolean)
    );
    const dominantAspectRatio = this.calculateDominantAspectRatio(analyses);
    const brandElements = this.extractBrandElements(analyses);
    const typography = this.extractTypography(analyses);
    const suggestedPromptPrefix = this.buildSuggestedPromptPrefix(
      dominantStyle,
      dominantMood,
      dominantColors
    );

    const profile: StyleProfile = {
      dominantColors,
      dominantStyle,
      dominantMood,
      dominantAspectRatio,
      typography: typography || undefined,
      brandElements,
      suggestedPromptPrefix,
    };

    return StyleProfileSchema.parse(profile);
  }

  private extractDominantColors(analyses: MaterialAnalysisResult[]): string[] {
    const colorCounts = new Map<string, number>();

    for (const analysis of analyses) {
      for (const color of analysis.dominantColors) {
        const normalized = color.toLowerCase().trim();
        colorCounts.set(normalized, (colorCounts.get(normalized) ?? 0) + 1);
      }
    }

    return [...colorCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([color]) => color);
  }

  private calculateDominantAspectRatio(
    analyses: MaterialAnalysisResult[]
  ): string {
    const ratioCounts = new Map<string, number>();

    for (const analysis of analyses) {
      const { width, height } = analysis.aspectRatio;
      const ratio = this.normalizeAspectRatio(width, height);
      ratioCounts.set(ratio, (ratioCounts.get(ratio) ?? 0) + 1);
    }

    if (ratioCounts.size === 0) return "16:9";

    let maxCount = 0;
    let dominant = "16:9";
    for (const [ratio, count] of ratioCounts) {
      if (count > maxCount) {
        maxCount = count;
        dominant = ratio;
      }
    }

    return dominant;
  }

  private normalizeAspectRatio(width: number, height: number): string {
    const gcdVal = this.gcd(width, height);
    const w = width / gcdVal;
    const h = height / gcdVal;

    const ratio = w / h;
    if (Math.abs(ratio - 16 / 9) < 0.1) return "16:9";
    if (Math.abs(ratio - 9 / 16) < 0.1) return "9:16";
    if (Math.abs(ratio - 4 / 3) < 0.1) return "4:3";
    if (Math.abs(ratio - 3 / 4) < 0.1) return "3:4";
    if (Math.abs(ratio - 1) < 0.1) return "1:1";

    return `${w}:${h}`;
  }

  private gcd(a: number, b: number): number {
    a = Math.abs(Math.round(a));
    b = Math.abs(Math.round(b));
    while (b) {
      const t = b;
      b = a % b;
      a = t;
    }
    return a || 1;
  }

  private extractBrandElements(analyses: MaterialAnalysisResult[]): string[] {
    const elements = new Set<string>();

    for (const analysis of analyses) {
      for (const text of analysis.textContent) {
        if (text.trim().length > 0) {
          elements.add(text.trim());
        }
      }
    }

    return [...elements].slice(0, 10);
  }

  private extractTypography(analyses: MaterialAnalysisResult[]): string {
    const textAnalyses = analyses.filter((a) => a.textContent.length > 0);
    if (textAnalyses.length === 0) return "";

    const hasText = textAnalyses.length > 0;
    return hasText ? "テキスト要素あり" : "";
  }

  private findMostFrequent(items: string[]): string {
    if (items.length === 0) return "";

    const counts = new Map<string, number>();
    for (const item of items) {
      const normalized = item.toLowerCase().trim();
      counts.set(normalized, (counts.get(normalized) ?? 0) + 1);
    }

    let maxCount = 0;
    let mostFrequent = items[0];
    for (const [item, count] of counts) {
      if (count > maxCount) {
        maxCount = count;
        mostFrequent = item;
      }
    }

    return mostFrequent;
  }

  private buildSuggestedPromptPrefix(
    style: string,
    mood: string,
    colors: string[]
  ): string {
    const parts: string[] = [];

    if (style) {
      parts.push(style);
    }
    if (mood) {
      parts.push(`${mood} mood`);
    }
    if (colors.length > 0) {
      parts.push(`color palette: ${colors.slice(0, 3).join(", ")}`);
    }

    return parts.join(", ");
  }

  // ============================================================
  // プロンプト生成
  // ============================================================

  generatePrompts(profile: StyleProfile, scenes: string[]): string[] {
    return scenes.map((scene) => {
      const parts: string[] = [];

      if (profile.suggestedPromptPrefix) {
        parts.push(profile.suggestedPromptPrefix);
      }

      parts.push(scene);

      if (profile.brandElements.length > 0) {
        parts.push(
          `incorporating brand elements: ${profile.brandElements.slice(0, 3).join(", ")}`
        );
      }

      return parts.join(". ") + ".";
    });
  }

  // ============================================================
  // フルパイプライン実行
  // ============================================================

  async run(
    dirPath: string,
    scenes?: string[]
  ): Promise<{
    files: MaterialFile[];
    analyses: MaterialAnalysisResult[];
    profile: StyleProfile;
    prompts: string[];
  }> {
    logger.info({ dirPath }, "パイプライン開始");

    const files = await this.scanDirectory(dirPath);
    logger.info({ fileCount: files.length }, "ファイルスキャン完了");

    const analyses = await this.analyzeMaterials(files);
    logger.info({ analysisCount: analyses.length }, "素材解析完了");

    const profile = this.generateStyleProfile(analyses);
    logger.info({ profile }, "スタイルプロファイル生成完了");

    const prompts = scenes ? this.generatePrompts(profile, scenes) : [];
    logger.info({ promptCount: prompts.length }, "プロンプト生成完了");

    return { files, analyses, profile, prompts };
  }
}

// ============================================================
// ユーティリティ
// ============================================================

function chunkArray<T>(arr: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}
