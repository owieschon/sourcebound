#!/usr/bin/env python3
"""Run the published drift tutorial and record stable observed outcomes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".sourcebound/learning/tutorial-evidence.json"
MANIFEST = """\
version: 1
bindings:
  - id: status-actions
    type: region
    doc: README.md
    region: status-actions
    extractor: python-literal
    source: {path: src/actions.py, symbol: ACTIONS}
    renderer: markdown-table
    columns: [command, job]
projections:
  llms_txt:
    output: llms.txt
    title: Moonbase Status documentation
    summary: Source-bound operator documentation.
    include: [README.md]
"""
README = """\
# Moonbase Status

<!-- sourcebound:purpose -->
Use this fixture when a public command changes before its operator guide. It gives maintainers a checked path from stale prose to a repaired and verified page.
<!-- sourcebound:end purpose -->

## Operator actions

<!-- sourcebound:begin status-actions -->
<!-- sourcebound:end status-actions -->
"""
SOURCE_BEFORE = """\
ACTIONS = [
    {"command": "report", "job": "Send the current habitat status"},
]
"""
SOURCE_AFTER = SOURCE_BEFORE.replace('"report"', '"publish"')


def _run(executable: Path, root: Path, *arguments: str) -> dict[str, object]:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    process = subprocess.run(
        [str(executable), "--root", str(root), *arguments],
        text=True,
        capture_output=True,
        env=environment,
        timeout=30,
        check=False,
    )
    output = (process.stdout + process.stderr).strip()
    return {
        "command": "sourcebound " + " ".join(arguments),
        "exit_code": process.returncode,
        "observed": output.splitlines()[0] if output else "No terminal output",
    }


def _write_fixture(root: Path) -> None:
    (root / "src").mkdir()
    (root / ".sourcebound.yml").write_text(MANIFEST, encoding="utf-8")
    (root / "README.md").write_text(README, encoding="utf-8")
    (root / "src/actions.py").write_text(SOURCE_BEFORE, encoding="utf-8")


def record(executable: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="sourcebound-learning-") as temporary:
        root = Path(temporary)
        _write_fixture(root)
        drive_baseline = _run(executable, root, "drive")
        project_baseline = _run(executable, root, "project")
        check_baseline = _run(executable, root, "check")
        verify_baseline = _run(executable, root, "verify")
        (root / "src/actions.py").write_text(SOURCE_AFTER, encoding="utf-8")
        readme_before_repair = (root / "README.md").read_text(encoding="utf-8")
        drift = _run(executable, root, "check")
        repair = _run(executable, root, "drive")
        readme_after_repair = (root / "README.md").read_text(encoding="utf-8")
        projection = _run(executable, root, "project")
        final_check = _run(executable, root, "check")
        final_verify = _run(executable, root, "verify")

    results = (
        drive_baseline,
        project_baseline,
        check_baseline,
        verify_baseline,
        drift,
        repair,
        projection,
        final_check,
        final_verify,
    )
    exit_codes = tuple(item["exit_code"] for item in results)
    if exit_codes != (0, 0, 0, 0, 1, 0, 0, 0, 0):
        raise RuntimeError(f"tutorial returned unexpected exit codes: {exit_codes}")
    if "publish" not in readme_after_repair or "report" not in readme_before_repair:
        raise RuntimeError("tutorial repair did not update the declared documentation region")
    prefix_before, suffix_before = readme_before_repair.split(
        "<!-- sourcebound:begin status-actions -->", 1
    )
    prefix_after, suffix_after = readme_after_repair.split(
        "<!-- sourcebound:begin status-actions -->", 1
    )
    if prefix_before != prefix_after or suffix_before.split(
        "<!-- sourcebound:end status-actions -->", 1
    )[1] != suffix_after.split("<!-- sourcebound:end status-actions -->", 1)[1]:
        raise RuntimeError("tutorial repair changed prose outside the declared region")
    return {
        "schema": "sourcebound.tutorial-evidence.v1",
        "steps": [
            {"moment": "Protected baseline", "command": "sourcebound check", "exit": 0, "meaning": "The bound page matches source."},
            {"moment": "Source changed alone", "command": "sourcebound check", "exit": 1, "meaning": "The status-actions binding is stale."},
            {"moment": "Declared region repaired", "command": "sourcebound drive", "exit": 0, "meaning": "Only the bound region changes."},
            {"moment": "Projection refreshed", "command": "sourcebound project", "exit": 0, "meaning": "llms.txt receives the repaired page digest."},
            {"moment": "Repository verified", "command": "sourcebound verify", "exit": 0, "meaning": "Bindings and projections are current."},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sourcebound", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    executable = args.sourcebound.resolve()
    if not executable.is_file():
        raise SystemExit(f"sourcebound executable not found: {executable}")
    rendered = json.dumps(record(executable), indent=2, sort_keys=True) + "\n"
    args.out.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.out.resolve().write_text(rendered, encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
