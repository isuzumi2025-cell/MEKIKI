# SKILL: render_diff

**Version**: 1.0.0
**Phase**: Phase 2
**Priority**: 🟡 MAJOR

---

## Objective

比較表示の座標精度保証：Web/PDFキャンバスへの画像・リージョン矩形・サムネイル描画を正確に実行し、座標ズレ・表示消失・PhotoImage GC問題を根絶する。

---

## Scope

### ✅ このユニットで触って良い範囲

- `OCR/app/gui/windows/advanced_comparison_view.py` - Canvas描画ロジック
- `OCR/app/gui/panels/spreadsheet_panel.py` - サムネイル生成
- Canvas scale計算・座標変換ロジック
- Configure イベントハンドラ

### ❌ このユニットで触るな

- SyncPair/Region生成ロジック（Phase 1）
- ID紐付けロジック（audit_ids で検証済み）
- 座標系定数（DPI_SCALE, y_offset）の変更

---

## Inputs

```python
@dataclass
class RenderDiffInput:
    sync_pairs: List[SyncPair]        # required
    web_image: PIL.Image              # required
    pdf_image: PIL.Image              # required
    web_regions: List[Region]         # required
    pdf_regions: List[Region]         # required
    display_mode: str = "split"       # "split" | "onion" | "overlay"
```

---

## Outputs

**内部状態更新**（GUI表示）:
```python
@dataclass
class RenderDiffOutput:
    canvas_items: Dict[str, List[str]]  # {"web_canvas": [...], "pdf_canvas": [...]}
    metadata: Dict[str, Any]
```

---

## Acceptance Criteria

### AC-RENDER-1: 画像表示 ✅

```
Web/PDF画像が正しく表示される

Validation:
  目視確認：Canvas に画像が表示される
```

### AC-RENDER-2: リージョン矩形表示 ✅

```
リージョン矩形が全て表示される（消失なし）

Validation:
  Canvas items数 == len(regions)
```

### AC-RENDER-3: ID表示 ✅

```
area_code（ID）がリージョン上に表示

Validation:
  Canvas text items に area_code が含まれる
```

### AC-RENDER-4: サムネイル位置精度 ✅

```
サムネイル切り出し位置が正確（誤差≤2px）

Validation:
  /audit-coords
  → "Coordinate error: avg=X.Xpx (≤2px)"
```

### AC-RENDER-5: UI選択範囲一致 ✅

```
UI選択範囲と内部矩形の座標が一致（±2px）

Validation:
  手動選択 → bbox確認 → 誤差計測
```

### AC-RENDER-6: リサイズ後も表示 ✅

```
Canvas リサイズ後もリージョンが表示

Validation:
  ウィンドウリサイズ → リージョン表示確認
```

### AC-RENDER-7: PhotoImage GC防止 ✅

```
PhotoImage参照がGCされない

Validation:
  self._photo_ref に参照が保持されている
```

### AC-RENDER-8: サムネイル全行表示 ✅

```
Live Comparison Sheetのサムネイルが全行に表示

Validation:
  サムネイル列に空欄なし
```

---

## Validation Steps

```bash
# Step 1: 座標監査（サムネイル位置検証）
/audit-coords

# Step 2: Canvas状態確認
python -c "
from OCR.app.gui.windows.advanced_comparison_view import AdvancedComparisonView
# ... Canvas items count確認
"

# Step 3: リサイズテスト（E2E）
# 1. アプリ起動
# 2. 比較表示を開く
# 3. ウィンドウをリサイズ
# 4. リージョンが消失しないことを確認
```

---

## Stop Conditions（中断条件）

### 🛑 IMMEDIATE STOP: PhotoImage GC で画像消失

**検出方法**: Canvas に画像が表示されない

**対処**:
```python
self._photo_ref = ImageTk.PhotoImage(image)
canvas.create_image(0, 0, anchor="nw", image=self._photo_ref)
```

---

### 🛑 IMMEDIATE STOP: リージョン矩形消失

**検出方法**: Configure イベント後にリージョンが消える

**対処**:
```python
def _on_canvas_configure(self, event):
    if self._display_in_progress:
        return

    def _redisplay():
        self._display_image(canvas, image)
        if regions:
            self._redraw_regions()  # ★ 追加

    self._resize_job = self.after(100, _redisplay)
```

---

### 🛑 IMMEDIATE STOP: サムネイル位置ズレ > 2px

**検出方法**:
```bash
/audit-coords
# → "Coordinate error: avg > 2px"
```

**対処**: bbox座標の scale_x/scale_y 適用を確認

---

### 🛑 WARNING: ID紐付け失敗（空サムネイル）

**検出方法**: サムネイル列が空白

**対処**:
```bash
/audit-ids
# → ID不一致を修正
```

---

## Dependencies

- CustomTkinter (Canvas, PhotoImage)
- PIL (Image, ImageTk)
- `app/gui/windows/advanced_comparison_view.py`
- `app/gui/panels/spreadsheet_panel.py`

---

## Example Usage

```python
view = AdvancedComparisonView(...)

# 画像設定
view.web_image = stitched_web
view.pdf_image = stitched_pdf

# リージョン設定
view.web_regions = web_regions
view.pdf_regions = pdf_regions

# 描画
view._display_image(view.web_canvas, view.web_image)
view._display_image(view.pdf_canvas, view.pdf_image)
view._redraw_regions()
```

---

**Status**: Phase 2 実装予定

**Next Unit**: sync_spreadsheet
