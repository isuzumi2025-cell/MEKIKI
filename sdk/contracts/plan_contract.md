# Plan Contract Template

**Purpose**: Standard format for implementation plans

## Structure

### 1. Summary

**Objective**: [What needs to be achieved]

**Scope**: [What is included/excluded]

**Estimated Effort**: [Number of files, LOC estimate]

### 2. Deliverables

| # | File | Type | LOC Estimate |
|:---:|:---|:---|:---:|
| 1 | `path/to/file.py` | Modified | ~50 |
| 2 | `path/to/test.py` | New | ~80 |

**Total**: X files, ~Y LOC

### 3. Acceptance Criteria

- ✅ AC-XXX-1: [Specific, measurable criterion]
- ✅ AC-XXX-2: [Specific, measurable criterion]
- ✅ AC-XXX-3: [Specific, measurable criterion]

### 4. Risks

| Risk | Probability | Impact | Mitigation |
|:---|:---:|:---:|:---|
| ID整合性破綻 | 🔴 High | 🔴 Critical | /audit-ids を必ず実行 |
| 座標系ズレ | 🟡 Medium | 🔴 Critical | /audit-coords で検証 |

### 5. Testing Strategy

**Unit Tests**:
- [ ] `test_xxx.py`: Test case descriptions

**Domain Checks**:
- [ ] `/audit-ids`: ID整合性
- [ ] `/audit-coords`: 座標検証

**E2E Test**:
- [ ] 1 Web + 1 PDF シナリオ

### 6. Rollback Plan

**Backup**:
```bash
mkdir backup_TaskXXX_YYYYMMDD
Copy-Item OCR\app\... backup_TaskXXX_YYYYMMDD\ -Force
```

**Restore**:
```bash
Copy-Item backup_TaskXXX_YYYYMMDD\*.py OCR\app\... -Force
```

**Git Tag**:
```bash
git tag task-xxx-complete
```

### 7. Approval

- [ ] Plan reviewed by user
- [ ] Acceptance criteria agreed
- [ ] Risks acknowledged
- [ ] Rollback plan confirmed

**Approved by**: [User name]
**Date**: [YYYY-MM-DD]

---

**Status**: Phase 0 定義完了、Phase 1以降で使用
