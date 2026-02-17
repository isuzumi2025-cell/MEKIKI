# OCR Scanner

広告・チラシ・PDF・Webページから日本語文言を高精度に抽出し、段落単位で構造化するツール。

## 機能

### Phase 1（コア）: 実装予定

- 画像/PDFからOCR実行
- 段落単位での構造化
- 日本語チェック（ルールベース）
- 正規化JSON出力

### Phase 2（比較）: 将来実装

- A/B差分検出
- 同期率算出
- CSV/Excel/Sheets出力

### Phase 3（Web）: 将来実装

- Webページ取得
- 認証対応（Basic/フォーム/パスワード入力型）
- スクリーンショット→OCR

### Phase 4（拡張）: 将来実装

- LLM評価コメント
- 絵コンテ生成
- アナリティクス連携

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` を `.env` にコピーして、必要な値を設定してください。

```bash
cp .env.example .env
# .env を編集
```

### 3. 設定ファイルの準備

```bash
cp configs/pipeline.yaml.example configs/pipeline.yaml
# pipeline.yaml を編集（必要に応じて）
```

## 使用方法

### CLI

```bash
# 画像/PDFを取り込む（Phase 1）
python -m app ingest \
  --input <file_or_dir> \
  --client <name> \
  --campaign <name> \
  [--month YYYY-MM] \
  [--preprocess-lines on/off] \
  [--debug on/off]

# Webページを取得（Phase 3 - 将来）
python -m app fetch_web \
  --connector <name> \
  --client <name> \
  --campaign <name> \
  [--month YYYY-MM]
```

## プロジェクト構造

```
/
├── app/                    # メインアプリケーション
│   ├── cli.py             # CLIエントリーポイント
│   ├── ingest.py           # Phase 1: 取り込み処理
│   ├── ocr/                # OCR関連
│   ├── pipeline/            # パイプライン処理
│   ├── japanese/            # 日本語チェック
│   └── utils/               # ユーティリティ
├── configs/                 # 設定ファイル
├── docs/                    # ドキュメント
│   ├── requirements.md
│   └── phases/
├── tests/                   # テスト
├── library/                 # 出力先（.gitignore）
└── README.md
```

## ドキュメント

- [仕様書](docs/requirements.md)
- [Phase 0: プロジェクト初期化](docs/phases/phase-0.md)
- [Phase 1: コア機能](docs/phases/phase-1.md)

## 開発

### テスト実行

```bash
pytest
```

### Phase 1への進め方

1. Phase 0のチェックリストを確認
2. `docs/phases/phase-1.md` を参照
3. E2Eが動く最小実装から開始

## ライセンス

（未定）
