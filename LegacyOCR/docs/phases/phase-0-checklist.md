# Phase 0 完了チェックリスト

## Phase 1へ進む前の確認事項

### ✅ プロジェクト構造

- [x] `docs/requirements.md` が存在し、仕様が明確
- [x] `docs/phases/phase-0.md`, `phase-1.md` が存在
- [x] `configs/pipeline.yaml.example`, `connectors.yaml.example` が存在
- [x] Pythonプロジェクトとして `python -m app --help` が動作
- [x] `tests/` ディレクトリが存在し、テスト実行可能
- [x] `.env.example` が存在し、必要な環境変数が列挙されている

### ✅ 依存関係

- [x] `requirements.txt` に必要なパッケージが記載されている
- [x] `pyproject.toml` が存在し、プロジェクトメタデータが定義されている

### ✅ CLIの骨格

- [x] `app/cli.py` が存在し、`ingest` と `fetch_web` コマンドが定義されている
- [x] `app/__main__.py` が存在し、`python -m app` で実行可能
- [x] `app/ingest.py` のプレースホルダーが存在

### ✅ 設定ファイル

- [x] `configs/pipeline.yaml.example` が存在し、OCR/前処理/段落/日本語チェックの設定が定義されている
- [x] `configs/connectors.yaml.example` が存在し、Web取得の設定が定義されている（Phase 3用）

### ✅ ドキュメント

- [x] `README.md` が存在し、セットアップ手順が記載されている
- [x] 仕様書が `docs/requirements.md` に反映されている

### ✅ その他

- [x] `.gitignore` が存在し、適切なファイルが除外されている
- [x] テスト用のプレースホルダーが `tests/test_ingest.py` に存在

## Phase 1実装前の準備

### 必要な環境設定

1. **OCR APIキーの準備**
   - Google Cloud Vision API: サービスアカウントキーまたはAPIキー
   - （オプション）Azure Computer Vision: エンドポイントとAPIキー
   - （フォールバック）Tesseract: システムにインストール

2. **依存パッケージのインストール**
   ```bash
   pip install -r requirements.txt
   ```

3. **設定ファイルの準備**
   ```bash
   cp configs/pipeline.yaml.example configs/pipeline.yaml
   # pipeline.yaml を編集（必要に応じて）
   ```

4. **環境変数の設定**
   ```bash
   cp .env.example .env
   # .env を編集してAPIキーなどを設定
   ```

### Phase 1実装の優先順位

1. **最小E2E実装**
   - 画像ファイルの読み込み
   - OCR実行（Google Cloud Vision API）
   - OCR生JSONの保存
   - 正規化JSONの最小スキーマで保存

2. **段落クラスタリング**
   - OCR要素の座標ソート
   - 近接×整列×サイズでのクラスタリング
   - paragraph_id の安定採番

3. **ロール推定**
   - ヒューリスティックベースのロール推定
   - headline/body/caption/price/legal/other

4. **日本語チェック**
   - ルールベースチェックの実装
   - grammar_issues / suggestions の生成

5. **デバッグ出力**
   - オーバーレイ画像の生成
   - ログ出力の整備

## 次のステップ

Phase 1の実装を開始する準備が整いました。

1. `docs/phases/phase-1.md` を参照
2. 最小E2E実装から開始
3. 段階的に機能を追加
