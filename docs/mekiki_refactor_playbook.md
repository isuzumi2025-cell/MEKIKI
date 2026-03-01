# Mekiki Refactor Playbook (Recommended Sequence)

Status: Active  
Last Updated: 2026-02-11

## 1. What Is Already Shared (Current Completion Shape)

The following governance baseline is already shared and executable:

1. Root orchestration spec: `ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md`
2. Context manifest and deterministic load order:
- `sdk/orchestrator/context_manifest.json`
- `sdk/orchestrator/context_loader.py`
3. Policy and security guardrails:
- `sdk/orchestrator/policy_guard.py`
- `sdk/contracts/security_contract.md`
- `sdk/orchestrator/security_playbook.md`
- `.claude/hooks/post_tool_use.md` (safe rollback policy)
4. CI governance checks:
- `.github/workflows/orchestra-governance-check.yml`
- `.github/workflows/orchestra-contract-check.yml`
5. Branch protection scripts:
- `scripts/github/apply_branch_protection.ps1`
- `scripts/github/get_branch_protection.ps1`

## 2. Priority Refactor Targets in Mekiki

Based on current code footprint, start with high-risk monoliths:

1. `OCR/app/gui/windows/advanced_comparison_view.py` (very large)
2. `OCR/app/gui/unified_app.py`
3. `OCR/app/gui/windows/storyboard_extractor.py`
4. Spreadsheet synchronization surface:
- `OCR/app/gui/panels/spreadsheet_panel.py`
- `OCR/app/sdk/...` matching/export contracts

## 3. Recommended Refactor Steps

### Step A: Stabilization Baseline

1. Define minimal smoke scenarios for Web/PDF ingest + compare + export.
2. Run current domain checks:
- `audit_ids`
- `audit_coords`
- `audit_match_quality`
3. Snapshot current metrics before structural changes.

### Step B: Extract Pure Domain Logic First

1. Move non-UI logic from large GUI files to service modules.
2. Keep adapters in UI layer thin and side-effect focused.
3. Add unit tests for extracted functions before replacing call sites.

### Step C: Introduce Bounded Modules

Split by domain boundaries:

1. `id_integrity`
2. `coordinate_transform`
3. `paragraph_matching`
4. `spreadsheet_projection`

Each module must have:

1. explicit input/output schemas
2. contract tests
3. telemetry hook points

### Step D: Replace Legacy Call Paths Incrementally

1. Feature-flag old/new path for each critical flow.
2. Compare outputs against baseline in verifier phase.
3. Remove dead branches only after two green cycles.

### Step E: Legacy Surface Reduction

1. Quarantine `_OLD` and backup-derived runtime references.
2. Ensure runtime imports never hit `_OLD`.
3. Convert backup references into documented migration notes.

## 4. Definition of Done per Refactor Slice

1. No regression in domain checks.
2. Diff per file stays bounded (target <= 100 LOC where practical).
3. At least one extracted module gains direct tests.
4. No destructive rollback steps needed.

## 5. Execution Cadence (1 Week Slice)

1. Day 1: baseline + hotspot scan + plan contract.
2. Day 2-3: extract one bounded module.
3. Day 4: wire-in + verify + telemetry.
4. Day 5: review, document, and merge.

## 6. Commands

```bash
powershell -ExecutionPolicy Bypass -File scripts/refactor/run_refactor_baseline.ps1
python scripts/refactor/hotspot_scan.py --out docs/analysis/mekiki_hotspot_report.md
python sdk/orchestrator/context_loader.py --mode check
python sdk/orchestrator/policy_guard.py
python sdk/orchestrator/completion_status.py --format markdown --out docs/analysis/mekiki_completion_status.md
```
