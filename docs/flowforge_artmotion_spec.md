# ArtMotion Forge — 仕様書 (Obsidian正本)

> FlowForge SDK の ArtMotion Forge モジュール仕様。
> イラスト生成 → アニメーション化パイプラインを提供する。

## 概要

ArtMotion Forge は、Imagen 3 / Gemini Flash でイラストを生成し、
Veo 3.1 で高品質アニメーション動画に変換する統合パイプラインである。

## アーキテクチャ

```
┌─────────────────────────────────────────────────┐
│                ArtMotionForge                    │
│                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │ ImageGen  │──▶│ VeoClient│──▶│ Result Cache │ │
│  │ Client    │   │          │   │ (LRU)        │ │
│  └──────────┘   └──────────┘   └──────────────┘ │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ BatchProcessor (並列度制御)               │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## 主要インターフェース

### ArtMotionForgeOptions
| フィールド | 型 | 説明 |
|---|---|---|
| apiKey | string? | Gemini API キー (env fallback) |
| defaultImageModel | ImageModel? | デフォルト画像モデル |
| defaultVideoModel | VeoModel? | デフォルト動画モデル |
| cacheCapacity | number? | キャッシュ容量 (default: 50) |

### ArtMotionGenerateOptions
| フィールド | 型 | 説明 |
|---|---|---|
| prompt | string | 生成プロンプト |
| style | ArtMotionStyle? | スタイル指定 |
| aspectRatio | string? | アスペクト比 |
| resolution | VeoResolution? | 解像度 (720p/1080p/4k) |
| imageModel | ImageModel? | 画像生成モデル |
| videoModel | VeoModel? | 動画生成モデル |
| negativePrompt | string? | ネガティブプロンプト |
| referenceImages | VeoReferenceImage[]? | 参照画像 |
| skipAnimation | boolean? | アニメーション化スキップ |
| signal | AbortSignal? | キャンセルシグナル |
| onProgress | ProgressCallback? | 進捗コールバック |

### ArtMotionStyle
| 値 | 説明 |
|---|---|
| "illustration" | イラスト調 |
| "watercolor" | 水彩画調 |
| "anime" | アニメ調 |
| "photorealistic" | 写実的 |
| "flat_design" | フラットデザイン |
| "custom" | カスタムスタイル |

### ArtMotionResult
| フィールド | 型 | 説明 |
|---|---|---|
| status | "completed" / "partial" / "failed" | ステータス |
| illustration | GeneratedImage? | 生成イラスト |
| animation | VeoGenerationResult? | 動画結果 |
| prompt | string | 使用プロンプト |
| cached | boolean | キャッシュヒットか |
| durationMs | number | 処理時間 |
| error | string? | エラーメッセージ |

## Draft モード

Draft モードでは、高速・低コストな生成を行う:
- 画像: NanoBanana (gemini-2.5-flash-image)
- 動画: Veo 3.1 Fast @ 720p

Production モードでは:
- 画像: Imagen 3 (imagen-3.0-generate-002)
- 動画: Veo 3.1 @ 1080p

## エラーリカバリ

1. 画像生成失敗 → フォールバックモデルで再試行
   - Imagen 3 失敗 → NanoBanana で再試行
   - NanoBanana 失敗 → エラー返却
2. 動画生成失敗 → イラストのみ返却 (status: "partial")
3. 全API呼び出しに withRetry() 適用

## キャッシュ機構

- LRUCache<string, ArtMotionResult> を使用
- キャッシュキー: prompt + style + aspectRatio + resolution のハッシュ
- キャッシュ容量: デフォルト 50 エントリ
- キャッシュヒット時は即座にコピーを返却

## バッチ生成

- generateBatch() で複数リクエストを一括処理
- 並列度 (concurrency) を制御可能
- StoryboardPipeline との連携対応
- 各リクエストの進捗を個別にコールバック

## AbortSignal 対応

- generate() / generateBatch() で AbortSignal を受け取り
- キャンセル時は進行中の API 呼び出しを中断
- キャンセル済みリクエストは status: "failed" で返却
