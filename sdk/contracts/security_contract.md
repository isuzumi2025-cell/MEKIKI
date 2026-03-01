# Security Contract v1

Status: Active  
Last Updated: 2026-02-11

## 1. Purpose

Define mandatory security controls for autonomous orchestration and SDK
operations.

## 2. Risk Classes

- LOW: docs, comments, non-runtime metadata.
- MEDIUM: source changes with bounded impact.
- HIGH: auth, secrets, network boundary, deployment, or data persistence.

## 3. Mandatory Controls by Risk Class

| Control | LOW | MEDIUM | HIGH |
|:--|:--:|:--:|:--:|
| Human plan review | Optional | Required | Required |
| Verifier gate | Required | Required | Required |
| Domain checks | Optional | Required | Required |
| Security checklist | Optional | Required | Required |
| Two-person approval | No | Optional | Required |
| Rollback drill | No | Optional | Required |

## 4. Identity and Access

1. Default deny for write operations.
2. Branch-scoped automation tokens.
3. Protected branch requires human approver.
4. CI workflow defaults to read-only permissions.
5. Secrets must be injected at runtime only.

## 5. Supply Chain Controls

1. Pin external actions by version or digest.
2. Pin dependency versions for production paths.
3. Keep a documented update cadence.
4. Reject unknown external script execution in CI.

## 6. Code and Artifact Controls

1. Run lint/tests before merge gates.
2. Run secret scan on changed files and build outputs.
3. Redact sensitive values from logs and reports.
4. Keep auditable trace: task ID, actor, decision, and test results.

## 7. Operational Safety

1. No destructive rollback defaults in runbooks/hooks.
2. Recovery uses branch/tag restore and targeted revert.
3. Incident handling must include containment and credential review.
4. Record post-incident learning as an ADR or runbook update.

## 8. Acceptance Criteria

Security contract is satisfied when:

1. Task includes risk class and control list.
2. Verification report includes security checklist outcome.
3. Protected branch merges include required approvals/checks.
4. Incident reports include timeline, impact, and corrective actions.

