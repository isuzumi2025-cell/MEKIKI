# Security Playbook for Autonomous Orchestration

Status: Active  
Last Updated: 2026-02-11

## 1. Objective

Provide practical security operations for autonomous execution across plan,
build, verify, and release.

## 2. Pre-Execution Checklist

1. Assign task risk class: LOW, MEDIUM, or HIGH.
2. Confirm target branches and write scope.
3. Confirm required checks and approvers.
4. Confirm no destructive rollback steps are in the plan.
5. Confirm telemetry fields for traceability are present.

## 3. Runtime Guardrails

1. Run only approved tools and scripts.
2. Refuse hidden privilege escalation requests.
3. Block unknown network destinations for HIGH-risk tasks.
4. Require explicit confirmation before sensitive commands.
5. Capture actor, command class, and outcomes in logs.

## 4. Vulnerability Response Plant

### 4.1 Detect

Trigger conditions:

- secret leak alert
- suspicious automation behavior
- policy gate bypass
- unexplained dependency drift

### 4.2 Contain

1. Freeze merge to protected branches.
2. Disable affected automation token or workflow.
3. Isolate impacted branch/workspace.

### 4.3 Eradicate

1. Remove malicious or unsafe changes.
2. Rotate compromised credentials.
3. Pin or roll forward dependencies/actions safely.

### 4.4 Recover

1. Restore from clean branch/tag checkpoint.
2. Re-run verification and security checklist.
3. Re-open merge only after human sign-off.

### 4.5 Learn

1. Publish incident report with timeline and root cause.
2. Update security contract and controls.
3. Add regression checks to prevent recurrence.

## 5. Secure Rollback Strategy

Use these in order:

1. `git revert <commit>` for explicit change undo.
2. Restore specific files from known good tag/branch.
3. Cherry-pick clean commits into recovery branch.

Do not use destructive repository resets as default procedure.

## 6. Telemetry Requirements

Each autonomous run must emit:

1. task_id
2. risk_class
3. actor_role
4. touched_files_count
5. verification_status
6. security_check_status
7. approval_status
8. incident_flag

## 7. Game Day Drill

Run monthly drill:

1. Simulate token leak.
2. Simulate malicious dependency update.
3. Simulate policy-gate bypass attempt.
4. Record MTTR and control gaps.
