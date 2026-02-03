# Command: audit_ids

**Purpose**: ID整合性チェック（web_id ↔ area_code の紐付け検証）

## Trigger

- コマンド実行: `/audit-ids`
- post_tool_use フック（自動）
- Phase 1実装前の診断

## Input Schema

```json
{
  "sync_pairs": "List[SyncPair] (required)",
  "web_regions": "List[Region] (required)",
  "pdf_regions": "List[Region] (required)",
  "output_format": "console | csv | json (optional, default: console)"
}
```

**例**:
```json
{
  "sync_pairs": [...],
  "web_regions": [...],
  "pdf_regions": [...],
  "output_format": "csv"
}
```

## Output Schema

### Console Output
```
================================
🔍 ID整合性監査レポート
================================

[✅ PASS] Web ID整合性
  - SyncPair.web_id と web_regions[].area_code: 100% 一致 (48/48)

[✅ PASS] PDF ID整合性
  - SyncPair.pdf_id と pdf_regions[].area_code: 100% 一致 (48/48)

[✅ PASS] ID重複チェック
  - Web ID重複: 0件
  - PDF ID重複: 0件

[Summary]
  Total SyncPairs: 48
  Total Errors: 0
  Status: ✅ PASS
```

### CSV Output (`exports/audit_ids_20260122.csv`)
```csv
Check,Status,Expected,Actual,Error_Detail
Web ID Match,PASS,48,48,
PDF ID Match,PASS,48,48,
Web ID Duplicate,PASS,0,0,
PDF ID Duplicate,PASS,0,0,
Web ID Missing,PASS,0,0,
PDF ID Missing,PASS,0,0,
```

### JSON Output
```json
{
  "timestamp": "2026-01-22T10:30:00",
  "status": "PASS | FAIL",
  "total_errors": 0,
  "checks": {
    "web_id_match": {
      "status": "PASS",
      "expected": 48,
      "actual": 48,
      "errors": []
    },
    "pdf_id_match": {
      "status": "PASS",
      "expected": 48,
      "actual": 48,
      "errors": []
    },
    "web_id_duplicate": {
      "status": "PASS",
      "duplicates": []
    },
    "pdf_id_duplicate": {
      "status": "PASS",
      "duplicates": []
    }
  }
}
```

## Validation Checks

### 1. Web ID Match
**検証内容**: `SyncPair.web_id` が `web_regions[].area_code` に存在するか

```python
web_area_codes = {r.area_code for r in web_regions}
for pair in sync_pairs:
    if pair.web_id not in web_area_codes:
        error = f"SyncPair.web_id={pair.web_id} が web_regions に存在しない"
```

### 2. PDF ID Match
**検証内容**: `SyncPair.pdf_id` が `pdf_regions[].area_code` に存在するか

```python
pdf_area_codes = {r.area_code for r in pdf_regions}
for pair in sync_pairs:
    if pair.pdf_id not in pdf_area_codes:
        error = f"SyncPair.pdf_id={pair.pdf_id} が pdf_regions に存在しない"
```

### 3. Web ID Duplicate
**検証内容**: `web_regions[].area_code` に重複がないか

```python
from collections import Counter
counter = Counter(r.area_code for r in web_regions)
duplicates = [id for id, count in counter.items() if count > 1]
```

### 4. PDF ID Duplicate
**検証内容**: `pdf_regions[].area_code` に重複がないか

```python
counter = Counter(r.area_code for r in pdf_regions)
duplicates = [id for id, count in counter.items() if count > 1]
```

### 5. Web ID Missing
**検証内容**: `web_regions[].area_code` が空文字列または None でないか

```python
missing = [r for r in web_regions if not r.area_code]
```

### 6. PDF ID Missing
**検証内容**: `pdf_regions[].area_code` が空文字列または None でないか

```python
missing = [r for r in pdf_regions if not r.area_code]
```

### 7. ID Format Validation
**検証内容**: area_code が `W-{3桁}` / `P-{3桁}` 形式か

```python
import re
web_pattern = re.compile(r'^W-\d{3}$')
pdf_pattern = re.compile(r'^P-\d{3}$')

for r in web_regions:
    if not web_pattern.match(r.area_code):
        error = f"Web area_code={r.area_code} が W-XXX 形式でない"

for r in pdf_regions:
    if not pdf_pattern.match(r.area_code):
        error = f"PDF area_code={r.area_code} が P-XXX 形式でない"
```

## Acceptance Criteria

- ✅ **AC-AUDIT-ID-1**: 全チェックがPASSの場合、exit code 0
- ✅ **AC-AUDIT-ID-2**: 1つでもエラーがある場合、exit code 1
- ✅ **AC-AUDIT-ID-3**: CSVレポートが `exports/` に保存される
- ✅ **AC-AUDIT-ID-4**: エラー詳細が明確に出力される
- ✅ **AC-AUDIT-ID-5**: 実行時間が1秒以内（パフォーマンス）

## Failure Modes & Error Handling

| エラー分類 | 原因例 | 対処 |
|:---|:---|:---|
| **MISMATCH** | SyncPair.web_id ≠ Region.area_code | Phase 1で修正（ID生成ロジック統一） |
| **DUPLICATE** | area_code重複 | カウンター初期化の確認 |
| **MISSING** | area_code が空 | ingest処理の確認 |
| **FORMAT_ERROR** | area_code形式が不正 | ID生成ロジックの確認 |
| **EMPTY_INPUT** | sync_pairs または regions が空 | ingest/match処理の確認 |

## Root Cause Analysis

**ID不一致の典型的原因**:

1. **ID生成タイミングのズレ**:
   - `ingest_web` で area_code 付与 → `W-001`, `W-002`
   - `match_paragraphs` で web_id 再生成 → `W-001`, `W-002` (異なるカウンター)
   - 解決: ID生成を1箇所に統一

2. **状態管理の不備**:
   - 2回目実行時にリストが append され続ける
   - area_code のインデックスがズレる
   - 解決: 状態初期化を関数冒頭で実施

3. **並列処理の競合**:
   - 複数スレッドが同時にカウンターをインクリメント
   - ID重複が発生
   - 解決: カウンターをスレッドセーフに

## Automated Fix (Phase 1)

**自動修正の方針**:
```python
# SyncPair.web_id を Region.area_code に合わせる
for pair in sync_pairs:
    # web_regions から該当Regionを探索（テキスト一致で）
    matching_region = find_region_by_text(pair.web_text, web_regions)
    if matching_region:
        pair.web_id = matching_region.area_code  # ★ 上書き
```

⚠️ **注意**: 根本解決はID生成ロジックの統一（Phase 1で実装）

## Dependencies

- `dataclasses` (SyncPair, Region)
- `collections.Counter`
- `re` (正規表現)

## Example Usage

```bash
# コンソール出力
/audit-ids

# CSV出力
/audit-ids --format=csv

# JSON出力
/audit-ids --format=json

# Python スクリプトから
python scripts/audit_ids.py \
  --sync-pairs=exports/sync_pairs.json \
  --web-regions=exports/web_regions.json \
  --pdf-regions=exports/pdf_regions.json \
  --output-format=csv
```

## Integration with post_tool_use Hook

```yaml
# .claude/hooks/post_tool_use.md
domain_checks:
  - name: audit_ids
    trigger: after_match_paragraphs
    on_failure: rollback
```

---

**Status**: Phase 0（仕様のみ）、Phase 1で実装
