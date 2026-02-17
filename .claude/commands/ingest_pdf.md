# Command: ingest_pdf

**Purpose**: PDF抽出 → pdf_paragraphs生成

## Trigger

ユーザーが「PDFファイルからテキスト抽出」を指示したとき、またはPDF Loadボタンを押したとき。

## Input Schema

```json
{
  "pdf_path": "string (required)",
  "output_format": "json | internal (optional, default: internal)",
  "pages": "int | 'all' (optional, default: all)"
}
```

**例**:
```json
{
  "pdf_path": "C:\\path\\to\\sample.pdf",
  "output_format": "json",
  "pages": "all"
}
```

## Output Schema

```json
{
  "pdf_paragraphs": [
    {
      "area_code": "P-001",
      "text": "サンプルテキスト...",
      "bbox": [x1, y1, x2, y2],
      "page": 1,
      "confidence": 1.0,
      "source": "pdftext | ocr"
    }
  ],
  "metadata": {
    "total_paragraphs": 45,
    "total_pages": 2,
    "image_path": "exports/pdf_stitched_20260122.png",
    "extraction_method": "hybrid"
  }
}
```

## Execution Steps

1. **PDF読み込み**: PyMuPDF (fitz) でPDF開く
   ```python
   import fitz
   doc = fitz.open(pdf_path)
   ```

2. **ハイブリッド抽出**: 埋め込みテキスト優先、OCRフォールバック
   - **優先**: `page.get_text("dict")` で埋め込みテキスト抽出
   - **フォールバック**: テキストなし → Vision API OCR

3. **座標変換**: PyMuPDF座標(72 DPI) → 画像座標(300 DPI)
   ```python
   DPI_SCALE = 300.0 / 72.0  # ≈ 4.166
   scaled_bbox = [
       int(bbox[0] * DPI_SCALE),
       int(bbox[1] * DPI_SCALE + y_offset),
       int(bbox[2] * DPI_SCALE),
       int(bbox[3] * DPI_SCALE + y_offset)
   ]
   ```

4. **画像レンダリング**: サムネイル用
   ```python
   mat = fitz.Matrix(DPI_SCALE, DPI_SCALE)
   pix = page.get_pixmap(matrix=mat)
   page_img = Image.open(io.BytesIO(pix.tobytes("png")))
   ```

5. **縦連結**: 複数ページを縦に連結
   - `stitch_images_vertically()`
   - y_offset累積計算

6. **ID付与**: `P-{3桁}` 形式で `area_code` 生成
   - `P-001`, `P-002`, ...

7. **パラグラフ形成**: blockレベル → パラグラフに統合
   - block["type"] == 0 (テキストブロック) を抽出
   - 近接block統合（オプション）

## Acceptance Criteria

- ✅ **AC-INGEST-PDF-1**: 埋め込みテキストを優先的に抽出
- ✅ **AC-INGEST-PDF-2**: 埋め込みテキストなし時にOCRフォールバック実行
- ✅ **AC-INGEST-PDF-3**: area_code が `P-001` から連番で付与されている
- ✅ **AC-INGEST-PDF-4**: area_code に重複がない
- ✅ **AC-INGEST-PDF-5**: bbox の座標変換が正しい（`bbox * DPI_SCALE + y_offset`）
- ✅ **AC-INGEST-PDF-6**: 画像レンダリングと座標のDPI_SCALEが一致
- ✅ **AC-INGEST-PDF-7**: 画像ファイルが `exports/` に保存されている

## Failure Modes & Error Handling

| エラー分類 | 原因例 | 対処 |
|:---|:---|:---|
| **FILE_NOT_FOUND** | PDFパス不正 | パス確認、ファイル存在チェック |
| **PDF_CORRUPTED** | PDF破損 | ファイル再取得、別ツールで修復 |
| **DPI_SCALE_MISMATCH** | 画像とbboxのスケール不一致 | `DPI_SCALE=300/72` を統一使用 |
| **Y_OFFSET_ERROR** | y_offset未加算 | stitching処理のoffset計算確認 |
| **ID_DUPLICATE** | area_code重複 | カウンター初期化確認 |
| **VISION_API_ERROR** | OCRフォールバック失敗 | API認証確認、quota確認 |

## Coordinate System Notes

⚠️ **CRITICAL**: PDF座標系は左下原点、画像座標系は左上原点。PyMuPDFの `get_text("dict")` は左上原点に変換済みのため、原点変換は不要。DPI_SCALEのみ適用。

```
PyMuPDF bbox: (x1, y1, x2, y2) at 72 DPI, 左上原点
Image coords: (x1, y1, x2, y2) at 300 DPI, 左上原点

変換: scaled = bbox * (300/72) ≈ bbox * 4.166
```

## Validation Commands

```bash
# ID整合性チェック
/audit-ids

# 座標監査（DPI_SCALE検証）
/audit-coords

# 画像とbboxの整合性確認
python -c "from PIL import Image; img=Image.open('exports/pdf_stitched.png'); print(img.size)"
```

## Dependencies

- PyMuPDF (fitz)
- `app/core/paragraph_detector.py` (オプション)
- `app/core/engine_cloud.py` (OCRフォールバック)
- `service_account.json` (OCR時)

## Example Usage

```python
# unified_app.py 内で呼び出し
def on_pdf_load():
    pdf_paragraphs = ingest_pdf(
        pdf_path="C:\\path\\to\\sample.pdf",
        output_format="internal"
    )
    # → pdf_paragraphs: List[ParaParagraph]
```

---

**Next Command**: `match_paragraphs.md`
