# 変更履歴

## [0.1.0] - 2025-01-XX

### 追加
- Phase 0: プロジェクト初期化
  - 仕様書（`docs/requirements.md`）の作成
  - 設定ファイル雛形（`configs/pipeline.yaml.example`, `configs/connectors.yaml.example`）
  - Pythonプロジェクト骨格の作成
  - CLIエントリーポイントの実装

- Phase 1: コア機能の実装
  - ファイル読み込み（画像/PDF）
  - Google Cloud Vision API によるOCR実行
  - OCR要素の正規化（ソート規則固定）
  - 段落クラスタリング（近接×整列×サイズ）
  - ロール推定（headline/body/caption/price/legal/other）
  - 日本語チェック（ルールベース）
  - 正規化JSON生成・保存
  - デバッグオーバーレイ画像生成
  - ライブラリ構造の自動生成

### 技術スタック
- Python 3.10+
- Google Cloud Vision API
- Pillow (画像処理)
- pdf2image (PDF処理)
- PyYAML (設定ファイル)
- Click (CLI)

### 次のステップ
- Phase 2: 比較・同期率・出力機能
- Phase 3: Webスクレイピング・認証対応
- Phase 4: 拡張機能（LLM評価、絵コンテ生成など）



