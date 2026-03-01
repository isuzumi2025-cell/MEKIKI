#!/usr/bin/env python3
"""Generate refactoring hotspot report for Mekiki OCR app."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


APP_ROOT = Path("OCR/app")
TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


@dataclass
class FileStat:
    path: Path
    size: int
    todo_count: int
    old_path: bool


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def collect_stats(root: Path) -> List[FileStat]:
    stats: List[FileStat] = []
    for path in iter_python_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        todo_count = len(TODO_PATTERN.findall(text))
        old_path = "_OLD" in path.parts or "backup" in path.name.lower()
        stats.append(
            FileStat(path=path, size=path.stat().st_size, todo_count=todo_count, old_path=old_path)
        )
    return stats


def render_markdown(stats: List[FileStat], top: int) -> str:
    lines: List[str] = []
    lines.append("# Mekiki Refactor Hotspot Report")
    lines.append("")
    lines.append(f"- Python files scanned: **{len(stats)}**")
    lines.append(f"- Top size rows: **{top}**")
    lines.append("")

    lines.append("## Largest Files")
    lines.append("")
    lines.append("| File | Size(bytes) | TODO-like tags | Legacy Path |")
    lines.append("|:--|--:|--:|:--:|")
    for s in sorted(stats, key=lambda x: x.size, reverse=True)[:top]:
        legacy = "YES" if s.old_path else "NO"
        lines.append(f"| `{s.path.as_posix()}` | {s.size} | {s.todo_count} | {legacy} |")
    lines.append("")

    lines.append("## Most TODO-like Tags")
    lines.append("")
    lines.append("| File | TODO-like tags | Size(bytes) |")
    lines.append("|:--|--:|--:|")
    for s in sorted(stats, key=lambda x: x.todo_count, reverse=True)[:top]:
        if s.todo_count == 0:
            continue
        lines.append(f"| `{s.path.as_posix()}` | {s.todo_count} | {s.size} |")
    lines.append("")

    legacy_count = sum(1 for s in stats if s.old_path)
    lines.append("## Legacy Footprint")
    lines.append("")
    lines.append(f"- Legacy/backup-like python files: **{legacy_count}**")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Mekiki refactor hotspot report")
    parser.add_argument("--root", default=str(APP_ROOT), help="scan root path")
    parser.add_argument("--top", type=int, default=15, help="top rows for tables")
    parser.add_argument("--out", default="", help="optional markdown output file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"scan root not found: {root}")

    stats = collect_stats(root)
    report = render_markdown(stats, args.top)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

