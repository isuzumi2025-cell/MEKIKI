# SKILL: ingest_web

**Version**: 1.0.0
**Phase**: Phase 1
**Priority**: 🟡 MAJOR

---

## Objective

WebページからのOCRテキスト抽出：Playwright + Google Cloud Vision API を使用し、固定ヘッダー除去・縦連結・座標変換・ID付与を正確に実行し、`web_paragraphs` を生成する。

---

## Scope

### ✅ このユニットで触って良い範囲

- `OCR/app/core/enhanced_scraper.py` - Playwright scraping
- `OCR/app/core/engine_cloud.py` - Vision API OCR（クラスタリング設定は慎重に）
- `exports/web_*.png` - Web画像出力（自動生成）
- ID生成ロジック（W-XXX形式）

### ❌ このユニットで触るな

- `OCR/app/sdk/similarity/paragraph_matcher.py` - マッチングロジック（Phase 1 Unit 2）
- `OCR/app/gui/panels/spreadsheet_panel.py` - Display logic（Phase 2）
- **クラスタリング緩和パラメータ**（overlap 0.4, gap_y 80）は絶対禁止

---

## Inputs

```python
@dataclass
class IngestWebInput:
    url: str                          # required
    output_format: str = "internal"   # "json" | "internal"
    pages: int = None                 # None = all pages
```

---

## Outputs

```python
@dataclass
class IngestWebOutput:
    web_paragraphs: List[Paragraph]
    metadata: Dict[str, Any]

@dataclass
class Paragraph:
    area_code: str                    # W-001, W-002, ...
    text: str
    bbox: Tuple[int, int, int, int]   # (x1, y1, x2, y2) with y_offset applied
    page: int
    confidence: float
```

---

## Acceptance Criteria

### AC-INGEST-WEB-1: 全ページキャプチャ ✅

```
固定ヘッダー重複なし、全ページがキャプチャされている

Validation:
  exports/web_page_*.png ファイル数 == 指定ページ数
```

### AC-INGEST-WEB-2: ID連番付与 ✅

```
area_code が W-001 から連番で付与

Validation:
  /audit-ids
  → "ID Format: PASS"
```

### AC-INGEST-WEB-3: ID重複なし ✅

```
area_code に重複がない

Validation:
  /audit-ids
  → "Duplicates: 0"
```

### AC-INGEST-WEB-4: y_offset 加算 ✅

```
bbox の y座標に y_offset が正しく加算

Validation:
  /audit-coords
  → "y_offset applied: 100%"
```

### AC-INGEST-WEB-5: クラスタリング厳格設定 ✅

```
Match:70設定（overlap>0.6, left_diff<30, gap_x>15）使用

Validation:
  grep -r "overlap_ratio\|gap_x" OCR/app/core/engine_cloud.py
  → 緩和パラメータ（0.4, 80）が存在しない
```

### AC-INGEST-WEB-6: 画像保存 ✅

```
画像ファイルが exports/ に保存

Validation:
  ls exports/web_stitched_*.png
  → ファイル存在確認
```

---

## Validation Steps

```bash
# Step 1: ID整合性チェック
/audit-ids

# Step 2: 座標監査
/audit-coords

# Step 3: クラスタリング設定確認
grep -r "overlap_ratio\|gap_x\|gap_y" OCR/app/core/engine_cloud.py

# Step 4: 画像確認
ls -la exports/web_*.png
```

---

## Stop Conditions（中断条件）

### 🛑 IMMEDIATE STOP: クラスタリング緩和パラメータ使用

**検出方法**:
```bash
grep -r "overlap.*0\.4\|gap_y.*80" OCR/app/core/engine_cloud.py
```

**対処**: CLAUDE.md の厳格設定に復元、バックアップから復旧

---

### 🛑 IMMEDIATE STOP: ID重複検出

**検出方法**:
```bash
/audit-ids
# → "Duplicates: N > 0"
```

**対処**: カウンター初期化処理を確認、状態管理を修正

---

### 🛑 WARNING: Vision API エラー

**検出方法**: API認証失敗、quota超過

**対処**:
- `service_account.json` 確認
- Cloud Console で quota 確認
- リトライロジック追加

---

## Dependencies

- Playwright (Web scraping)
- Google Cloud Vision API
- `service_account.json`
- `app/core/enhanced_scraper.py`
- `app/core/engine_cloud.py`

---

## Example Usage

```python
from app.core.enhanced_scraper import scrape_url
from app.core.engine_cloud import process_image

web_paragraphs = await ingest_web(
    url="https://example.com",
    output_format="internal"
)
```

---

**Status**: Phase 1 実装予定

**Next Unit**: ingest_pdf
