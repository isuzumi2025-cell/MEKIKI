# Orchestra Governance Quickstart

## Goal

Operate autonomous development with consistent context loading and policy gates.

## Files

1. Entrypoint: `ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md`
2. Manifest: `sdk/orchestrator/context_manifest.json`
3. Loader: `sdk/orchestrator/context_loader.py`
4. Guard: `sdk/orchestrator/policy_guard.py`
5. CI: `.github/workflows/orchestra-governance-check.yml`
6. GitHub branch protection scripts: `scripts/github/*.ps1`

## Local Commands

```bash
python sdk/orchestrator/context_loader.py --mode list
python sdk/orchestrator/context_loader.py --mode check
python sdk/orchestrator/policy_guard.py
```

## Optional Bundle Export

```bash
python sdk/orchestrator/context_loader.py --mode bundle --output outputs/context_bundle.md
```

## Rules

1. Keep orchestration definitions in `sdk/contracts`, `sdk/orchestrator`, and `sdk/telemetry`.
2. Keep root as entrypoint only; do not duplicate policy text in multiple places.
3. Update `context_manifest.json` when adding or renaming governance files.
4. Do not introduce destructive rollback commands into hook/runbook content.

## GitHub Protection Apply

```powershell
$env:GITHUB_TOKEN = "YOUR_TOKEN"
powershell -ExecutionPolicy Bypass -File scripts/github/apply_branch_protection.ps1 -Branch main -RequiredApprovals 1 -EnforceAdmins
```
