# Hook: post_tool_use

Purpose: Safe post-tool verification for autonomous development

Trigger:

- After edit/write/command actions that modify repository state

## 1. Verification Sequence

1. Format and lint (if relevant paths changed)
2. Unit tests for impacted modules
3. Domain checks:
- `audit_ids`
- `audit_coords`
- `audit_match_quality`
4. Risk-class security checklist for MEDIUM/HIGH tasks

## 2. Execution Policy

1. Run before commit for code changes.
2. Run after major refactor or schema updates.
3. Re-run in CI for merge eligibility.

## 3. Failure Handling (Safe Mode)

If a check fails:

1. Stop further automated changes.
2. Record failed check details in task notes.
3. Open or continue a fix branch.
4. Apply targeted fix and re-run checks.
5. Escalate to investigator role when root cause is unclear.

## 4. Rollback Policy

Allowed:

- `git revert <commit>` for explicit undo
- Restore specific files from known-good branch or tag
- Cherry-pick clean commits into a recovery branch

Not allowed as default:

- `git reset --hard`
- Force-push rewriting protected branch history

## 5. Severity Matrix

| Check | Severity | Action |
|:--|:--:|:--|
| `audit_ids` fail | CRITICAL | Block merge, fix before proceeding |
| `audit_coords` fail | CRITICAL | Block merge, fix before proceeding |
| `audit_match_quality` fail | MAJOR | Investigate, fix or approved exception |
| Unit test fail | CRITICAL | Block merge, fix before proceeding |
| Lint/format fail | MINOR | Auto-fix where safe, then re-check |

## 6. Success Criteria

A task can proceed only when:

1. Required checks pass for the task risk class.
2. Verification status is recorded.
3. Required approvals are complete.

