# SKILL: audit_ids

**Version**: 1.0.0
**Phase**: Phase 1 Unit 1
**Priority**: 🔴 CRITICAL

---

## Objective

ID整合性の完全検証：`SyncPair.web_id`/`pdf_id` と `Region.area_code` の紐付けが100%一致することを保証し、サムネイル・リージョン表示の空欄を根絶する。

---

## Scope

### ✅ このユニットで触って良い範囲

- `OCR/scripts/audit_ids.py` - ID監査スクリプト（新規作成）
- `OCR/tests/test_audit_ids.py` - ユニットテスト（新規作成）
- `exports/audit_ids_*.csv` - レポート出力先（自動生成）
- `exports/audit_ids_*.json` - JSON出力先（自動生成）

### ❌ このユニットで触るな

- `OCR/app/sdk/selection/simple_handler.py` - ID生成ロジック（変更禁止）
- `OCR/app/sdk/similarity/paragraph_matcher.py` - SyncPair生成ロジック（変更禁止）
- `OCR/app/gui/panels/spreadsheet_panel.py` - サムネイル表示ロジック（Phase 2で修正）
- `OCR/app/core/engine_cloud.py` - クラスタリング設定（Phase 2で修正）

---

## Inputs

```python
@dataclass
class AuditInput:
    sync_pairs: List[SyncPair]      # required
    web_regions: List[Region]       # required
    pdf_regions: List[Region]       # required
    output_format: str = "console"  # "console" | "csv" | "json"
```

**入力元**:
- `sync_pairs`: `match_paragraphs` コマンド出力
- `web_regions`: `ingest_web` コマンド出力
- `pdf_regions`: `ingest_pdf` コマンド出力

**スキーマ仮定**:
```python
@dataclass
class SyncPair:
    web_id: str      # e.g., "W-001"
    pdf_id: str      # e.g., "P-001"
    web_text: str
    pdf_text: str
    similarity: float

@dataclass
class Region:
    area_code: str   # e.g., "W-001", "P-001"
    text: str
    bbox: Tuple[int, int, int, int]
    page: int
```

---

## Outputs

### Console Output (default)

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

Exit Code: 0
```

### JSON Output (`--format=json`)

```json
{
  "timestamp": "2026-01-22T10:30:00",
  "status": "PASS",
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
    },
    "web_id_missing": {
      "status": "PASS",
      "missing_count": 0
    },
    "pdf_id_missing": {
      "status": "PASS",
      "missing_count": 0
    },
    "id_format_error": {
      "status": "PASS",
      "invalid_ids": []
    }
  },
  "error_classifications": {
    "ID_FORMAT_MISMATCH": 0,
    "MISSING_MAPPING": 0,
    "DUPLICATE_ID": 0,
    "CROSS_MEDIA_COLLISION": 0,
    "PAGE_INDEX_OUT_OF_RANGE": 0,
    "MISSING_AREA_CODE": 0
  }
}
```

### CSV Output (`--format=csv`)

`exports/audit_ids_20260122_103000.csv`:
```csv
Check,Status,Expected,Actual,Error_Detail
Web ID Match,PASS,48,48,
PDF ID Match,PASS,48,48,
Web ID Duplicate,PASS,0,0,
PDF ID Duplicate,PASS,0,0,
Web ID Missing,PASS,0,0,
PDF ID Missing,PASS,0,0,
ID Format Error,PASS,0,0,
```

---

## Acceptance Criteria

### AC-ID-1: No Duplicate IDs ✅

```
web_regions[].area_code に重複がない
pdf_regions[].area_code に重複がない

Validation:
  python OCR/scripts/audit_ids.py --format=console
  → "Duplicates: 0"
```

### AC-ID-2: SyncPair ↔ Region Mapping 100% ✅

```
SyncPair.web_id が web_regions[].area_code に100%存在
SyncPair.pdf_id が pdf_regions[].area_code に100%存在

Validation:
  python OCR/scripts/audit_ids.py --format=console
  → "Web ID Match: 100%"
  → "PDF ID Match: 100%"
```

### AC-ID-3: ID Format Valid ✅

```
web_regions[].area_code が W-XXX 形式
pdf_regions[].area_code が P-XXX 形式
(SEL_XXX も許可)

Validation:
  python OCR/scripts/audit_ids.py --format=console
  → "Format: PASS"
```

### AC-AUDIT-ID-1: Exit Code 0 on PASS ✅

```
全チェックがPASSの場合、exit code 0

Validation:
  python OCR/scripts/audit_ids.py
  echo $?
  → 0
```

### AC-AUDIT-ID-2: Exit Code 1 on FAIL ✅

```
1つでもエラーがある場合、exit code 1

Validation:
  python OCR/scripts/audit_ids.py
  echo $?
  → 1
```

### AC-AUDIT-ID-3: CSV Report Saved ✅

```
CSVレポートが exports/ に保存される

Validation:
  python OCR/scripts/audit_ids.py --format=csv
  ls exports/audit_ids_*.csv
  → ファイル存在確認
```

### AC-AUDIT-ID-4: Error Details Clear ✅

```
エラー詳細が明確に出力される

Validation:
  エラーメッセージに以下を含む：
  - Error Type (MISSING_MAPPING等)
  - Affected ID (W-001等)
  - Expected vs Actual
```

### AC-AUDIT-ID-5: Performance ≤1s ✅

```
実行時間が1秒以内

Validation:
  time python OCR/scripts/audit_ids.py
  → real < 1.0s
```

---

## Validation Steps

### Step 1: Unit Tests

```bash
# 全テストケース実行
pytest OCR/tests/test_audit_ids.py -v

# 期待結果：
# - test_perfect_match ✅ PASS
# - test_id_format_mismatch ✅ PASS
# - test_duplicate_ids ✅ PASS
# - test_missing_area_code ✅ PASS
# - test_syncpair_mismatch ✅ PASS
# - test_cross_media_collision ✅ PASS
# - test_sel_prefix_allowed ✅ PASS
# - test_empty_syncpair_ids_allowed ✅ PASS
```

### Step 2: Console Output Test

```bash
# テストデータでコンソール出力確認
python OCR/scripts/audit_ids.py --test --format=console

# 期待結果：
# ✅ PASS
# Web ID Match: 100%
# PDF ID Match: 100%
# Duplicates: 0
```

### Step 3: JSON Output Test

```bash
# JSON出力確認
python OCR/scripts/audit_ids.py --test --format=json > exports/test_audit.json

# jqで検証
cat exports/test_audit.json | jq '.status'
# → "PASS"

cat exports/test_audit.json | jq '.total_errors'
# → 0
```

### Step 4: CSV Export Test

```bash
# CSV出力確認
python OCR/scripts/audit_ids.py --test --format=csv

# ファイル確認
ls -la exports/audit_ids_*.csv

# 内容確認（全PASS）
cat exports/audit_ids_*.csv
# → すべてのチェックが PASS
```

### Step 5: Error Detection Test

```bash
# エラー検出テスト（意図的に不整合データを投入）
python OCR/tests/test_audit_ids.py::test_syncpair_mismatch -v

# 期待結果：
# エラーが正しく検出される
# Error Type: MISSING_MAPPING
# Affected ID: W-999
```

### Step 6: Performance Test

```bash
# 実行時間計測
time python OCR/scripts/audit_ids.py --test --format=console

# 期待結果：
# real < 1.0s
```

---

## Stop Conditions（中断条件）

### 🛑 IMMEDIATE STOP: ID生成ロジックに触れた

**検出方法**:
```bash
git diff OCR/app/sdk/selection/simple_handler.py
git diff OCR/app/sdk/similarity/paragraph_matcher.py
```

**対処**: 変更をロールバックし、audit_ids は診断のみに専念する。

---

### 🛑 IMMEDIATE STOP: スキーマ破綻

**検出方法**:
```bash
python OCR/scripts/audit_ids.py --test --format=json
# → KeyError または AttributeError
```

**対処**: SyncPair/Region の dataclass 定義を確認し、フィールド名の不一致を修正。

---

### 🛑 IMMEDIATE STOP: 座標系に触れた

**検出方法**:
```bash
grep -r "DPI_SCALE\|y_offset\|bbox" OCR/scripts/audit_ids.py
```

**対処**: audit_ids は座標を扱わない。座標検証は `/audit-coords` （Phase 2）に委譲。

---

### 🛑 WARNING: テスト失敗率 > 10%

**検出方法**:
```bash
pytest OCR/tests/test_audit_ids.py -v --tb=short
# → Failed tests > 10%
```

**対処**: 失敗したテストケースを個別に確認し、スクリプトロジックを修正。

---

### 🛑 WARNING: 実行時間 > 1s

**検出方法**:
```bash
time python OCR/scripts/audit_ids.py --test --format=console
# → real > 1.0s
```

**対処**:
- O(n^2) ループを O(n) に最適化
- set/dict を活用した高速検索
- 不要なログ出力を削除

---

## Error Classifications（Fail Fast）

### ID_FORMAT_MISMATCH

**定義**: area_code が `W-XXX` / `P-XXX` / `SEL_XXX` 形式でない

**検出**:
```python
if not re.match(r'^(W|P|SEL)[-_]\d{3}$', area_code):
    raise ValueError(f"ID_FORMAT_MISMATCH: {area_code}")
```

**復旧**: ID生成ロジックを修正（Phase 2）

---

### MISSING_MAPPING

**定義**: SyncPair.web_id が web_regions[].area_code に存在しない

**検出**:
```python
web_area_codes = {r.area_code for r in web_regions}
for pair in sync_pairs:
    if pair.web_id not in web_area_codes:
        raise ValueError(f"MISSING_MAPPING: {pair.web_id}")
```

**復旧**: ID生成の統一化（Phase 2）

---

### DUPLICATE_ID

**定義**: area_code に重複がある

**検出**:
```python
from collections import Counter
counter = Counter(r.area_code for r in web_regions)
duplicates = [id for id, count in counter.items() if count > 1]
if duplicates:
    raise ValueError(f"DUPLICATE_ID: {duplicates}")
```

**復旧**: カウンター初期化処理を確認

---

### CROSS_MEDIA_COLLISION

**定義**: Web ID と PDF ID が衝突（例: W-001 と P-001 が同じ area_code）

**検出**:
```python
web_ids = {r.area_code for r in web_regions}
pdf_ids = {r.area_code for r in pdf_regions}
collision = web_ids & pdf_ids
if collision:
    raise ValueError(f"CROSS_MEDIA_COLLISION: {collision}")
```

**復旧**: ID prefix の徹底（W- / P- の分離）

---

### MISSING_AREA_CODE

**定義**: area_code が空文字列または None

**検出**:
```python
missing = [r for r in web_regions if not r.area_code]
if missing:
    raise ValueError(f"MISSING_AREA_CODE: {len(missing)} regions")
```

**復旧**: ingest処理の確認

---

## Dependencies

- `dataclasses` (SyncPair, Region)
- `collections.Counter`
- `re` (正規表現)
- `json` (JSON出力)
- `csv` (CSV出力)
- `pytest` (テスト)

---

## Example Usage

```bash
# Console出力（デフォルト）
python OCR/scripts/audit_ids.py --test --format=console

# JSON出力
python OCR/scripts/audit_ids.py --test --format=json

# CSV出力
python OCR/scripts/audit_ids.py --test --format=csv

# テストなし（実データ）
python OCR/scripts/audit_ids.py \
  --sync-pairs=exports/sync_pairs.json \
  --web-regions=exports/web_regions.json \
  --pdf-regions=exports/pdf_regions.json \
  --format=console
```

---

## Integration with post_tool_use Hook

`.claude/hooks/post_tool_use.md` に統合：

```yaml
domain_checks:
  - name: audit_ids
    trigger: after_match_paragraphs
    command: python OCR/scripts/audit_ids.py --format=console
    on_failure: rollback
```

---

**Status**: ✅ Phase 1 Unit 1 完了（実装済み）

**Next Unit**: match_paragraphs（スキーマ固定）
