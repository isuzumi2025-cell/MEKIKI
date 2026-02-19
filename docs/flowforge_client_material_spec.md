# Client Material Pipeline — 仕様書 (Obsidian正本)

> FlowForge SDK の Client Material Pipeline モジュール仕様。
> クライアント素材の自動解析・スタイルプロファイル生成を提供する。

## 概要

Client Material Pipeline は、クライアントから提供された素材
(画像、PDF、動画) を自動解析し、スタイルプロファイルとプロンプトを生成する。

## アーキテクチャ

```
┌───────────────────────────────────────────────────┐
│            ClientMaterialPipeline                  │
│                                                    │
│  ┌────────────┐  ┌───────────────┐  ┌──────────┐  │
│  │ Directory   │─▶│ Material      │─▶│ Style    │  │
│  │ Scanner     │  │ Analyzer      │  │ Profiler │  │
│  └────────────┘  │ (Gemini       │  └──────────┘  │
│                  │  Vision API)   │                 │
│  ┌────────────┐  └───────────────┘  ┌──────────┐  │
│  │ PDF        │                     │ Prompt   │  │
│  │ Extractor  │                     │ Generator│  │
│  └────────────┘                     └──────────┘  │
│  ┌────────────┐                                    │
│  │ Video      │                                    │
│  │ Thumbnail  │                                    │
│  └────────────┘                                    │
└───────────────────────────────────────────────────┘
```

## 主要インターフェース

### ClientMaterialPipelineOptions
| フィールド | 型 | 説明 |
|---|---|---|
| apiKey | string? | Gemini API キー (env fallback) |
| supportedImageExts | string[]? | 対応画像拡張子 |
| supportedVideoExts | string[]? | 対応動画拡張子 |
| maxFileSizeMB | number? | 最大ファイルサイズ (default: 50) |
| concurrency | number? | 並列解析数 (default: 3) |

### MaterialFile
| フィールド | 型 | 説明 |
|---|---|---|
| path | string | ファイルパス |
| type | MaterialType | ファイル種別 |
| name | string | ファイル名 |
| sizeBytes | number | ファイルサイズ |
| mimeType | string | MIME タイプ |

### MaterialType
| 値 | 説明 |
|---|---|
| "image" | 画像ファイル (jpg, png, webp, gif, bmp, tiff) |
| "pdf" | PDF ファイル |
| "video" | 動画ファイル (mp4, mov, avi, webm) |
| "unknown" | 未対応形式 |

### MaterialAnalysisResult
| フィールド | 型 | 説明 |
|---|---|---|
| file | MaterialFile | 解析対象ファイル |
| description | string | シーン記述 |
| dominantColors | string[] | 主要色 |
| style | string | スタイル記述 |
| mood | string | ムード |
| objects | string[] | 検出オブジェクト |
| textContent | string[] | 検出テキスト |
| aspectRatio | { width: number; height: number } | アスペクト比 |
| quality | "low" / "medium" / "high" | 品質評価 |

### StyleProfile
| フィールド | 型 | 説明 |
|---|---|---|
| dominantColors | string[] | 主要色パレット |
| dominantStyle | string | 支配的スタイル |
| dominantMood | string | 支配的ムード |
| dominantAspectRatio | string | 最頻アスペクト比 |
| typography | string? | タイポグラフィ傾向 |
| brandElements | string[] | ブランド要素 |
| suggestedPromptPrefix | string | 推奨プロンプト接頭辞 |

## ディレクトリスキャン

### scanDirectory(dirPath: string)
- 指定ディレクトリを再帰的にスキャンし、素材ファイルを列挙
- エラーハンドリング:
  - 権限エラー (EACCES): スキップしてログ出力
  - シンボリックリンク: 循環参照チェック付きで追跡
  - 不正パス: バリデーション + エラーメッセージ
  - 空ディレクトリ: 空配列を返却
- ファイルサイズ制限チェック
- 隠しファイル (`.` prefix) はスキップ

## 素材解析

### analyzeMaterials(files: MaterialFile[])
- Gemini Vision API で画像を解析
- PDF: ページ抽出 → 画像変換 → 個別解析
- 動画: サムネイル抽出 → 解析
- withRetry() で API 呼び出しをラップ
- 並列度制御 (concurrency オプション)

## StyleProfile 生成

### generateStyleProfile(analyses: MaterialAnalysisResult[])
- 全解析結果を統合し、スタイルプロファイルを生成
- dominantAspectRatio: 画像メタデータから最頻値を自動判定
- dominantColors: 出現頻度上位の色を抽出
- suggestedPromptPrefix: スタイル+ムードからプロンプト接頭辞を生成

## プロンプト生成

### generatePrompts(profile: StyleProfile, scenes: string[])
- StyleProfile に基づいてシーンごとのプロンプトを生成
- ブランド要素をプロンプトに反映
- ArtMotion Forge との連携を想定した形式で出力
