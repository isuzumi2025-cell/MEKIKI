#!/usr/bin/env python3
"""Policy guard checks for autonomous orchestration governance."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path("sdk/orchestrator/context_manifest.json")


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def check_required_files(repo_root: Path, manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for rel in manifest.get("required_files", []):
        full = repo_root / rel
        if not full.exists():
            failures.append(f"missing required file: {rel}")
    return failures


def check_forbidden_patterns(
    repo_root: Path, manifest: dict[str, Any]
) -> list[str]:
    failures: list[str] = []
    for rule in manifest.get("forbidden_patterns", []):
        rel = rule.get("path", "")
        pat = rule.get("pattern", "")
        reason = rule.get("reason", "forbidden pattern")
        if not rel or not pat:
            failures.append("invalid forbidden_patterns rule in manifest")
            continue
        full = repo_root / rel
        if not full.exists():
            failures.append(f"forbidden pattern target missing: {rel}")
            continue
        content = full.read_text(encoding="utf-8")
        try:
            found = re.search(pat, content) is not None
        except re.error as exc:
            failures.append(
                f"invalid regex in forbidden_patterns for {rel}: {pat} ({exc})"
            )
            continue
        if found:
            failures.append(
                f"forbidden pattern found in {rel}: '{pat}' ({reason})"
            )
    return failures


def check_gitattributes(repo_root: Path, manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required_lines = manifest.get("gitattributes_requirements", [])
    target = repo_root / ".gitattributes"
    if not target.exists():
        return ["missing .gitattributes"]
    content = target.read_text(encoding="utf-8")
    for line in required_lines:
        if line not in content:
            failures.append(f".gitattributes missing required line: {line}")
    return failures


def check_entrypoint_alignment(repo_root: Path, manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    entrypoint = manifest.get("entrypoint", "")
    if not entrypoint:
        return ["manifest missing entrypoint"]
    entrypoint_path = repo_root / entrypoint
    if not entrypoint_path.exists():
        return [f"entrypoint missing: {entrypoint}"]

    content = entrypoint_path.read_text(encoding="utf-8")
    required_markers = [
        "Orchestration Contracts",
        "Privilege Architecture",
        "Threat Model and Defense-in-Depth",
    ]
    for marker in required_markers:
        if marker not in content:
            failures.append(
                f"entrypoint missing marker '{marker}' in {entrypoint}"
            )
    return failures


def main() -> int:
    repo_root = Path.cwd()
    if not MANIFEST_PATH.exists():
        print(f"policy guard: FAIL\n- missing manifest: {MANIFEST_PATH}")
        return 1

    manifest = load_manifest(MANIFEST_PATH)
    failures: list[str] = []
    failures.extend(check_required_files(repo_root, manifest))
    failures.extend(check_forbidden_patterns(repo_root, manifest))
    failures.extend(check_gitattributes(repo_root, manifest))
    failures.extend(check_entrypoint_alignment(repo_root, manifest))

    if failures:
        print("policy guard: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("policy guard: PASS")
    print("checks: required_files, forbidden_patterns, gitattributes, entrypoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
