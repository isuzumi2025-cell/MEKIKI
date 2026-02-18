/**
 * subject.ts
 *
 * SubjectRegistry で使用する型定義。
 */

export interface Subject {
  id: string;
  name: string;
  description: string;
  keyFeatures: string[];
  sourceJobId?: string;
  thumbnail?: string;
  carryover: boolean;
  createdAt: Date;
}

export interface SubjectRegistryOptions {
  apiKey?: string;
  similarityThreshold?: number;
}

export interface GenerationJobResult {
  jobId: string;
  outputUrl: string;
  imageBytes?: string;
  imageMimeType?: string;
  metadata?: Record<string, unknown>;
}

export interface SimilarityMatch {
  subject: Subject;
  score: number;
}

export interface ExtractedSubjectData {
  index: number;
  name: string;
  description: string;
  keyFeatures: string[];
}
