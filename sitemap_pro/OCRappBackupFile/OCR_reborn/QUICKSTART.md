# 🚀 クイックスタートガイド

## 📋 前提条件

- Python 3.9 以上
- pip（パッケージマネージャー）
- Google Cloud Platform アカウント

## ⚡ 5分でセットアップ

### ステップ1: 依存関係のインストール

```bash
# 仮想環境の作成（推奨）
python -m venv venv

# 仮想環境の有効化
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt

# Playwrightブラウザのインストール
playwright install chromium
```

### ステップ2: Google Cloud 認証の設定

#### 2-1. Vision API と Sheets API の有効化

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成または選択
3. 以下のAPIを有効化:
   - Cloud Vision API
   - Google Sheets API
   - Google Drive API

#### 2-2. サービスアカウントの作成

1. 「IAMと管理」→「サービスアカウント」に移動
2. 「サービスアカウントを作成」をクリック
3. 名前を入力（例: "web-pdf-verification"）
4. 役割を付与:
   - Cloud Vision API: 「Cloud Vision API ユーザー」
   - Sheets/Drive: 「編集者」
5. 「キーを作成」→ JSON形式を選択
6. ダウンロードしたJSONファイルを `service_account.json` にリネーム
7. プロジェクトルートに配置

```
OCR_reborn/
├── service_account.json  ← ここに配置
├── main.py
└── ...
```

### ステップ3: アプリケーションの起動

```bash
python main.py
```

## 📝 基本的な使い方

### GUIモード（推奨）

1. **アプリケーションを起動**
   ```bash
   python main.py
   ```

2. **Web画像を読み込み**
   - 「🌐 Web読込」ボタンをクリック
   - URLを入力（例: https://example.com）
   - Basic認証が必要な場合はID/PASSも入力
   - 「読込実行」をクリック

3. **PDF画像を読み込み**
   - 「📄 PDF読込」ボタンをクリック
   - PDFファイルを選択

4. **AI解析を実行**
   - 「▶ AI解析実行」ボタンをクリック
   - 自動的に領域が検出される

5. **比較を実行**
   - 「🔍 比較実行」ボタンをクリック
   - 「🔍 比較」タブで結果を確認

6. **結果をエクスポート**
   - 「📊 Sheets出力」: Googleスプレッドシートに出力
   - 「💾 CSV出力」: CSVファイルとして保存

### コマンドラインモード（バッチ処理）

#### 基本的な比較

```bash
python examples/example_basic.py
```

#### 複数URLの一括処理

```bash
python examples/example_batch.py
```

#### スプレッドシート連携

```bash
python examples/example_spreadsheet.py
```

## 🔧 設定のカスタマイズ

### config.py の作成

```bash
# 設定ファイルのコピー
cp config.example.py config.py

# config.py を編集
# 例: クローラーのビューポートサイズを変更
```

```python
# config.py
CRAWLER_VIEWPORT_WIDTH = 1920
CRAWLER_VIEWPORT_HEIGHT = 1080
PDF_DPI = 400  # PDF解像度を上げる
```

## 📚 よくある質問

### Q1: `playwright install` でエラーが出る

```bash
# Chromiumだけをインストール
playwright install chromium

# 全てのブラウザをインストール（時間がかかる）
playwright install
```

### Q2: Google認証エラーが出る

**原因1: APIが有効化されていない**
- Cloud Console で Vision API, Sheets API, Drive API を有効化してください

**原因2: service_account.json のパスが間違っている**
- プロジェクトルートに配置されているか確認

**原因3: スプレッドシートの権限がない**
- スプレッドシートをサービスアカウントのメールアドレスと共有してください
  - サービスアカウントのメール: `xxx@xxx.iam.gserviceaccount.com`

### Q3: OCRの精度が低い

**解決策:**
1. PDF/画像の解像度を上げる
   ```python
   pdf_loader = PDFLoader(dpi=400)  # デフォルト: 300
   ```

2. 画像前処理を強化
   ```python
   from app.core.pdf_loader import ImageOptimizer
   optimized = ImageOptimizer.optimize_for_ocr(image, upscale=True)
   ```

### Q4: Webページが正しくロードされない

**解決策:**
1. 待機時間を増やす
   ```python
   crawler.crawl(url, output_path, wait_time=5)  # デフォルト: 2秒
   ```

2. 手動ログインモードを使う
   ```python
   crawler.interactive_login(url)
   ```

## 🎯 次のステップ

### より高度な使い方

1. **カスタムクラスタリングパラメータ**
   - `app/core/engine_clustering.py` のパラメータを調整

2. **独自の比較ロジック**
   - `app/core/comparator.py` をカスタマイズ

3. **バッチ処理の自動化**
   - `examples/example_batch.py` をベースにスケジューラーと連携

4. **API化**
   - FastAPI などを使ってREST API化

### サポート

問題が解決しない場合:
1. `logs/` フォルダのログを確認
2. GitHubでIssueを作成
3. README.md の詳細ドキュメントを参照

## 🎉 成功！

セットアップが完了しました！
Web vs PDF の整合性検証を始めましょう 🚀

```bash
python main.py
```

