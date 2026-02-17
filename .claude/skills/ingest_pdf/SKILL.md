# SKILL: ingest_pdf

**Version**: 1.0.0
**Phase**: Phase 1
**Priority**: 🟡 MAJOR

---

## Objective

PDFからのハイブリッドテキスト抽出：PyMuPDF埋め込みテキスト優先 + Vision API OCRフォールバックを実行し、DPI_SCALE座標変換・y_offset加算・ID付与を正確に行い、`pdf_paragraphs` を生成する。

---

## Scope

### ✅ このユニットで触って良い範囲

- PyMuPDF (fitz) によるPDF処理
- `OCR/app/core/paragraph_detector.py` - PDF text extraction
- `OCR/app/core/engine_cloud.py` - OCRフォールバック
- `exports/pdf_*.png` - PDF画像出力（自動生成）
- ID生成ロジック（P-XXX形式）

### ❌ このユニットで触るな

- **DPI_SCALE = 300/72 ≈ 4.166** は変更禁止
- 座標系の原点変換ロジック（PyMuPDFは既に左上原点）
- マッチングロジック（Phase 1 Unit 2）

---

## Inputs

```python
@dataclass
class IngestPdfInput:
    pdf_path: str                     # required
    output_format: str = "internal"   # "json" | "internal"
    pages: str = "all"                # "all" | int
```

---

## Outputs

```python
@dataclass
class IngestPdfOutput:
    pdf_paragraphs: List[Paragraph]
    metadata: Dict[str, Any]

@dataclass
class Paragraph:
    area_code: str                    # P-001, P-002, ...
    text: str
    bbox: Tuple[int, int, int, int]   # scaled by DPI_SCALE, y_offset applied
    page: int
    confidence: float
    source: str                       # "pdftext" | "ocr"
```

---

## Acceptance Criteria

### AC-INGEST-PDF-1: 埋め込みテキスト優先 ✅

```
埋め込みテキストを優先的に抽出

Validation:
  metadata["extraction_method"] == "hybrid"
  source == "pdftext" の割合が高い
```

### AC-INGEST-PDF-2: OCRフォールバック ✅

```
埋め込みテキストなし時にOCR実行

Validation:
  テキストなしページで source == "ocr"
```

### AC-INGEST-PDF-3: ID連番付与 ✅

```
area_code が P-001 から連番

Validation:
  /audit-ids
  → "ID Format: PASS"
```

### AC-INGEST-PDF-4: ID重複なし ✅

```
area_code に重複がない

Validation:
  /audit-ids
  → "Duplicates: 0"
```

### AC-INGEST-PDF-5: DPI_SCALE 座標変換 ✅

```
bbox * DPI_SCALE + y_offset が正しい

Validation:
  /audit-coords
  → "DPI_SCALE consistency: 100%"
```

### AC-INGEST-PDF-6: 画像レンダリング一致 ✅

```
画像レンダリングと座標のDPI_SCALEが一致

Validation:
  PIL Image size == PyMuPDF pixmap size
```

### AC-INGEST-PDF-7: 画像保存 ✅

```
画像ファイルが exports/ に保存

Validation:
  ls exports/pdf_stitched_*.png
```

---

## Validation Steps

```bash
# Step 1: ID整合性チェック
/audit-ids

# Step 2: 座標監査（DPI_SCALE検証）
/audit-coords

# Step 3: DPI_SCALE定数確認
grep -r "DPI_SCALE.*300.*72" OCR/app/core/paragraph_detector.py

# Step 4: 画像サイズ確認
python -c "from PIL import Image; img=Image.open('exports/pdf_stitched.png'); print(img.size)"
```

---

## Stop Conditions（中断条件）

### 🛑 IMMEDIATE STOP: DPI_SCALE 変更

**検出方法**:
```bash
grep -r "DPI_SCALE" OCR/app/core/ | grep -v "300.*72"
```

**対処**: DPI_SCALE = 300/72 に復元

---

### 🛑 IMMEDIATE STOP: y_offset 未加算

**検出方法**:
```bash
/audit-coords
# → "y_offset applied: < 100%"
```

**対処**: stitching処理のoffset計算を確認

---

### 🛑 IMMEDIATE STOP: 原点変換ミス

**検出方法**: サムネイル位置が上下反転

**対処**: PyMuPDFの `get_text("dict")` は左上原点のため、原点変換は不要

---

### 🛑 WARNING: PyMuPDF エラー

**検出方法**: PDF破損、ファイル読み込み失敗

**対処**:
- ファイルパス確認
- PDF修復ツール使用
- 別PDFでテスト

---

## Dependencies

- PyMuPDF (fitz)
- PIL (Image)
- `app/core/paragraph_detector.py`
- `app/core/engine_cloud.py`
- `service_account.json` (OCR時)

---

## Example Usage

```python
import fitz
from app.core.paragraph_detector import extract_pdf_text

pdf_paragraphs = ingest_pdf(
    pdf_path="C:\\path\\to\\sample.pdf",
    output_format="internal"
)
```

---

**Status**: Phase 1 実装予定

**Next Unit**: match_paragraphs
