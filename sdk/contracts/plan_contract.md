# Plan Contract v2

Status: Active  
Last Updated: 2026-02-11

## 1. Goal

Standardize how autonomous tasks are planned, approved, executed, and verified.

## 2. Required Plan Fields

1. Objective
2. Scope (in/out)
3. Deliverables (files and expected change size)
4. Acceptance criteria
5. Risk class: LOW, MEDIUM, HIGH
6. Security controls for the selected risk class
7. Test and domain-check strategy
8. Rollback and recovery plan (non-destructive)
9. Approval requirements

## 3. Deliverables Template

| # | File | Change Type | LOC Estimate | Risk |
|:--:|:--|:--|:--:|:--:|
| 1 | `path/to/file` | modify/new/delete | ~N | L/M/H |

## 4. Security Control Mapping

### LOW

- Verifier check
- Basic tests for impacted area

### MEDIUM

- Verifier check
- Domain checks
- Security checklist
- Human review before protected merge

### HIGH

- All MEDIUM controls
- Two-person approval
- Incident rollback drill readiness
- Explicit secrets and token impact review

## 5. Rollback Requirements

Allowed rollback paths:

1. `git revert` targeted commits
2. Restore selected files from known-good branch or tag
3. Recovery branch with clean cherry-picks

Disallowed as default:

- `git reset --hard`
- History rewrites on protected branches

## 6. Approval Matrix

| Risk | Planner | Verifier | Human Approver |
|:--|:--:|:--:|:--:|
| LOW | Required | Required | Optional |
| MEDIUM | Required | Required | Required |
| HIGH | Required | Required | Required (2+) |

## 7. Definition of Plan Complete

A plan is complete when:

1. Required fields are fully specified.
2. Risk class and controls are consistent.
3. Verification strategy is executable.
4. Approval path is explicit.

