#!/usr/bin/env python3
"""Record the deterministic fixture states used by the static demonstration."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from clean_docs.regions import atomic_write


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = """\
version: 1
bindings:
  - id: public-command
    type: region
    doc: README.md
    region: public-command
    extractor: file
    source: {path: command.txt}
    renderer: scalar
"""
README = """\
# Fixture service

<!-- sourcebound:purpose -->
Use this fixture when demonstrating a source-bound command repair. It lets readers observe drift, a bounded write, and the passing check.
<!-- sourcebound:end purpose -->

## Command

<!-- sourcebound:begin public-command -->
sourcebound check
<!-- sourcebound:end public-command -->
"""


def _run(root: Path, *arguments: str) -> dict[str, object]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *arguments],
        text=True,
        capture_output=True,
        env=environment,
        timeout=30,
        check=False,
    )
    output = proc.stdout
    if proc.stderr:
        output += proc.stderr
    return {
        "command": "sourcebound " + " ".join(arguments),
        "exit_code": proc.returncode,
        "output": output.rstrip(),
    }


def record() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="sourcebound-demo-") as temporary:
        root = Path(temporary)
        (root / ".sourcebound.yml").write_text(MANIFEST, encoding="utf-8")
        (root / "README.md").write_text(README, encoding="utf-8")
        (root / "command.txt").write_text("sourcebound check\n", encoding="utf-8")
        before = _run(root, "check")
        (root / "command.txt").write_text("sourcebound check --changed\n", encoding="utf-8")
        drift = _run(root, "check")
        repair = _run(root, "drive")
        verified = _run(root, "check")
    expected = (before["exit_code"], drift["exit_code"], repair["exit_code"], verified["exit_code"])
    if expected != (0, 1, 0, 0):
        raise RuntimeError(f"demo fixture returned unexpected exit codes: {expected}")
    return {
        "schema": "sourcebound.demo-evidence.v1",
        "title": "Make stale prose fail loudly.",
        "intended_reader": (
            "Maintainers deciding whether source-bound documentation is worth adding to a repository."
        ),
        "value": (
            "One binding connects a command in source to its README claim. When the source changes "
            "alone, the check fails with the exact stale region; repair rewrites that region and nothing else."
        ),
        "prerequisites": [
            "No account, credentials, backend, or database.",
            "The outputs below come from a generated temporary repository.",
        ],
        "states": [
            {"id": "before", "label": "1. Current", "steps": [before]},
            {"id": "drift", "label": "2. Drift caught", "steps": [drift]},
            {
                "id": "repaired",
                "label": "3. Repaired and verified",
                "steps": [repair, verified],
            },
        ],
        "limits": [
            "This page replays recorded deterministic evidence; it does not execute in the browser.",
            "The fixture proves one region-binding workflow, not every supported extractor.",
        ],
        "next_step": {
            "label": "Run the local quickstart",
            "href": "https://github.com/owieschon/sourcebound#install-and-audit",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / ".sourcebound/demo/evidence.json")
    args = parser.parse_args()
    rendered = json.dumps(record(), indent=2, sort_keys=True) + "\n"
    atomic_write(args.out.resolve(), rendered)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
