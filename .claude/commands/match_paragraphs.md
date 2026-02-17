# Command: match_paragraphs

**Purpose**: マッチング → sync_pairs生成

## Trigger

Web/PDFのパラグラフ抽出完了後、「全文比較」または「AI分析モード」実行時。

## Input Schema

```json
{
  "web_paragraphs": "List[Paragraph] (required)",
  "pdf_paragraphs": "List[Paragraph] (required)",
  "threshold": "float (optional, default: 0.25)",
  "algorithm": "greedy | optimal (optional, default: greedy)"
}
```

**例**:
```json
{
  "web_paragraphs": [...],
  "pdf_paragraphs": [...],
  "threshold": 0.25,
  "algorithm": "greedy"
}
```

## Output Schema

### Legacy Format (SyncPair)

```json
{
  "sync_pairs": [
    {
      "web_id": "W-001",
      "pdf_id": "P-003",
      "web_text": "サンプルテキスト...",
      "pdf_text": "サンプルテキスト...",
      "similarity": 0.95,
      "web_bbox": [100, 200, 500, 250],
      "pdf_bbox": [120, 180, 480, 230]
    }
  ],
  "metadata": {
    "total_pairs": 48,
    "avg_similarity": 0.78,
    "sync_rate": 0.366,
    "unmatched_web": 22,
    "unmatched_pdf": 3
  }
}
```

### New Format (MatchResult Schema v1.0.0) - Phase 1 Unit 2

**Purpose**: Stabilize downstream processes with fixed schema and validation.

```python
@dataclass
class BBox:
    x1: int; y1: int; x2: int; y2: int
    # Validation: x1 < x2, y1 < y2, within image bounds

@dataclass
class MatchEntity:
    source_id: str  # W-XXX, P-XXX, SEL_XXX
    page: int       # 0-indexed, must be < page_count
    bbox: BBox
    text: str
    role: Optional[str] = None
    features: Optional[Dict] = None

@dataclass
class MatchScore:
    overall: float  # 0.0-1.0 (required)
    text: float     # 0.0-1.0 (required)
    layout: Optional[float] = None
    style: Optional[float] = None
    confidence: float = 1.0

@dataclass
class MatchResult:
    match_id: str
    web: Optional[MatchEntity]
    pdf: Optional[MatchEntity]
    score: MatchScore
    status: MatchStatus  # EXACT | PARTIAL | LOW_CONF | NO_MATCH
    debug: MatchDebug

    # Backward compatibility methods
    def to_legacy_syncpair() -> SyncPair
    @classmethod
    def from_legacy_syncpair(pair: SyncPair) -> MatchResult
```

**Schema Validation** (OCR/app/sdk/similarity/schema_validator.py):
- ID format: `^(W|P|SEL)[-_]\d{3}$`
- BBox: `x1 < x2`, `y1 < y2`, within `image_size`
- Page: `0 <= page < page_count`
- Score: `0.0 <= score <= 1.0`

**Error Classifications**:
- `MISSING_FIELD`: Required field absent
- `INVALID_BBOX`: Inverted or malformed bbox
- `INVALID_PAGE`: Negative or out-of-range page
- `INVALID_SCORE`: Score outside [0.0, 1.0]
- `INVALID_ID_FORMAT`: ID doesn't match pattern
- `BBOX_OUT_OF_RANGE`: BBox exceeds image bounds
- `PAGE_OUT_OF_RANGE`: Page ≥ page_count

## Execution Steps

1. **前提条件チェック**:
   - `web_paragraphs` が空でない
   - `pdf_paragraphs` が空でない
   - 各パラグラフに `area_code` が付与されている

2. **類似度行列計算**: `paragraph_matcher.py`
   ```python
   similarity_matrix[i][j] = compute_similarity(
       web_paragraphs[i].text,
       pdf_paragraphs[j].text
   )
   # 使用: difflib.SequenceMatcher
   ```

3. **貪欲法マッチング**:
   - 類似度行列から最大値を選択
   - threshold (0.25) 以上のペアのみ採用
   - 使用済みのweb_id/pdf_idはスキップ
   - 全ペア確定まで繰り返し

4. **SyncPair生成**:
   ```python
   SyncPair(
       web_id=web.area_code,  # ★ 重要: area_codeと一致必須
       pdf_id=pdf.area_code,
       web_text=web.text,
       pdf_text=pdf.text,
       similarity=score,
       web_bbox=web.bbox,
       pdf_bbox=pdf.bbox
   )
   ```

5. **Sync Rate計算**:
   ```python
   sync_rate = len(sync_pairs) / max(len(web), len(pdf))
   ```

6. **スコア分布検証**: 異常検出
   - 極端に低いスコアのペア（<0.3）が多数 → 警告
   - 極端に高いスコアのペア（>0.95）が多数 → 虚構マッチの可能性
   - 二峰性が崩れている → クラスタリング設定の問題

## Acceptance Criteria

- ✅ **AC-MATCH-1**: `SyncPair.web_id` が `web_paragraphs[].area_code` と100%一致
- ✅ **AC-MATCH-2**: `SyncPair.pdf_id` が `pdf_paragraphs[].area_code` と100%一致
- ✅ **AC-MATCH-3**: Sync Rate ≥ ベースライン（36.6%）
- ✅ **AC-MATCH-4**: Match数 ≥ ベースライン（70ペア、Match:70設定使用時）
- ✅ **AC-MATCH-5**: 虚構マッチ0件（緩和パラメータ未使用）
- ✅ **AC-MATCH-6**: スコア分布が正常（二峰性維持）
- ✅ **AC-MATCH-7**: ID重複なし（各web_id/pdf_idは最大1回のみ使用）

## Failure Modes & Error Handling

| エラー分類 | 原因例 | 対処 |
|:---|:---|:---|
| **EMPTY_INPUT** | web/pdf_paragraphs が空 | ingest段階のエラー確認 |
| **ID_MISSING** | area_code が未付与 | ingest処理の確認 |
| **ID_MISMATCH** | SyncPair.web_id ≠ Region.area_code | ID生成ロジック修正（Phase 1） |
| **LOW_SYNC_RATE** | Sync Rate < 30% | クラスタリング設定確認、テキスト正規化確認 |
| **VIRTUAL_MATCH** | Match:2（虚構） | 緩和パラメータ使用を検出、厳格設定に復元 |
| **SCORE_ANOMALY** | スコア分布が異常 | `/audit-match-quality` で可視化、原因特定 |

## Score Distribution Analysis

**正常なスコア分布**（Match:70設定）:
```
Score Range | Count | 判定
------------|-------|------
0.90-1.00   |  25   | ✅ 高品質マッチ
0.70-0.89   |  30   | ✅ 良好なマッチ
0.50-0.69   |  10   | ⚠️ 要確認
0.25-0.49   |   5   | ⚠️ 低品質
< 0.25      |   0   | ❌ 未マッチ（除外）
```

**異常なスコア分布**（緩和パラメータ使用時）:
```
Score Range | Count | 判定
------------|-------|------
0.90-1.00   |   0   | ❌ 高品質マッチなし
0.70-0.89   |   0   | ❌ 良好なマッチなし
0.50-0.69   |   1   | ❌ 虚構マッチ
0.25-0.49   |   1   | ❌ 虚構マッチ
```

## Validation Commands

```bash
# ID整合性チェック（最重要）
/audit-ids

# マッチ品質監査
/audit-match-quality

# スコア分布の可視化（Phase 1で実装）
python scripts/visualize_score_distribution.py
```

## Dependencies

- `app/sdk/similarity/paragraph_matcher.py`
- `app/core/paragraph_matcher.py`
- `app/core/sync_matcher.py`

**Phase 1 Unit 2 Additions**:
- `app/sdk/similarity/match_schema.py` - MatchResult schema (v1.0.0)
- `app/sdk/similarity/schema_validator.py` - Schema validation
- `tests/test_match_schema.py` - Unit tests for schema validation

## Example Usage

### Legacy Usage (Existing Code)

```python
# unified_app.py 内で呼び出し
from app.sdk.similarity.paragraph_matcher import ParagraphMatcher

matcher = ParagraphMatcher(threshold=0.25)
sync_pairs = matcher.match(web_paragraphs, pdf_paragraphs)

# → sync_pairs: List[SyncPair]
```

### New Schema Usage (Phase 1 Unit 2)

```python
from app.sdk.similarity.match_schema import MatchResult
from app.sdk.similarity.schema_validator import MatchSchemaValidator

# Convert legacy SyncPair to MatchResult
match = MatchResult.from_legacy_syncpair(sync_pair)

# Validate before passing to downstream processes
validator = MatchSchemaValidator()
result = validator.validate(
    match,
    image_size=(web_width, web_height),
    page_count=pdf_page_count
)

if not result.is_valid:
    # Handle validation errors
    for error in result.errors:
        print(f"[{error.error_type}] {error.field_path}: {error.message}")
    raise ValueError("Invalid MatchResult schema")

# Convert back to legacy format if needed
sync_pair = match.to_legacy_syncpair()
```

---

**Next Command**: `render_diff.md`
