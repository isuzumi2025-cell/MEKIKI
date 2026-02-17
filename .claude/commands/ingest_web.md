# Command: ingest_web

**Purpose**: Web OCR → web_paragraphs生成

## Trigger

ユーザーが「Web URLからテキスト抽出」を指示したとき、またはOCR実行ボタンを押したとき。

## Input Schema

```json
{
  "url": "string (required)",
  "output_format": "json | internal (optional, default: internal)",
  "pages": "int (optional, default: all)"
}
```

**例**:
```json
{
  "url": "https://example.com/ad-page",
  "output_format": "json",
  "pages": 10
}
```

## Output Schema

```json
{
  "web_paragraphs": [
    {
      "area_code": "W-001",
      "text": "サンプルテキスト...",
      "bbox": [x1, y1, x2, y2],
      "page": 1,
      "confidence": 0.95
    }
  ],
  "metadata": {
    "total_paragraphs": 50,
    "total_pages": 3,
    "image_path": "exports/web_stitched_20260122.png"
  }
}
```

## Execution Steps

1. **Playwright起動**: `enhanced_scraper.py` でWebページをキャプチャ
   - 固定ヘッダー除去（`position: fixed` 要素を一時非表示）
   - スクロールキャプチャ（`scroll_delay=1.0s`）
   - 画像保存（`exports/web_page_{i}.png`）

2. **縦連結**: 複数ページを縦に連結
   - `stitch_images_vertically()`
   - 各ページの `y_offset` 累積計算

3. **Vision API実行**: `engine_cloud.py` でOCR
   - Google Cloud Vision API呼び出し
   - テキスト + bbox取得

4. **クラスタリング**: 近接テキストをパラグラフに統合
   - パラメータ: `overlap>0.6`, `left_diff<30`, `gap_x>15` （厳格設定）
   - ⚠️ 禁止: `overlap 0.4`, `gap_y 80` （緩和設定）

5. **ID付与**: `W-{3桁}` 形式で `area_code` 生成
   - `W-001`, `W-002`, ...

6. **座標変換**: y_offset加算
   - `bbox = (x1, y1+y_offset, x2, y2+y_offset)`

7. **正規化**: 日本語テキスト正規化
   - 日本語文字間のスペース削除
   - `_normalize_japanese_text()`

## Acceptance Criteria

- ✅ **AC-INGEST-WEB-1**: 全ページがキャプチャされている（固定ヘッダー重複なし）
- ✅ **AC-INGEST-WEB-2**: area_code が `W-001` から連番で付与されている
- ✅ **AC-INGEST-WEB-3**: area_code に重複がない
- ✅ **AC-INGEST-WEB-4**: bbox の y座標に y_offset が正しく加算されている
- ✅ **AC-INGEST-WEB-5**: クラスタリングパラメータが Match:70設定（厳格）を使用
- ✅ **AC-INGEST-WEB-6**: 画像ファイルが `exports/` に保存されている

## Failure Modes & Error Handling

| エラー分類 | 原因例 | 対処 |
|:---|:---|:---|
| **NETWORK_ERROR** | URL到達不可、タイムアウト | リトライ（最大3回）、タイムアウト延長 |
| **VISION_API_ERROR** | API認証失敗、quota超過 | `service_account.json` 確認、quota確認 |
| **CLUSTERING_ERROR** | 緩和パラメータ使用 | `CLAUDE.md` の正しい設定に復元 |
| **ID_DUPLICATE** | area_code重複 | カウンター初期化確認、ログ出力 |
| **COORDINATE_ERROR** | y_offset未加算 | stitching処理のoffset計算確認 |

## Validation Commands

```bash
# ID整合性チェック
/audit-ids

# 座標監査
/audit-coords

# クラスタリング設定確認
grep -r "overlap_ratio\|gap_x\|gap_y" OCR/app/core/engine_cloud.py
```

## Dependencies

- `app/core/enhanced_scraper.py`
- `app/core/engine_cloud.py`
- `service_account.json` (Google Cloud認証)

## Example Usage

```python
# unified_app.py 内で呼び出し
async def on_ocr_execute():
    web_paragraphs = await ingest_web(
        url="https://example.com",
        output_format="internal"
    )
    # → web_paragraphs: List[ParaParagraph]
```

---

**Next Command**: `ingest_pdf.md`
