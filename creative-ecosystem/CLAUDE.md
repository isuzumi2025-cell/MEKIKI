# ICC — Integrated Creative Ecosystem

**Version**: 0.1.0
**Last Updated**: 2026-02-28
**Parent Project**: MEKIKI Proofing System (../CLAUDE.md)

---

## アーキテクチャ概要

```
creative-ecosystem/
├── apps/
│   ├── frontend/          React 19 + Vite + Tailwind v4  :5173
│   ├── backend/           FastAPI Gateway                :8000
│   └── flowforge-server/  Express sidecar               :3001
├── packages/
│   ├── ai-client/         TS: Gemini/Claude/OpenAI/Grok
│   ├── ai-client-python/  Py: 同上
│   ├── ui-components/     共有 React コンポーネント
│   └── rag-engine/        RAG エンジン（Phase 4）
└── domain/
    ├── mekiki-engine/     ⛔ READ-ONLY (../OCR/app/core/)
    └── mekiki-ocr/        ⛔ READ-ONLY (../OCR/app/sdk/)
```

---

## 🚨 重要制約

### MEKIKI Engine は変更禁止

`domain/mekiki-engine/` は OCR 精度に直結します。
- ❌ `../OCR/app/core/engine_cloud.py` を変更しない
- ❌ `../OCR/app/core/sync_matcher.py` を変更しない
- ✅ `apps/backend/app/routers/mekiki.py` 経由で REST API のみ追加

### ID 整合性（W-XXX / P-XXX）

- `SyncPair.web_id` / `pdf_id` 形式: `W-001`, `P-001`
- 変更禁止: `area_code` のフォーマット
- 詳細: `../CLAUDE.md` の Pitfall #1 参照

### クラスタリング設定

- `overlap_ratio > 0.5` 固定（0.4 に緩めない）
- 詳細: `../CLAUDE.md` の Pitfall #3 参照

---

## 起動方法

```bash
# 全サービス同時起動 (Turborepo)
cd creative-ecosystem
pnpm install
pnpm dev

# 個別起動
pnpm dev:frontend    # :5173
pnpm dev:backend     # :8000  (python: cd apps/backend && python run.py)
pnpm dev:flowforge   # :3001
```

---

## API エンドポイント

| エンドポイント | 説明 |
|---|---|
| `GET  /health` | Gateway ヘルスチェック |
| `POST /api/v1/mekiki/ocr` | OCR 実行 |
| `POST /api/v1/storyboard/plan` | ストーリーボード企画生成 |
| `POST /api/v1/storyboard/generate` | FlowForge 動画生成 |
| `GET  /api/v1/vault/search` | Vault RAG 検索 |
| `POST /api/v1/sitemap/jobs` | サイトクロール開始 |

---

## Phase 進捗

| Phase | 内容 | 状態 |
|---|---|---|
| 0 | モノレポ基盤 | ✅ 完了 |
| 1 | 共有AIクライアント | ✅ 完了 |
| 2 | 統合フロントエンド | ✅ 完了 |
| 3 | FastAPI Gateway + ストーリーボードAPI | ✅ 完了 |
| 4 | RAGエンジン & Vault統合 | 🔲 未着手 |
| 5 | Marketing Analytics | 🔲 未着手 |
| 6 | イベントバス & ワークフロー | 🔲 未着手 |

---

## 環境変数

`.env` ファイルを `apps/backend/` に作成してください（`.env.example` 参照）。
