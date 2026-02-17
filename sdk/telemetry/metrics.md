# Telemetry Metrics

**Purpose**: KPI定義と測定方法

## Core KPIs

### 1. Round Trip Count (往復回数)

**Definition**: Plan承認 → 実装 → 検証 → 修正 のサイクル数

**Target**: ≤3 回

**Measurement**:
```
round_trips = count(state_transitions where status changed from "in_progress" to "blocked" or "failed")
```

**Tracking**:
- Task開始時刻
- 各状態遷移時刻
- 完了時刻

### 2. Diff Size per File (差分量)

**Definition**: 1ファイルあたりの変更行数（追加+削除）

**Target**: ≤100 LOC

**Measurement**:
```bash
git diff --stat HEAD~1 | awk '{if ($NF == "file") print $(NF-2)}'
```

**Tracking**:
- ファイルパス
- 追加行数
- 削除行数
- 合計差分

### 3. Test Failure Rate (テスト失敗率)

**Definition**: 失敗したテスト数 / 全テスト数

**Target**: ≤10%

**Measurement**:
```bash
pytest OCR/tests/ --json-report --json-report-file=report.json
# Parse report.json for pass/fail counts
```

**Tracking**:
- Total tests
- Passed tests
- Failed tests
- Failure rate

## Domain-Specific Metrics

### 4. ID Integrity Score

**Definition**: ID整合性チェックのPASS率

**Target**: 100%

**Measurement**:
```bash
python OCR/scripts/audit_ids.py --format=json
# Parse JSON for error count
```

**Tracking**:
- Total checks
- Passed checks
- Failed checks
- Pass rate

### 5. Match Quality Score

**Definition**: マッチング品質の総合スコア

**Target**: Match数≥70、虚構マッチ0件

**Measurement**:
```bash
python OCR/scripts/audit_match_quality.py --format=json
# Parse JSON for match count, virtual matches
```

**Tracking**:
- Match count
- Virtual match count
- Average similarity score
- Score distribution

### 6. Coordinate Accuracy

**Definition**: 座標変換の平均誤差

**Target**: ≤2px

**Measurement**:
```bash
python OCR/scripts/audit_coords.py --format=json
# Parse JSON for avg_error
```

**Tracking**:
- Average error (px)
- Max error (px)
- Error distribution

## Reporting

### Daily Report

```
Date: YYYY-MM-DD

Round Trips: X (target: ≤3)
Diff Size: Y LOC/file (target: ≤100)
Test Failure Rate: Z% (target: ≤10%)

ID Integrity: 100% ✅
Match Quality: 70 matches ✅
Coordinate Accuracy: 1.2px ✅

Status: ✅ ALL TARGETS MET
```

### Weekly Trend

- Plot round trip trend
- Plot diff size trend
- Plot test failure rate trend
- Identify anomalies

---

**Status**: Phase 0 定義完了、Phase 2以降で実装
