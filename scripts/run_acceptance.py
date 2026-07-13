#!/usr/bin/env python3
"""Run the named Version 0.1 acceptance scenarios and write one JSON receipt."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "tests/v01-acceptance.yml"
EXPECTED_IDS = {
    "ultra-csm-capability-drift",
    "command-claim",
    "symbol-removal",
    "unrelated-prose-preservation",
    "ref-purity",
    "ci-behavior",
    "version-zero-policy-parity",
    "known-false-positive-regressions",
    "self-hosting-checker-tampering",
}


@dataclass(frozen=True)
class AcceptanceCase:
    id: str
    test: str


def load_cases(path: Path) -> tuple[AcceptanceCase, ...]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"version", "release", "scenarios"}:
        raise ValueError("acceptance registry must contain version, release, and scenarios")
    if raw["version"] != 1 or raw["release"] != "0.1":
        raise ValueError("acceptance registry must describe release 0.1 at version 1")
    scenarios = raw["scenarios"]
    if not isinstance(scenarios, list):
        raise ValueError("acceptance scenarios must be a list")
    cases = []
    for index, item in enumerate(scenarios):
        if not isinstance(item, dict) or set(item) != {"id", "test"}:
            raise ValueError(f"acceptance scenario {index} must contain id and test")
        identifier = item["id"]
        node = item["test"]
        if not isinstance(identifier, str) or not isinstance(node, str):
            raise ValueError(f"acceptance scenario {index} fields must be strings")
        if not node.startswith("tests/") or "::" not in node:
            raise ValueError(f"acceptance scenario {identifier} has an invalid pytest node")
        if not (ROOT / node.split("::", 1)[0]).is_file():
            raise ValueError(f"acceptance scenario {identifier} names a missing test file")
        cases.append(AcceptanceCase(identifier, node))
    if {case.id for case in cases} != EXPECTED_IDS or len(cases) != len(EXPECTED_IDS):
        raise ValueError("acceptance registry must name each Version 0.1 scenario exactly once")
    return tuple(cases)


def run_cases(cases: tuple[AcceptanceCase, ...]) -> dict[str, object]:
    results = []
    for case in cases:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", case.test],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        results.append({
            "id": case.id,
            "test": case.test,
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })
    return {
        "schema": "clean-docs.acceptance.v1",
        "release": "0.1",
        "ok": all(result["ok"] for result in results),
        "scenarios": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        receipt = run_cases(load_cases(args.registry.resolve()))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"acceptance: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
