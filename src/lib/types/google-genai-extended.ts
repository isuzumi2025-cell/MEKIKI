/**
 * google-genai-extended.d.ts
 *
 * @google/genai SDK の型定義を補完・再エクスポートするモジュール。
 * SDK が提供する型を FlowForge SDK 内部で統一的に利用するためのブリッジ。
 */

import type {
  GoogleGenAI,
  GenerateVideosOperation,
  GenerateVideosResponse,
  GenerateVideosParameters,
  GenerateVideosConfig,
  GeneratedVideo,
  Video,
  GenerateImagesResponse,
  GenerateImagesParameters,
  GenerateImagesConfig,
  GeneratedImage,
  Part,
  Blob as GenAIBlob,
  Image as GenAIImage,
  Models,
  Operations,
  Files,
  DownloadFileParameters,
  VideoGenerationReferenceImage,
  VideoGenerationReferenceType,
} from "@google/genai";

export type {
  GoogleGenAI,
  GenerateVideosOperation,
  GenerateVideosResponse,
  GenerateVideosParameters,
  GenerateVideosConfig,
  GeneratedVideo,
  Video,
  GenerateImagesResponse,
  GenerateImagesParameters,
  GenerateImagesConfig,
  GeneratedImage,
  Part,
  GenAIBlob,
  GenAIImage,
  Models,
  Operations,
  Files,
  DownloadFileParameters,
  VideoGenerationReferenceImage,
  VideoGenerationReferenceType,
};

/**
 * Part の inlineData フィールドにアクセスするための型ガード。
 * SDK の Part 型は inlineData?: Blob (data, mimeType) を持つ。
 */
export function hasInlineData(
  part: Part
): part is Part & { inlineData: NonNullable<Part["inlineData"]> } {
  return part.inlineData !== undefined && part.inlineData !== null;
}

/**
 * Part の inlineData から data が存在するかチェックする型ガード。
 */
export function hasInlineImageData(
  part: Part
): part is Part & {
  inlineData: { data: string; mimeType: string };
} {
  return (
    hasInlineData(part) &&
    typeof part.inlineData.data === "string" &&
    part.inlineData.data.length > 0
  );
}
