# SKILL: match_paragraphs

**Version**: 1.0.0
**Phase**: Phase 1 Unit 2
**Priority**: 🔴 CRITICAL

---

## Objective

マッチング結果スキーマの固定化：MatchResult Schema v1.0.0 を確立し、bbox/page/score の範囲外データが下流（render_diff, sync_spreadsheet）に流れることを防ぐ。Backward compatibility を保ちながら、データ品質を保証する。

---

## Scope

### ✅ このユニットで触って良い範囲

- `OCR/app/sdk/similarity/match_schema.py` - MatchResult schema v1.0.0（新規作成）
- `OCR/app/sdk/similarity/schema_validator.py` - Schema validation（新規作成）
- `OCR/tests/test_match_schema.py` - Schema unit tests（新規作成）
- `.claude/commands/match_paragraphs.md` - スキーマ仕様追記
- `sdk/contracts/acceptance_criteria.md` - AC-SCHEMA-1〜6追加

### ❌ このユニットで触るな

- `OCR/app/sdk/similarity/paragraph_matcher.py` - マッチングアルゴリズム（変更禁止）
- `OCR/app/core/paragraph_matcher.py` - 既存マッチングロジック（変更禁止）
- `OCR/app/core/sync_matcher.py` - SyncPair生成ロジック（変更禁止）
- `OCR/app/core/engine_cloud.py` - クラスタリング設定（変更禁止）
- `OCR/app/gui/panels/spreadsheet_panel.py` - Display logic（Phase 2で対応）

---

## Inputs

```python
@dataclass
class MatchInput:
    web_paragraphs: List[Paragraph]  # required
    pdf_paragraphs: List[Paragraph]  # required
    threshold: float = 0.25           # optional
    algorithm: str = "greedy"         # "greedy" | "optimal"
```

**入力元**:
- `web_paragraphs`: `ingest_web` コマンド出力
- `pdf_paragraphs`: `ingest_pdf` コマンド出力

**Paragraph Schema**:
```python
@dataclass
class Paragraph:
    area_code: str               # W-001, P-001
    text: str
    bbox: Tuple[int, int, int, int]
    page: int
    confidence: float = 1.0
```

---

## Outputs

### Legacy Format (SyncPair) - Backward Compatible

```python
@dataclass
class SyncPair:
    web_id: str                      # e.g., "W-001"
    pdf_id: str                      # e.g., "P-001"
    web_text: str
    pdf_text: str
    similarity: float                # 0.0-1.0
    web_bbox: Optional[Tuple[int, int, int, int]] = None
    pdf_bbox: Optional[Tuple[int, int, int, int]] = None
```

### New Format (MatchResult Schema v1.0.0) - Phase 1 Unit 2

```python
@dataclass
class BBox:
    x1: int
    y1: int
    x2: int
    y2: int

    # Validation: x1 < x2, y1 < y2, within image bounds
    def to_tuple() -> Tuple[int, int, int, int]

    @classmethod
    def from_tuple(bbox: Tuple) -> BBox

@dataclass
class MatchEntity:
    source_id: str                   # W-XXX, P-XXX, SEL_XXX
    page: int                        # 0-indexed, must be < page_count
    bbox: BBox
    text: str
    role: Optional[str] = None
    features: Optional[Dict] = None

@dataclass
class MatchScore:
    overall: float                   # 0.0-1.0 (required)
    text: float                      # 0.0-1.0 (required)
    layout: Optional[float] = None   # 0.0-1.0
    style: Optional[float] = None    # 0.0-1.0
    confidence: float = 1.0

@dataclass
class MatchResult:
    match_id: str
    web: Optional[MatchEntity]
    pdf: Optional[MatchEntity]
    score: MatchScore
    status: MatchStatus              # EXACT | PARTIAL | LOW_CONF | NO_MATCH
    debug: MatchDebug

    # Backward compatibility methods
    def to_legacy_syncpair() -> SyncPair

    @classmethod
    def from_legacy_syncpair(pair: SyncPair) -> MatchResult
```

**Schema Version**: `v1.0.0`

---

## Acceptance Criteria

### AC-SCHEMA-1: Schema Version Fixed ✅

```
MatchResult schema version が v1.0.0 に固定

Validation:
  pytest OCR/tests/test_match_schema.py::TestMatchResult -v
  → All tests PASS
```

### AC-SCHEMA-2: BBox Validation ✅

```
BBox座標が有効（x1 < x2, y1 < y2, 画像範囲内）

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match, image_size=(W, H))
  → result.is_valid == True
  → No INVALID_BBOX or BBOX_OUT_OF_RANGE errors
```

### AC-SCHEMA-3: ID Format Validation ✅

```
source_id が ^(W|P|SEL)[-_]\d{3}$ パターンに一致

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match)
  → No INVALID_ID_FORMAT errors
```

### AC-SCHEMA-4: Score Range Validation ✅

```
全スコアが [0.0, 1.0] 範囲内

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match)
  → No INVALID_SCORE errors
```

### AC-SCHEMA-5: Page Range Validation ✅

```
page index が [0, page_count) 範囲内

Validation:
  validator = MatchSchemaValidator()
  result = validator.validate(match, page_count=N)
  → No INVALID_PAGE or PAGE_OUT_OF_RANGE errors
```

### AC-SCHEMA-6: Backward Compatibility ✅

```
MatchResult ↔ SyncPair 双方向変換が可逆

Validation:
  pytest OCR/tests/test_match_schema.py::TestBackwardCompatibility::test_roundtrip_conversion -v
  → PASS (キー情報が保存される)
```

### AC-MATCH-1: SyncPair.web_id ↔ web_paragraphs[].area_code 100% ✅

```
SyncPair.web_id が web_paragraphs[].area_code と100%一致

Validation:
  /audit-ids
  → "Web ID Match: 100%"
```

### AC-MATCH-2: SyncPair.pdf_id ↔ pdf_paragraphs[].area_code 100% ✅

```
SyncPair.pdf_id が pdf_paragraphs[].area_code と100%一致

Validation:
  /audit-ids
  → "PDF ID Match: 100%"
```

---

## Validation Steps

### Step 1: Schema Unit Tests

```bash
# 全テストケース実行
pytest OCR/tests/test_match_schema.py -v

# 期待結果（20+ tests）：
# TestBBox::test_bbox_creation ✅ PASS
# TestBBox::test_bbox_to_tuple ✅ PASS
# TestBBox::test_bbox_from_tuple ✅ PASS
# TestBBox::test_bbox_invalid_coordinates ✅ PASS
# TestMatchEntity::test_valid_web_entity ✅ PASS
# TestMatchEntity::test_valid_pdf_entity ✅ PASS
# TestMatchEntity::test_valid_sel_entity ✅ PASS
# TestMatchEntity::test_invalid_id_format ✅ PASS
# TestMatchEntity::test_negative_page_index ✅ PASS
# TestMatchScore::test_valid_score ✅ PASS
# TestMatchScore::test_score_out_of_range ✅ PASS
# TestMatchScore::test_negative_score ✅ PASS
# TestMatchResult::test_valid_exact_match ✅ PASS
# TestMatchResult::test_valid_no_match ✅ PASS
# TestMatchResult::test_bbox_out_of_image_bounds ✅ PASS
# TestMatchResult::test_page_out_of_range ✅ PASS
# TestBackwardCompatibility::test_to_legacy_syncpair ✅ PASS
# TestBackwardCompatibility::test_from_legacy_syncpair_basic ✅ PASS
# TestBackwardCompatibility::test_from_legacy_syncpair_with_bbox ✅ PASS
# TestBackwardCompatibility::test_roundtrip_conversion ✅ PASS
# TestIntegration::test_multiple_validation_errors ✅ PASS
# TestIntegration::test_validation_with_context ✅ PASS
```

### Step 2: BBox Validation Test

```python
from OCR.app.sdk.similarity.match_schema import BBox, MatchEntity, MatchResult, MatchScore, MatchStatus, MatchDebug
from OCR.app.sdk.similarity.schema_validator import MatchSchemaValidator

# BBox validation
validator = MatchSchemaValidator()

# Valid BBox
match = MatchResult(
    match_id="M-001",
    web=MatchEntity(
        source_id="W-001",
        page=0,
        bbox=BBox(x1=10, y1=20, x2=110, y2=50),
        text="Valid bbox"
    ),
    pdf=None,
    score=MatchScore(overall=0.9, text=0.9),
    status=MatchStatus.NO_MATCH,
    debug=MatchDebug(algorithm="test", duration_ms=10)
)

result = validator.validate(match, image_size=(1000, 1500), page_count=10)
assert result.is_valid  # ✅ PASS

# Invalid BBox (x1 > x2)
match_invalid = MatchResult(
    match_id="M-BAD",
    web=MatchEntity(
        source_id="W-002",
        page=0,
        bbox=BBox(x1=110, y1=20, x2=10, y2=50),  # Inverted
        text="Invalid bbox"
    ),
    pdf=None,
    score=MatchScore(overall=0.9, text=0.9),
    status=MatchStatus.NO_MATCH,
    debug=MatchDebug(algorithm="test", duration_ms=10)
)

result_invalid = validator.validate(match_invalid)
assert not result_invalid.is_valid  # ✅ FAIL (expected)
assert any(e.error_type == ValidationErrorType.INVALID_BBOX for e in result_invalid.errors)
```

### Step 3: Score Range Validation Test

```python
# Score out of range [0.0, 1.0]
match_bad_score = MatchResult(
    match_id="M-003",
    web=MatchEntity(
        source_id="W-003",
        page=0,
        bbox=BBox(x1=10, y1=20, x2=110, y2=50),
        text="Bad score"
    ),
    pdf=None,
    score=MatchScore(overall=1.5, text=0.9),  # overall > 1.0
    status=MatchStatus.NO_MATCH,
    debug=MatchDebug(algorithm="test", duration_ms=10)
)

result_bad_score = validator.validate(match_bad_score)
assert not result_bad_score.is_valid
assert any(e.error_type == ValidationErrorType.INVALID_SCORE for e in result_bad_score.errors)
```

### Step 4: Backward Compatibility Test

```python
from OCR.app.sdk.similarity.match_schema import MatchResult

# SyncPair → MatchResult conversion
@dataclass
class MockSyncPair:
    web_id: str
    pdf_id: str
    similarity: float
    web_text: str
    pdf_text: str
    web_bbox: Optional[tuple] = None
    pdf_bbox: Optional[tuple] = None

sync_pair = MockSyncPair(
    web_id="W-100",
    pdf_id="P-100",
    similarity=0.85,
    web_text="Legacy web",
    pdf_text="Legacy pdf",
    web_bbox=(10, 20, 110, 50),
    pdf_bbox=(50, 100, 200, 150)
)

match = MatchResult.from_legacy_syncpair(sync_pair)
assert match.web.source_id == "W-100"
assert match.pdf.source_id == "P-100"
assert match.score.overall == 0.85
assert match.web.bbox.to_tuple() == (10, 20, 110, 50)

# MatchResult → SyncPair conversion (roundtrip)
sync_pair_roundtrip = match.to_legacy_syncpair()
assert sync_pair_roundtrip.web_id == "W-100"
assert sync_pair_roundtrip.pdf_id == "P-100"
assert sync_pair_roundtrip.similarity == 0.85
```

### Step 5: Integration with Existing Code

```python
# Legacy code continues to work
from OCR.app.sdk.similarity.paragraph_matcher import ParagraphMatcher

matcher = ParagraphMatcher(threshold=0.25)
sync_pairs = matcher.match(web_paragraphs, pdf_paragraphs)

# New validation can be added incrementally
for pair in sync_pairs:
    match = MatchResult.from_legacy_syncpair(pair)
    result = validator.validate(match, image_size=(1920, 3000), page_count=5)

    if not result.is_valid:
        # Log errors, but don't break existing flow
        for error in result.errors:
            print(f"[{error.error_type}] {error.field_path}: {error.message}")
```

### Step 6: Performance Test

```bash
# Schema validation overhead測定
time python -c "
from OCR.app.sdk.similarity.match_schema import MatchResult
from OCR.app.sdk.similarity.schema_validator import MatchSchemaValidator

# 1000 MatchResults validation
validator = MatchSchemaValidator()
for i in range(1000):
    # ... validation
    pass
"

# 期待結果：< 1.0s for 1000 validations
```

---

## Stop Conditions（中断条件）

### 🛑 IMMEDIATE STOP: Matching Algorithm に触れた

**検出方法**:
```bash
git diff OCR/app/sdk/similarity/paragraph_matcher.py
git diff OCR/app/core/paragraph_matcher.py
git diff OCR/app/core/sync_matcher.py
```

**対処**: このユニットはスキーマ定義と検証のみ。アルゴリズム変更は Phase 2 以降。

---

### 🛑 IMMEDIATE STOP: Backward Compatibility 破綻

**検出方法**:
```bash
pytest OCR/tests/test_match_schema.py::TestBackwardCompatibility -v
# → FAIL
```

**対処**:
- `to_legacy_syncpair()` の実装を確認
- SyncPair のフィールド名と一致させる
- Roundtrip conversion が可逆であることを保証

---

### 🛑 IMMEDIATE STOP: ID Format Validation が厳格すぎる

**検出方法**:
```python
# SEL_XXX を拒否している場合
validator.validate(MatchEntity(source_id="SEL_001", ...))
# → INVALID_ID_FORMAT error
```

**対処**: ID pattern を `^(W|P|SEL)[-_]\d{3}$` に修正（SEL許可）

---

### 🛑 WARNING: Test Failure Rate > 10%

**検出方法**:
```bash
pytest OCR/tests/test_match_schema.py -v
# → Failed > 10%
```

**対処**: 失敗したテストケースを個別に確認し、スキーマ定義を修正。

---

### 🛑 WARNING: Validation Overhead > 10ms/item

**検出方法**:
```bash
time python -c "
# 100 items validation
for i in range(100):
    validator.validate(match)
"
# → > 1.0s
```

**対処**:
- 正規表現のコンパイル結果をキャッシュ
- 不要なログ出力を削除
- set/dict を活用した高速検索

---

## Error Classifications（Fail Fast）

### INVALID_BBOX

**定義**: BBox座標が反転（x1 >= x2, y1 >= y2）または malformed

**検出**:
```python
if bbox.x1 >= bbox.x2 or bbox.y1 >= bbox.y2:
    raise ValueError(f"INVALID_BBOX: {bbox}")
```

**復旧**: BBox生成ロジックを確認

---

### BBOX_OUT_OF_RANGE

**定義**: BBox座標が画像範囲外

**検出**:
```python
if not (0 <= bbox.x1 < bbox.x2 <= image_width):
    raise ValueError(f"BBOX_OUT_OF_RANGE: {bbox} exceeds ({image_width}, {image_height})")
```

**復旧**: 座標変換ロジックを確認（DPI_SCALE, y_offset）

---

### INVALID_PAGE

**定義**: Page index が負数

**検出**:
```python
if page < 0:
    raise ValueError(f"INVALID_PAGE: {page}")
```

**復旧**: Page index生成ロジックを確認

---

### PAGE_OUT_OF_RANGE

**定義**: Page index が page_count 以上

**検出**:
```python
if page >= page_count:
    raise ValueError(f"PAGE_OUT_OF_RANGE: {page} >= {page_count}")
```

**復旧**: Page count計算を確認

---

### INVALID_SCORE

**定義**: Score が [0.0, 1.0] 範囲外

**検出**:
```python
if not (0.0 <= score.overall <= 1.0):
    raise ValueError(f"INVALID_SCORE: {score.overall}")
```

**復旧**: スコア正規化ロジックを確認

---

### INVALID_ID_FORMAT

**定義**: source_id が `^(W|P|SEL)[-_]\d{3}$` パターンに不一致

**検出**:
```python
import re
if not re.match(r'^(W|P|SEL)[-_]\d{3}$', source_id):
    raise ValueError(f"INVALID_ID_FORMAT: {source_id}")
```

**復旧**: ID生成ロジックを確認

---

## Dependencies

- `dataclasses` (MatchResult, BBox, MatchEntity, MatchScore)
- `enum` (MatchStatus, ValidationErrorType)
- `typing` (Optional, Dict, List)
- `re` (ID format validation)
- `pytest` (Unit tests)

---

## Example Usage

### Validation Example

```python
from OCR.app.sdk.similarity.match_schema import MatchResult
from OCR.app.sdk.similarity.schema_validator import MatchSchemaValidator

# Create validator
validator = MatchSchemaValidator()

# Validate MatchResult
result = validator.validate(
    match,
    image_size=(1920, 3000),
    page_count=5
)

if not result.is_valid:
    # Handle validation errors
    for error in result.errors:
        print(f"[{error.error_type}] {error.field_path}: {error.message}")
    raise ValueError("Invalid MatchResult schema")
```

### Conversion Example

```python
# Legacy SyncPair → MatchResult
match = MatchResult.from_legacy_syncpair(sync_pair)

# Validate
result = validator.validate(match, image_size=(W, H), page_count=N)

# Convert back to legacy format if needed
if result.is_valid:
    sync_pair = match.to_legacy_syncpair()
```

---

## Integration with post_tool_use Hook

`.claude/hooks/post_tool_use.md` に統合（将来）：

```yaml
domain_checks:
  - name: match_schema_validation
    trigger: after_match_paragraphs
    command: python OCR/scripts/validate_match_schema.py
    on_failure: log_warning  # Non-blocking for now
```

---

**Status**: ✅ Phase 1 Unit 2 完了（実装済み）

**Next Unit**: render_diff（メタデータ固定）
