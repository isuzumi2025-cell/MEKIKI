# Autonomous Orchestra and SDK Spec v1

Status: Active  
Last Updated: 2026-02-11  
Scope: Repository root governance for autonomous development

## 1. Intent

This document is the root-level agreement for running a robust autonomous
orchestration system and SDK. It defines:

- A secure operating model for agent-driven development.
- A clear state machine and control points for execution.
- A practical privilege model for Windows + WSL + OneDrive constraints.

## 2. Non-Negotiable Principles

1. Single Git runtime: WSL Git only.
2. Main branch is human-governed and protected.
3. Least privilege by default for all bots and workflows.
4. Every autonomous action must be auditable.
5. No destructive rollback as a default operation.

## 3. System Topology

### 3.1 Planes

- Control Plane: task intake, planning, policy checks, approvals.
- Execution Plane: implementer/investigator/verifier/refactorer agents.
- Data Plane: source code, tests, artifacts, telemetry.
- Trust Plane: identities, permissions, signatures, secret boundaries.

### 3.2 Execution Flow

1. Intake: requirement is normalized into task metadata.
2. Plan: explicit deliverables, acceptance criteria, and risk class.
3. Execute: bounded edits with branch isolation.
4. Verify: tests, domain checks, and policy gates.
5. Review: human decision for protected targets.
6. Merge: controlled integration and telemetry capture.

## 4. Privilege Architecture

### 4.1 Rings

- Ring 0 (Human Approver): final authority for protected branches.
- Ring 1 (Orchestrator): write to `ai/*` and `session/*`; read elsewhere.
- Ring 2 (Worker Agents): scoped write to assigned workspace only.
- Ring 3 (CI): default read-only token; per-job elevation only.
- Ring 4 (Secrets): runtime injection only, never committed.

### 4.2 Hard Rules

1. No direct agent write access to `main`.
2. No global write tokens in CI defaults.
3. No permanent broad credentials for automation.
4. No fallback to `git reset --hard` in normal operations.

## 5. Threat Model and Defense-in-Depth

### 5.1 Primary Risks

- Prompt or instruction injection through docs/tools.
- Privilege escalation through over-broad tokens.
- Supply chain drift from unpinned dependencies and actions.
- Secret leakage through logs, artifacts, or backup folders.
- OneDrive file state conflicts causing inconsistent execution.
- Unsafe rollback behavior that erases valid unrelated work.

### 5.2 Required Controls

1. Trust boundary checks before tool execution.
2. Token minimization and branch-scoped credentials.
3. Action/dependency pinning and periodic security updates.
4. Secret scanning and redaction in logs/artifacts.
5. Local file pinning (`Always keep on this device`) for active repos.
6. Recovery via branch/tag snapshots, not destructive reset.

## 6. Safe Operations on OneDrive + WSL

1. Use WSL Git as source of truth.
2. Keep `core.filemode=false` for NTFS stability.
3. Enforce line endings with `.gitattributes`.
4. Avoid x-bit assumptions; call scripts through interpreter.
5. Treat Git remote history as canonical collaboration state.

## 7. Orchestration Contracts

This spec is backed by:

- `sdk/contracts/plan_contract.md`
- `sdk/contracts/acceptance_criteria.md`
- `sdk/contracts/security_contract.md` (added by this change)
- `sdk/orchestrator/task_model.md`
- `sdk/orchestrator/state_machine.md`
- `sdk/orchestrator/security_playbook.md` (added by this change)
- `sdk/telemetry/metrics.md`

## 7.1 Context Loading Contract

Single source of truth:

- `sdk/orchestrator/context_manifest.json`

Entrypoint behavior:

1. Start from `ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md`.
2. Load contract files in `load_order` from the manifest.
3. Refuse execution when required files are missing or policy check fails.

Reference commands:

```bash
python sdk/orchestrator/context_loader.py --mode list
python sdk/orchestrator/context_loader.py --mode check
python sdk/orchestrator/policy_guard.py
```

## 8. Hot Consensus Protocol (H-O-T)

Use this for fast high-quality decisions:

1. H (Hypothesis): one-sentence goal and expected impact.
2. O (Options): exactly three options with measurable tradeoffs.
3. T (Tradeoff): declare what is accepted, rejected, and why now.

Decision output:

- A single ADR note with owner, decision date, and review date.

## 9. Rollout Plan

### Phase A (Now)

1. Publish this root spec.
2. Add security contract and security playbook.
3. Replace destructive rollback guidance in post-tool hook docs.

### Phase B (Next)

1. Add CI policy gate for risk-classed tasks.
2. Add secret scanning and artifact redaction checks.
3. Add branch protection and required review gates.

### Phase C (Scale)

1. Add signed release provenance.
2. Add anomaly detection from telemetry.
3. Add periodic game-day incident drills.

## 10. Definition of Done

This governance model is active when:

1. All new autonomous tasks reference this spec.
2. Hook and runbook docs do not contain destructive rollback defaults.
3. Security contract controls are linked in plan and verification output.
4. Protected branches require human review and passing checks.
