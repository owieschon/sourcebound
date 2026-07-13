#!/usr/bin/env python3
"""Fail when project documentation contains prohibited source-brand names."""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOC_SUFFIXES = {".md", ".rst", ".txt"}
SKIP_PARTS = {".git", ".venv", "build", "dist", "node_modules"}
BLOCKED = re.compile("clau" + "de(?: code)?", re.IGNORECASE)


def scan(root: Path) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in DOC_SUFFIXES:
            continue
        if set(path.relative_to(root).parts) & SKIP_PARTS:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if BLOCKED.search(line):
                findings.append((path.relative_to(root), line_number, line.strip()))
    return findings


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = scan(root)
    for path, line_number, line in findings:
        print(f"{path}:{line_number}: prohibited documentation name: {line}")
    if findings:
        print(f"documentation-name-check: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("documentation-name-check: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
