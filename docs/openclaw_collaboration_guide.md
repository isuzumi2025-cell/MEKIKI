# OpenClaw Collaboration Guide for Mekiki

Status: Active  
Last Updated: 2026-02-11

## 1. Goal

Use OpenClaw as a friendly co-pilot without breaking Mekiki governance,
security, or quality gates.

## 2. Collaboration Contract

OpenClaw contributions should follow the same contracts as internal agents:

1. `sdk/contracts/plan_contract.md`
2. `sdk/contracts/security_contract.md`
3. `sdk/orchestrator/state_machine.md`
4. `sdk/orchestrator/security_playbook.md`

## 3. Friendly Operating Mode

### 3.1 What OpenClaw Should Do

1. Propose bounded diffs with explicit acceptance criteria.
2. Reference affected files and expected behavior changes.
3. Include quick validation commands for verifier handoff.
4. Respect risk class and approval requirements.

### 3.2 What OpenClaw Must Not Do

1. Bypass policy guard or required checks.
2. Modify protected branches directly.
3. Introduce destructive rollback flows.
4. Access secrets outside approved runtime injection paths.

## 4. Recommended Integration Pattern

1. Intake in root spec context:
- load `ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md`
- load `sdk/orchestrator/context_manifest.json` order
2. OpenClaw creates patch proposal on feature branch.
3. Local verifier runs:
- context check
- policy guard
- domain checks
4. PR merges only after required checks and human review.

## 5. Prompt Template for OpenClaw

Use this when assigning work:

```text
You are contributing to Mekiki under strict governance.
Read and obey:
1) ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md
2) sdk/orchestrator/context_manifest.json load_order

Task:
- Objective: <one line>
- Scope: <in/out>
- Risk class: <LOW|MEDIUM|HIGH>
- Acceptance criteria: <list>

Constraints:
- No destructive rollback commands.
- Keep changes bounded and testable.
- Provide validation commands and impacted files.
```

## 6. First OpenClaw Pilot Tasks (Low Risk)

1. Extract pure helper from a large UI file without behavior changes.
2. Add tests for ID/coordinate conversion helper.
3. Improve doc automation scripts (non-runtime path).

These give quick wins while keeping blast radius small.

