# Visual Sitemap Generator

スクリーンショット付きのサイトマップを生成するアプリケーション。広告LP群の高速クロールと監査に最適化。

## 特徴

- 🚀 **BFSクロール** - 浅い階層優先で全体像を素早く把握
- 📸 **フルページスクショ** - PC/SP両対応
- 🔍 **簡易SEO監査** - 404/500、title/h1欠落、OGP欠落等を検出
- 🌳 **インタラクティブツリー** - Cytoscape.js でクリック可能なサイトマップ
- 🔐 **認証対応** - Basic認証、フォームログイン、手動介入（2FA）
- 📊 **エクスポート** - HTML/CSV/JSON

## クイックスタート

### 1. 環境構築

```bash
cd sitemap_app

# 仮想環境作成
python -m venv .venv

# 有効化 (Windows)
.venv\Scripts\activate
# 有効化 (Mac/Linux)
# source .venv/bin/activate

# 依存パッケージインストール
pip install -r requirements.txt

# Playwright ブラウザインストール
playwright install chromium
```

### 2. サーバー起動

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. ダッシュボードにアクセス

ブラウザで http://localhost:8000 を開く

## 使い方

### パターン1: 認証なしのサイト

1. ダッシュボードで「プロファイル」タブを開く
2. 「新規プロファイル」をクリック
3. 名前と対象URLを入力
4. 「作成」
5. 「新規クロール」タブでプロファイルを選択して開始

### パターン2: Basic認証サイト

```json
// プロファイル作成時の auth_config
{
    "mode": "basic",
    "user": "your_username",
    "pass": "your_password"
}
```

### パターン3: フォームログイン（ステージング環境等）

```json
{
    "mode": "form",
    "login_url": "https://staging.example.com/login",
    "username_selector": "#email",
    "password_selector": "#password",
    "submit_selector": "button[type=submit]",
    "user": "test@example.com",
    "pass": "password123",
    "success_indicator": ".dashboard"
}
```

### パターン4: 手動介入（2FA必須サイト）

```json
{
    "mode": "manual",
    "login_url": "https://example.com/login",
    "pause_message": "2FAコードを入力してログインを完了してください"
}
```

## API エンドポイント

| Method | Path | 説明 |
|--------|------|------|
| POST | `/api/v1/profiles` | プロファイル作成 |
| GET | `/api/v1/profiles` | プロファイル一覧 |
| GET | `/api/v1/profiles/{id}` | プロファイル詳細 |
| PUT | `/api/v1/profiles/{id}` | プロファイル更新 |
| DELETE | `/api/v1/profiles/{id}` | プロファイル削除 |
| POST | `/api/v1/jobs` | クロールジョブ開始 |
| GET | `/api/v1/jobs` | ジョブ一覧 |
| GET | `/api/v1/jobs/{id}` | ジョブステータス |
| POST | `/api/v1/jobs/{id}/stop` | ジョブ停止 |
| GET | `/api/v1/jobs/{id}/results` | 結果詳細 |
| GET | `/api/v1/jobs/{id}/export/html` | HTMLサイトマップ |
| GET | `/api/v1/jobs/{id}/export/csv` | CSVエクスポート |
| GET | `/api/v1/jobs/{id}/export/json` | JSONエクスポート |
| GET | `/api/v1/jobs/{id}/audit` | 監査レポート |

## 設定値

`app/core/config.py` で変更可能：

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `DEFAULT_MAX_PAGES` | 50 | 最大クロールページ数 |
| `DEFAULT_MAX_DEPTH` | 3 | 最大クロール深さ |
| `DEFAULT_MAX_TIME_SECONDS` | 1800 | 最大クロール時間（30分） |
| `DEFAULT_CONCURRENT_LIMIT` | 3 | 同時並列数 |
| `DEFAULT_TIMEOUT` | 30000 | ページタイムアウト (ms) |
| `PC_VIEWPORT_WIDTH` | 1920 | PCスクショ幅 |
| `SP_VIEWPORT_WIDTH` | 390 | SPスクショ幅 |

## テスト実行

```bash
# ユニットテスト
pytest tests/ -v

# 特定のテストファイル
pytest tests/test_parser.py -v
```

## ディレクトリ構成

```
sitemap_app/
├── app/
│   ├── api/endpoints.py     # REST API
│   ├── core/
│   │   ├── config.py        # 設定
│   │   ├── crawler.py       # BFSクローラー
│   │   ├── engine.py        # Playwright/httpxエンジン
│   │   ├── parser.py        # URL正規化
│   │   ├── auditor.py       # 監査チェック
│   │   ├── exporter.py      # エクスポート
│   │   ├── auth.py          # 認証ハンドラ
│   │   ├── robots.py        # robots.txt
│   │   └── interfaces.py    # 拡張インターフェース
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   ├── schemas/schemas.py
│   └── static/index.html    # ダッシュボードUI
├── tests/
├── outputs/                  # スクショ保存先
├── requirements.txt
└── README.md
```

## 大規模サイト対応（アドオン）

50ページを超える大規模サイトには以下の拡張が必要：

- **ジョブキュー**: Redis + Celery/RQ
- **データベース**: SQLite → PostgreSQL
- **差分クロール**: content_hash による変更検出
- **sitemap.xml 取込**: シードURL一括投入

拡張ポイントは `app/core/interfaces.py` で定義済み。

## トラブルシューティング

### Playwright がインストールできない

```bash
# 管理者権限で実行
playwright install --with-deps chromium
```

### スクショが真っ白

networkidle待機がタイムアウトしている可能性。`config.py` で `DEFAULT_WAIT_UNTIL` を `"domcontentloaded"` に変更。

### メモリ不足

`CONCURRENT_LIMIT` を 1 に下げる。

## ライセンス

MIT
