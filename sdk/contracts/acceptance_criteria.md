# Acceptance Criteria Catalog

**Purpose**: Reusable AC definitions for domain-specific validation

## ID Integrity (ID監査)

### AC-ID-1: No Duplicate IDs

```
web_regions[].area_code に重複がない
pdf_regions[].area_code に重複がない

Validation:
  /audit-ids --format=console
  → "Duplicates: 0"
```

### AC-ID-2: SyncPair ↔ Region Mapping 100%

```
SyncPair.web_id が web_regions[].area_code に100%存在
SyncPair.pdf_id が pdf_regions[].area_code に100%存在

Validation:
  /audit-ids --format=console
  → "Web ID Match: 100%"
  → "PDF ID Match: 100%"
```

### AC-ID-3: ID Format Valid

```
web_regions[].area_code が W-XXX 形式
pdf_regions[].area_code が P-XXX 形式
(SEL_XXX も許可)

Validation:
  /audit-ids --format=console
  → "Format: PASS"
```

## Coordinate Integrity (座標監査)

### AC-COORD-1: DPI_SCALE Consistent

```
PDF座標変換に DPI_SCALE = 300/72 ≈ 4.166 を統一使用

Validation:
  /audit-coords --format=console
  → "DPI_SCALE consistency: 100%"
```

### AC-COORD-2: y_offset Applied

```
縦連結時に y_offset が各ページ座標に正しく加算されている

Validation:
  /audit-coords --format=console
  → "y_offset applied: 100%"
```

### AC-COORD-3: Coordinate Error ≤2px

```
UI選択範囲 ↔ 内部座標の誤差が2px以内

Validation:
  /audit-coords --format=console
  → "Coordinate error: avg=X.Xpx (≤2px)"
```

## Match Quality (マッチ品質)

### AC-MATCH-1: Match Count ≥ Baseline

```
Match:70設定使用時、Match数≥70

Validation:
  /audit-match-quality --format=console
  → "Match count: 70 (≥70 ✅)"
```

### AC-MATCH-2: No Virtual Matches

```
緩和パラメータ未使用、虚構マッチ0件

Validation:
  /audit-match-quality --format=console
  → "Virtual matches: 0 ✅"
```

### AC-MATCH-3: Score Distribution Normal

```
スコア分布が正常（二峰性維持）

Validation:
  /audit-match-quality --format=console
  → "Score distribution: Normal ✅"
```

## Match Schema (Phase 1 Unit 2)

### AC-SCHEMA-1: Schema Version Fixed

```
MatchResult schema version が v1.0.0 に固定

Validation:
  pytest OCR/tests/test_match_schema.py::TestMatchResult -v
  → All tests PASS
```

### AC-SCHEMA-2: BBox Validation

```
BBox座標が有効（x1 < x2, y1 < y2, 画像範囲内）

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match, image_size=(W, H))
  → result.is_valid == True
  → No INVALID_BBOX or BBOX_OUT_OF_RANGE errors
```

### AC-SCHEMA-3: ID Format Validation

```
source_id が ^(W|P|SEL)[-_]\d{3}$ パターンに一致

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match)
  → No INVALID_ID_FORMAT errors
```

### AC-SCHEMA-4: Score Range Validation

```
全スコアが [0.0, 1.0] 範囲内

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match)
  → No INVALID_SCORE errors
```

### AC-SCHEMA-5: Page Range Validation

```
page index が [0, page_count) 範囲内

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match, page_count=N)
  → No INVALID_PAGE or PAGE_OUT_OF_RANGE errors
```

### AC-SCHEMA-6: Backward Compatibility

```
MatchResult ↔ SyncPair 双方向変換が可逆

Validation:
  pytest OCR/tests/test_match_schema.py::TestBackwardCompatibility::test_roundtrip_conversion -v
  → PASS (キー情報が保存される)
```

## Display Quality (表示品質)

### AC-DISPLAY-1: All Regions Displayed

```
Web/PDF両方のキャンバスに全リージョン矩形が表示される

Validation:
  E2Eテスト（目視）
  → リージョン数 == Canvas items数
```

### AC-DISPLAY-2: All IDs Displayed

```
Live Comparison Sheetの全行にWeb ID/PDF IDが表示される

Validation:
  E2Eテスト（目視）
  → ID列に空欄なし
```

### AC-DISPLAY-3: All Thumbnails Displayed

```
Live Comparison Sheetの全行にサムネイルが表示される

Validation:
  E2Eテスト（目視）
  → サムネイル列に空欄なし
```

## Spreadsheet Export (スプレッドシート反映)

### AC-SHEET-1: Schema Version Fixed

```
スプレッドシート列定義がバージョン固定（v1.0.0）

Validation:
  schema_validator.py
  → "Schema version: v1.0.0"
```

### AC-SHEET-2: All Columns Present

```
必須列が全て存在（#, Web ID, Web Text, ⇔, PDF Text, PDF ID, Sync Rate）

Validation:
  スプレッドシート確認
  → 列数 == 9
```

### AC-SHEET-3: All Data Exported

```
全SyncPairが漏れなくエクスポートされる

Validation:
  len(sync_pairs) == スプレッドシート行数
```

## Performance (パフォーマンス)

### AC-PERF-1: Round Trips ≤3

```
Plan → 実装 → 検証 → 修正 のサイクルが3往復以内

Measurement:
  Task開始〜完了までのイテレーション数
```

### AC-PERF-2: Diff Size ≤100 LOC/File

```
1ファイルあたりの差分行数が100行以内

Validation:
  git diff --stat
  → 各ファイル ≤100 LOC
```

### AC-PERF-3: Test Failure Rate ≤10%

```
テスト失敗率が10%以内

Measurement:
  Failed tests / Total tests ≤ 0.1
```

---

**Status**: Phase 0 定義完了、Phase 1以降で使用
