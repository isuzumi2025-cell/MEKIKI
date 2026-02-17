# Hook: post_tool_use

**Purpose**: ツール実行後の自動検証

**Trigger**: 全ツール実行後（Edit, Write, Bash等）

## Validation Steps

### 1. Formatter/Lint (Phase 2以降)

```bash
# Black (code formatter)
black --check OCR/app/

# Flake8 (linter)
flake8 OCR/app/ --max-line-length=100
```

### 2. Unit Tests

```bash
# Run all tests
pytest OCR/tests/ -v

# Run specific test
pytest OCR/tests/test_audit_ids.py -v
```

### 3. Domain Checks (MANDATORY)

#### /audit-ids

```bash
python OCR/scripts/audit_ids.py --format=console
```

**Acceptance Criteria**:
- Web ID Match: 100%
- PDF ID Match: 100%
- ID Duplicate: 0 errors
- Status: PASS

#### /audit-coords (Phase 2)

```bash
python OCR/scripts/audit_coords.py --format=console
```

**Acceptance Criteria**:
- DPI_SCALE consistency: 100%
- y_offset applied: 100%
- Coordinate error: ≤2px

#### /audit-match-quality (Phase 2)

```bash
python OCR/scripts/audit_match_quality.py --format=console
```

**Acceptance Criteria**:
- Match count: ≥70 (Match:70 baseline)
- Virtual matches: 0
- Score distribution: Normal (bimodal maintained)

### 4. Rollback on Failure

If any check fails:

```bash
# Rollback to previous state
git reset --hard HEAD

# Or restore from backup
Copy-Item backup_YYYYMMDD\*.py OCR\app\... -Force
```

## Execution Policy

- **Pre-commit**: Run before `git commit`
- **Post-edit**: Run after major code changes
- **CI/CD**: Integrate into continuous integration pipeline

## Failure Handling

| Check | Severity | Action |
|:---|:---:|:---|
| /audit-ids FAIL | 🔴 CRITICAL | Immediate rollback, fix before proceeding |
| /audit-coords FAIL | 🔴 CRITICAL | Immediate rollback, fix before proceeding |
| /audit-match-quality FAIL | 🟡 MAJOR | Investigate, rollback if regression |
| Unit tests FAIL | 🔴 CRITICAL | Immediate rollback |
| Formatter FAIL | 🟢 MINOR | Auto-fix with `black`, then re-check |

**Status**: Phase 0 定義完了、Phase 1以降で段階的実装
