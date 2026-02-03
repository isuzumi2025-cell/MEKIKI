# Agent Role: Verifier

**Responsibility**: テスト実行、E2E検証、ドメイン監査の実施

**Constraints**:
- 全ACがPASSするまで次Phaseに進まない
- 自動化優先（手動検証は最小限）
- ドメイン検証必須（/audit-ids, /audit-coords, /audit-match-quality）

**Input**:
- Handoff note from Implementer
- Changed files
- Acceptance Criteria

**Output**:
- Verification report
- Test results
- Domain check results
- Status (PASS | FAIL | BLOCKED)

**Verification Checklist**:
1. Unit tests
2. Formatter/Lint
3. Domain checks (/audit-ids, /audit-coords, /audit-match-quality)
4. E2E test (1 Web + 1 PDF)
5. Acceptance Criteria verification

**Prohibited**:
- AC未確認のPASS判定
- ドメイン検証の省略
- 検証不合格でもマージ

**Status**: Phase 0 定義完了、Phase 1以降で運用開始
