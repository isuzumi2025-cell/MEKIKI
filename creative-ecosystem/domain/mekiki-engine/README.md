# MEKIKI Engine (Sealed Module)

> **⛔ 変更禁止 — READ-ONLY**
>
> このモジュールは OCR 精度に直結しています。
> 内部ファイルの変更は禁止です。API ラッパーのみを追加してください。

## 参照先

実際のコードは `../../OCR/` にあります（相対パス）。

| ファイル | 責務 |
|---|---|
| `../../OCR/app/core/engine_cloud.py` | OCR クラスタリング（Match:70 設定） |
| `../../OCR/app/core/sync_matcher.py` | マッチングロジック |
| `../../OCR/app/core/paragraph_matcher.py` | パラグラフ比較 |

## API ラッパー

`apps/backend/app/routers/mekiki.py` 経由で REST API として公開されます。

```
POST /api/v1/mekiki/ocr          — OCR 実行
POST /api/v1/mekiki/match        — パラグラフマッチング
GET  /api/v1/mekiki/sync-pairs   — SyncPair 取得
POST /api/v1/mekiki/storyboard   — ストーリーボード生成
```
