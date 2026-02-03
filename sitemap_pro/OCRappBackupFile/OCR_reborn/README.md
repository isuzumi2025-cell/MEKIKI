# 🔬 Web vs PDF 整合性検証システム

既存の高精度OCRツールの「脳」（高度なクラスタリングアルゴリズム）をWebスクレイピングに応用し、WebサイトとPDFの整合性を検証するシステムです。

## ✨ 主要機能

### 1. 🧠 高度な領域検出エンジン
既存OCRツールで実証された2つのコアアルゴリズムを移植:
- **近接クラスタリング (Proximity Clustering)**: 縦方向に近い文字ブロックを統合
- **動的密度クラスタリング (Dynamic Density Clustering)**: 孤立した小領域を自動吸収

### 2. 🌐 Webクローラー
- PCビューポート (1920x1080) での高品質スクリーンショット
- Basic認証対応
- Cookie保存/復元
- 完全ロード待機 (networkidle + sleep)

### 3. 📄 PDF高解像度ローダー
- PyMuPDFによる高速・高品質変換
- DPI調整可能（デフォルト: 300）
- OCR最適化処理

### 4. ✏️ 編集可能Canvas UI
- ドラッグで新規エリア作成
- クリックでエリア選択
- 右クリックでエリア削除
- リアルタイムテキスト抽出

### 5. 🔍 Web vs PDF 比較エンジン
- テキスト差分検出 (difflib)
- 類似度計算 (0.0 - 1.0)
- マッチング/ミスマッチ/専用エリアの分類
- HTML/CSV形式でのレポート出力

### 6. 📊 Googleスプレッドシート同期
- エリア情報のリアルタイム反映
- 既存シートへの上書き対応
- 権限共有機能
- タイムスタンプ付き

## 🚀 セットアップ

### 必要要件
- Python 3.9+
- Google Cloud Platform アカウント（Vision API / Sheets API用）

### インストール

```bash
# 1. リポジトリのクローン
git clone <repository_url>
cd OCR_reborn

# 2. 依存関係のインストール
pip install -r requirements.txt

# 3. Playwrightのブラウザインストール
playwright install chromium

# 4. Google認証情報の配置
# service_account.json を project_root に配置
```

### Google Cloud 設定

1. **Vision API の有効化**
   - Google Cloud Console で Vision API を有効化
   - サービスアカウントを作成し、JSONキーをダウンロード

2. **Sheets API の有効化**
   - Sheets API と Drive API を有効化
   - 同じサービスアカウントに権限を付与

3. **認証ファイルの配置**
   ```bash
   # ダウンロードしたJSONファイルを service_account.json にリネーム
   mv path/to/your-key.json service_account.json
   ```

## 📖 使い方

### 起動

```bash
python main.py
```

### 基本ワークフロー

1. **Web画像の読み込み**
   - 「🌐 Web読込」ボタンをクリック
   - URLを入力（Basic認証が必要な場合はID/PASSも入力）
   - スクリーンショットが自動撮影される

2. **PDF画像の読み込み**
   - 「📄 PDF読込」ボタンをクリック
   - PDFファイルを選択
   - 高解像度画像に自動変換される

3. **AI解析実行**
   - 「▶ AI解析実行」ボタンをクリック
   - 領域が自動検出される
   - 各タブで手動編集も可能

4. **比較実行**
   - 「🔍 比較実行」ボタンをクリック
   - Web vs PDF の差分が可視化される
   - サマリーが表示される

5. **エクスポート**
   - 「📊 Sheets出力」: Googleスプレッドシートに出力
   - 「💾 CSV出力」: CSV形式で保存

## 🏗️ アーキテクチャ

```
project_root/
├── main.py                          # メインアプリケーション
├── app/
│   ├── core/
│   │   ├── engine_clustering.py    # クラスタリングエンジン（コアロジック）
│   │   ├── engine_spreadsheet.py   # スプレッドシート同期
│   │   ├── crawler.py              # Webクローラー
│   │   ├── pdf_loader.py           # PDF高解像度ローダー
│   │   └── comparator.py           # 比較エンジン
│   └── gui/
│       ├── canvas_editor.py        # Canvas編集UI
│       └── macro_view.py           # 全体比較ビュー
├── requirements.txt
└── README.md
```

## 🎯 コアアルゴリズム詳細

### 近接クラスタリング

```python
# 判定条件:
- 横方向の重なり率 > 70% または 左端の差 < 20px
- 縦方向の間隔 < フォントサイズ × 2.5（最小80px）
- フォントサイズの差が2倍以内
- 横方向の間隔 < 10px
```

### 動的密度クラスタリング

```python
# 孤立判定:
- 面積が平均の10%以下
- または、テキスト文字数が3文字未満

# 吸収条件:
- 最も近い親領域との距離が200px以内
```

## 📊 出力形式

### Googleスプレッドシート

| Area ID | Position | Extracted Text | Human Verify | Correction | Status | Timestamp |
|---------|----------|----------------|--------------|------------|--------|-----------|
| Area 1  | (x0, y0, x1, y1) | テキスト内容 | | | Pending | 2024-01-01 12:00:00 |

### CSV

```csv
Area ID,Status,Similarity,Web Text,PDF Text
Area 1,match,98.5%,同じテキスト,同じテキスト
Area 2,mismatch,75.2%,異なるテキスト,違うテキスト
```

## 🔧 カスタマイズ

### クローラー設定

```python
# app/core/crawler.py
crawler = WebCrawler(
    viewport_width=1920,   # ビューポート幅
    viewport_height=1080   # ビューポート高さ
)
```

### PDF解像度設定

```python
# app/core/pdf_loader.py
pdf_loader = PDFLoader(
    dpi=300  # 解像度（デフォルト: 300）
)
```

### クラスタリング閾値

```python
# app/core/engine_clustering.py
# _vertical_stack_clustering 内のパラメータを調整
overlap_ratio > 0.7      # 重なり率
threshold_y = base_size * 2.5  # 縦間隔
```

## 🐛 トラブルシューティング

### Playwright エラー
```bash
# ブラウザを再インストール
playwright install --force chromium
```

### Google認証エラー
```bash
# 環境変数を設定（オプション）
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service_account.json"
```

### OCR精度が低い
- PDF/画像の解像度を上げる (DPI: 300 → 400)
- 画像前処理を強化 (`ImageOptimizer.optimize_for_ocr`)

## 📝 ライセンス

MIT License

## 🙏 謝辞

このシステムは、既存の高精度OCRツールのコアアルゴリズムを基盤としています。
特に、近接クラスタリングと動的密度クラスタリングのロジックは、
実運用で実証された精度の高いアプローチを採用しています。

## 📮 お問い合わせ

問題や質問がある場合は、Issueを作成してください。

