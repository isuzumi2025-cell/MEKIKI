# GitHub Branch Protection Setup

## Scope

Apply branch protection to `main` for:

1. PR-based merges only
2. Required checks:
- `contract-check`
- `governance-check`
3. Required reviews
4. No force-push and no branch deletion

## Prerequisites

1. Admin or maintainer permission on the repository.
2. Personal Access Token with repo administration scope.
3. Token available as `GITHUB_TOKEN` (or pass `-Token`).
4. Alternatively, authenticated `git credential` helper can be used.

## Apply

```powershell
$env:GITHUB_TOKEN = "YOUR_TOKEN"
powershell -ExecutionPolicy Bypass -File scripts/github/apply_branch_protection.ps1 -Branch main -RequiredApprovals 1 -EnforceAdmins
```

## Verify

```powershell
$env:GITHUB_TOKEN = "YOUR_TOKEN"
powershell -ExecutionPolicy Bypass -File scripts/github/get_branch_protection.ps1 -Branch main
```

## Dry Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts/github/apply_branch_protection.ps1 -Branch main -DryRun
```

## Notes

1. This setup assumes workflow jobs `contract-check` and `governance-check`.
2. If job names change, update `scripts/github/apply_branch_protection.ps1`.
3. For HIGH-risk change lanes, set `-RequiredApprovals 2`.
4. If `GITHUB_TOKEN` is not set, scripts try `git credential fill` fallback.
