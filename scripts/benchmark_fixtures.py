#!/usr/bin/env python3
"""Measure changed-check budgets on small, medium, and monorepo fixtures."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from clean_docs.bootstrap import apply_bootstrap_plan, build_bootstrap_plan
from clean_docs.performance import benchmark_changed_check
from clean_docs.regions import atomic_write


@dataclass(frozen=True)
class FixtureCase:
    name: str
    files: int
    project: Path = Path(".")
    unrelated_files: int = 0


CASES = (
    FixtureCase("small", 5),
    FixtureCase("medium", 150),
    FixtureCase("monorepo", 100, Path("packages/service"), 150),
)


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.test",
        "commit",
        "-qm",
        message,
    )
    return _git(root, "rev-parse", "HEAD")


def _files(root: Path, count: int) -> None:
    source = root / "src/package"
    source.mkdir(parents=True)
    for index in range(count):
        (source / f"module_{index:04d}.py").write_text(
            f"def _private_{index}():\n    return {index}\n"
        )


def _run_case(parent: Path, case: FixtureCase) -> dict[str, object]:
    root = parent / case.name
    root.mkdir()
    _git(root, "init", "-q")
    project_root = root / case.project
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "README.md").write_text(f"# {case.name.title()} fixture\n")
    (project_root / "pyproject.toml").write_text(
        f'[project]\nname = "{case.name}-fixture"\nversion = "1.0.0"\n'
    )
    (project_root / "cli.py").write_text("parser.add_parser('serve')\n")
    _files(project_root, case.files)
    if case.unrelated_files:
        unrelated = root / "packages/unrelated"
        unrelated.mkdir(parents=True)
        _files(unrelated, case.unrelated_files)
    plan = build_bootstrap_plan(project_root)
    if plan.gaps:
        raise RuntimeError(f"{case.name} bootstrap gaps: {plan.gaps}")
    apply_bootstrap_plan(project_root, plan)
    base = _commit(root, "protected baseline")
    (project_root / "cli.py").write_text(
        "parser.add_parser('serve')\nparser.add_parser('ship')\n"
    )
    head = _commit(root, "public CLI change")
    receipt = benchmark_changed_check(
        root,
        project_root / ".sourcebound.yml",
        base=base,
        head=head,
        project=case.project,
        iterations=3,
    )
    payload = receipt.as_dict()
    payload["fixture_files"] = case.files + case.unrelated_files
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="sourcebound-performance-") as temporary:
            cases = [_run_case(Path(temporary), case) for case in CASES]
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"performance: {exc}")
        return 2
    payload = {
        "schema": "sourcebound.performance-suite.v1",
        "ok": all(case["ok"] for case in cases),
        "cases": cases,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        atomic_write(args.out.resolve(), rendered)
    print(rendered, end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
