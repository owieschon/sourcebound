#!/usr/bin/env python3
"""Build the typed historical record used by the learning postmortem."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from clean_docs.regions import atomic_write


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/archive/v0/ultra-csm-before-after.md"
OUTPUT = ROOT / ".sourcebound/learning/ultra-csm-hygiene.json"


def _table_rows(text: str) -> list[dict[str, str]]:
    match = re.search(
        r"## The numbers\n\n\| Measure \| Before \| After \|\n"
        r"\| --- \| --- \| --- \|\n(?P<body>(?:\|.*\|\n)+)",
        text,
    )
    if match is None:
        raise RuntimeError("archived measurement table not found")
    rows: list[dict[str, str]] = []
    for line in match.group("body").splitlines():
        measure, before, after = (cell.strip() for cell in line.strip("|").split("|"))
        rows.append({"measure": measure, "before": before, "after": after})
    return rows


def _examples(text: str) -> list[dict[str, str]]:
    sections = re.findall(
        r"## Example \d+: (?P<case>[^\n]+)\n\n"
        r"Before -- (?P<before_intro>[^\n]+):\n\n```text\n(?P<before>.*?)\n```\n\n"
        r"After -- (?P<after_intro>[^\n]+):\n\n```text\n(?P<after>.*?)\n```",
        text,
        flags=re.DOTALL,
    )
    if len(sections) != 3:
        raise RuntimeError("expected three archived before-and-after examples")
    return [
        {
            "case": case,
            "before": before_intro.rstrip("."),
            "after": after_intro.rstrip("."),
        }
        for case, before_intro, _before, after_intro, _after in sections
    ]


def build_record(source: Path = SOURCE) -> dict[str, object]:
    text = source.read_text(encoding="utf-8")
    return {
        "schema": "sourcebound.learning-evidence.v1",
        "source": source.relative_to(ROOT).as_posix(),
        "measurements": _table_rows(text),
        "examples": _examples(text),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    rendered = json.dumps(build_record(args.source.resolve()), indent=2, sort_keys=True) + "\n"
    atomic_write(args.out.resolve(), rendered)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
