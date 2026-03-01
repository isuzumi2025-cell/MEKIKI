#!/usr/bin/env python3
"""Compute governance completion status for Mekiki autonomous development."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


MANIFEST_PATH = Path("sdk/orchestrator/context_manifest.json")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def check_foundation(repo_root: Path, manifest: dict) -> List[CheckResult]:
    results: List[CheckResult] = []
    required = manifest.get("required_files", [])
    missing = [rel for rel in required if not file_exists(repo_root / rel)]
    results.append(
        CheckResult(
            name="required_files_present",
            passed=len(missing) == 0,
            detail="all present" if not missing else "missing: " + ", ".join(missing),
        )
    )

    root_spec = repo_root / "ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md"
    if root_spec.exists():
        content = root_spec.read_text(encoding="utf-8")
        active = "Status: Active" in content
        results.append(
            CheckResult(
                name="root_spec_active",
                passed=active,
                detail="Status: Active found" if active else "Status: Active missing",
            )
        )
    else:
        results.append(
            CheckResult(
                name="root_spec_active",
                passed=False,
                detail="ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md missing",
            )
        )
    return results


def check_automation(repo_root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    workflow_governance = repo_root / ".github/workflows/orchestra-governance-check.yml"
    workflow_contract = repo_root / ".github/workflows/orchestra-contract-check.yml"
    loader = repo_root / "sdk/orchestrator/context_loader.py"
    guard = repo_root / "sdk/orchestrator/policy_guard.py"

    results.append(
        CheckResult(
            name="governance_workflow",
            passed=file_exists(workflow_governance),
            detail="present" if file_exists(workflow_governance) else "missing",
        )
    )
    results.append(
        CheckResult(
            name="contract_workflow",
            passed=file_exists(workflow_contract),
            detail="present" if file_exists(workflow_contract) else "missing",
        )
    )
    results.append(
        CheckResult(
            name="context_loader",
            passed=file_exists(loader),
            detail="present" if file_exists(loader) else "missing",
        )
    )
    results.append(
        CheckResult(
            name="policy_guard",
            passed=file_exists(guard),
            detail="present" if file_exists(guard) else "missing",
        )
    )
    return results


def check_security(repo_root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    sec_contract = repo_root / "sdk/contracts/security_contract.md"
    sec_playbook = repo_root / "sdk/orchestrator/security_playbook.md"
    hook = repo_root / ".claude/hooks/post_tool_use.md"

    results.append(
        CheckResult(
            name="security_contract",
            passed=file_exists(sec_contract),
            detail="present" if file_exists(sec_contract) else "missing",
        )
    )
    results.append(
        CheckResult(
            name="security_playbook",
            passed=file_exists(sec_playbook),
            detail="present" if file_exists(sec_playbook) else "missing",
        )
    )

    if hook.exists():
        content = hook.read_text(encoding="utf-8").lower()
        destructive_cmd = re.search(
            r"(?im)^\s*git\s+reset\s+--hard\b", content
        )
        safe = destructive_cmd is None
        results.append(
            CheckResult(
                name="safe_rollback_policy",
                passed=safe,
                detail=(
                    "destructive reset not present"
                    if safe
                    else "destructive reset command found"
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="safe_rollback_policy",
                passed=False,
                detail="hook file missing",
            )
        )
    return results


def check_openclaw_readiness(repo_root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    guide = repo_root / "docs/openclaw_collaboration_guide.md"
    playbook = repo_root / "docs/mekiki_refactor_playbook.md"
    results.append(
        CheckResult(
            name="openclaw_guide",
            passed=file_exists(guide),
            detail="present" if file_exists(guide) else "missing",
        )
    )
    results.append(
        CheckResult(
            name="refactor_playbook",
            passed=file_exists(playbook),
            detail="present" if file_exists(playbook) else "missing",
        )
    )
    return results


def summarize(groups: Dict[str, List[CheckResult]]) -> dict:
    total = sum(len(v) for v in groups.values())
    passed = sum(1 for results in groups.values() for r in results if r.passed)
    percent = 0.0 if total == 0 else round((passed / total) * 100.0, 1)
    return {"passed": passed, "total": total, "percent": percent}


def render_text(groups: Dict[str, List[CheckResult]], summary: dict) -> str:
    lines: List[str] = []
    lines.append("Mekiki Governance Completion Status")
    lines.append(
        f"overall: {summary['passed']}/{summary['total']} ({summary['percent']}%)"
    )
    lines.append("")
    for group, results in groups.items():
        lines.append(f"[{group}]")
        for r in results:
            icon = "PASS" if r.passed else "FAIL"
            lines.append(f"- {icon} {r.name}: {r.detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown(groups: Dict[str, List[CheckResult]], summary: dict) -> str:
    lines: List[str] = []
    lines.append("# Mekiki Governance Completion Status")
    lines.append("")
    lines.append(
        f"- Overall: **{summary['passed']}/{summary['total']} ({summary['percent']}%)**"
    )
    lines.append("")
    for group, results in groups.items():
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| Check | Status | Detail |")
        lines.append("|:--|:--:|:--|")
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"| `{r.name}` | {status} | {r.detail} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report Mekiki governance completion")
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="output format",
    )
    parser.add_argument(
        "--out",
        default="",
        help="optional output file path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd()
    manifest = load_manifest(repo_root / MANIFEST_PATH)

    groups: Dict[str, List[CheckResult]] = {
        "foundation": check_foundation(repo_root, manifest),
        "automation": check_automation(repo_root),
        "security": check_security(repo_root),
        "openclaw_readiness": check_openclaw_readiness(repo_root),
    }
    summary = summarize(groups)

    if args.format == "json":
        payload = {
            "summary": summary,
            "groups": {
                k: [r.__dict__ for r in results] for k, results in groups.items()
            },
        }
        output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    elif args.format == "markdown":
        output = render_markdown(groups, summary)
    else:
        output = render_text(groups, summary)

    if args.out:
        out_path = repo_root / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
