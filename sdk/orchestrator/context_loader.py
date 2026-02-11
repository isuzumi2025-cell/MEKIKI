#!/usr/bin/env python3
"""Load and validate autonomous orchestration context from a manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("sdk/orchestrator/context_manifest.json")


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if "load_order" not in data or not isinstance(data["load_order"], list):
        raise ValueError("manifest must include list field: load_order")
    return data


def check_files_exist(repo_root: Path, manifest: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for rel in manifest.get("required_files", []):
        if not (repo_root / rel).exists():
            missing.append(rel)
    return missing


def list_context(manifest: dict[str, Any]) -> int:
    print(f"entrypoint: {manifest.get('entrypoint', '<missing>')}")
    print("load_order:")
    for idx, rel in enumerate(manifest["load_order"], start=1):
        print(f"{idx}. {rel}")
    return 0


def bundle_context(
    repo_root: Path, manifest: dict[str, Any], output_path: Path | None
) -> int:
    lines: list[str] = []
    lines.append("# Autonomous Context Bundle")
    lines.append("")
    lines.append(f"Manifest Version: {manifest.get('version', 'unknown')}")
    lines.append("")

    for rel in manifest["load_order"]:
        src = repo_root / rel
        lines.append(f"## Source: {rel}")
        lines.append("")
        if not src.exists():
            lines.append("MISSING")
            lines.append("")
            continue
        content = src.read_text(encoding="utf-8")
        lines.append(content.rstrip())
        lines.append("")

    payload = "\n".join(lines).rstrip() + "\n"
    if output_path is None:
        sys.stdout.write(payload)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        print(f"bundle written: {output_path}")
    return 0


def check_context(repo_root: Path, manifest: dict[str, Any]) -> int:
    errors: list[str] = []

    load_order = manifest.get("load_order", [])
    if len(load_order) != len(set(load_order)):
        errors.append("load_order contains duplicates")

    entrypoint = manifest.get("entrypoint")
    if entrypoint and entrypoint not in load_order:
        errors.append("entrypoint must be included in load_order")

    missing_required = check_files_exist(repo_root, manifest)
    if missing_required:
        errors.append(
            "missing required files: " + ", ".join(sorted(missing_required))
        )

    missing_in_load_order = [
        rel for rel in load_order if not (repo_root / rel).exists()
    ]
    if missing_in_load_order:
        errors.append(
            "missing load_order files: "
            + ", ".join(sorted(missing_in_load_order))
        )

    if errors:
        print("context check: FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("context check: PASS")
    print(f"files checked: {len(load_order)}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load and validate autonomous orchestration context"
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="path to context manifest json",
    )
    parser.add_argument(
        "--mode",
        choices=["list", "bundle", "check"],
        default="list",
        help="operation mode",
    )
    parser.add_argument(
        "--output",
        default="",
        help="output path for bundle mode (stdout when omitted)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    repo_root = Path.cwd()

    try:
        manifest = read_manifest(manifest_path)
    except Exception as exc:  # pragma: no cover - cli entrypoint
        print(f"context loader error: {exc}")
        return 2

    if args.mode == "list":
        return list_context(manifest)
    if args.mode == "bundle":
        out = Path(args.output) if args.output else None
        return bundle_context(repo_root, manifest, out)
    return check_context(repo_root, manifest)


if __name__ == "__main__":
    raise SystemExit(main())

