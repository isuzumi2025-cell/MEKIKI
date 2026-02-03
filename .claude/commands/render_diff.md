# Command: render_diff

**Purpose**: 色分け表示（オニオンスキン含む）

## Trigger

マッチング完了後、「比較表示」または「Advanced Comparison View」を開いたとき。

## Input Schema

```json
{
  "sync_pairs": "List[SyncPair] (required)",
  "web_image": "PIL.Image (required)",
  "pdf_image": "PIL.Image (required)",
  "web_regions": "List[Region] (required)",
  "pdf_regions": "List[Region] (required)",
  "display_mode": "split | onion | overlay (optional, default: split)"
}
```

**例**:
```json
{
  "sync_pairs": [...],
  "web_image": <PIL.Image>,
  "pdf_image": <PIL.Image>,
  "web_regions": [...],
  "pdf_regions": [...],
  "display_mode": "split"
}
```

## Output Schema

**内部状態更新**（ファイル出力なし、GUI表示）:
```json
{
  "canvas_items": {
    "web_canvas": ["image_id", "region_1", "region_2", ...],
    "pdf_canvas": ["image_id", "region_1", "region_2", ...]
  },
  "metadata": {
    "total_regions": 48,
    "displayed_regions": 48,
    "scroll_region": [0, 0, 1920, 3240]
  }
}
```

## Execution Steps

1. **Canvas初期化**: `advanced_comparison_view.py`
   - web_canvas, pdf_canvas をクリア
   - scrollregion リセット

2. **画像描画**: `_display_image()`
   ```python
   # PhotoImage作成（GC対策で参照保持）
   photo = ImageTk.PhotoImage(image)
   self._photo_ref = photo  # ★ 重要: GC防止

   # Canvas描画
   canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")
   canvas.config(scrollregion=canvas.bbox("all"))
   ```

3. **リージョン矩形描画**: `_redraw_regions()`
   ```python
   for region in regions:
       x1, y1, x2, y2 = region.bbox
       # scale適用
       sx1 = x1 * scale_x
       sy1 = y1 * scale_y
       sx2 = x2 * scale_x
       sy2 = y2 * scale_y

       # 矩形描画
       canvas.create_rectangle(
           sx1, sy1, sx2, sy2,
           outline="green",
           width=2,
           tags=("region", f"region_{region.area_code}")
       )

       # ID表示
       canvas.create_text(
           sx1 + 5, sy1 + 5,
           text=region.area_code,
           fill="yellow",
           anchor="nw",
           tags=("region", f"text_{region.area_code}")
       )
   ```

4. **座標変換の検証**: ピクセル完全一致確認
   - UI選択範囲: `canvasx(event.x) / scale_x` → 画像座標
   - 内部矩形: `bbox * scale` → Canvas座標
   - 誤差許容: ±2px

5. **サムネイル生成**: `spreadsheet_panel.py`
   ```python
   # SyncPair.web_id から Region を探索
   region = web_map.get(pair.web_id)  # ★ area_code一致が前提
   if region:
       x1, y1, x2, y2 = region.bbox
       thumbnail = web_image.crop((x1, y1, x2, y2))
       thumbnail.thumbnail((80, 80), Image.LANCZOS)
   ```

6. **Configure イベント対応**: リサイズ時の再描画
   ```python
   def _on_canvas_configure(self, event):
       if self._display_in_progress:
           return  # 描画中はスキップ

       def _redisplay():
           self._display_image(canvas, image)
           if regions:
               self._redraw_regions()  # ★ リージョンも再描画

       self._resize_job = self.after(100, _redisplay)
   ```

## Acceptance Criteria

- ✅ **AC-RENDER-1**: Web/PDF画像が正しく表示される
- ✅ **AC-RENDER-2**: リージョン矩形が全て表示される（消失なし）
- ✅ **AC-RENDER-3**: area_code（ID）がリージョン上に表示される
- ✅ **AC-RENDER-4**: サムネイル切り出し位置が正確（誤差≤2px）
- ✅ **AC-RENDER-5**: UI選択範囲と内部矩形の座標が一致（±2px）
- ✅ **AC-RENDER-6**: Canvas リサイズ後もリージョンが表示される
- ✅ **AC-RENDER-7**: PhotoImage参照がGCされない（画像消失なし）
- ✅ **AC-RENDER-8**: Live Comparison Sheetのサムネイルが全行に表示される

## Failure Modes & Error Handling

| エラー分類 | 原因例 | 対処 |
|:---|:---|:---|
| **IMAGE_NOT_DISPLAYED** | PhotoImage GC | `self._photo_ref` で参照保持 |
| **REGION_NOT_DISPLAYED** | Configure イベント干渉 | デバウンス処理で `_redraw_regions()` 呼び出し |
| **REGION_DISAPPEARED** | 2回目実行時の消失 | 状態初期化を関数冒頭で1回のみ |
| **THUMBNAIL_OFFSET** | bbox座標のズレ | `/audit-coords` で座標検証 |
| **THUMBNAIL_EMPTY** | ID不一致 | `/audit-ids` でID紐付け検証 |
| **SCALE_MISMATCH** | scale_x/scale_y未設定 | `_display_image()` でscale計算確認 |

## Coordinate Validation

**必須チェック**:
```python
# 1. bbox座標の範囲チェック
assert 0 <= x1 < x2 <= image.width
assert 0 <= y1 < y2 <= image.height

# 2. scale計算
scale_x = canvas_width / image.width
scale_y = canvas_height / image.height

# 3. Canvas座標変換
canvas_x1 = x1 * scale_x
canvas_y1 = y1 * scale_y

# 4. UI選択範囲→画像座標
image_x = canvasx(event.x) / scale_x
```

## Display Modes

### Split Mode（デフォルト）
- Web/PDFを左右に並べて表示
- リージョンを両方に描画

### Onion Skin Mode
- Web/PDFを重ね合わせ
- 透明度調整でズレを可視化
- ⚠️ Phase 2で実装予定

### Overlay Mode
- 差分箇所のみハイライト
- ⚠️ Phase 2で実装予定

## Validation Commands

```bash
# 座標監査（サムネイル位置検証）
/audit-coords

# Canvas状態確認（デバッグ）
python -c "
from app.gui.windows.advanced_comparison_view import AdvancedComparisonView
# ... Canvas items確認
"
```

## Dependencies

- `app/gui/windows/advanced_comparison_view.py`
- `app/gui/panels/spreadsheet_panel.py`
- CustomTkinter (Canvas, PhotoImage)
- PIL (Image, ImageTk)

## Example Usage

```python
# unified_app.py 内で呼び出し
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

**Next Command**: `sync_spreadsheet.md`
