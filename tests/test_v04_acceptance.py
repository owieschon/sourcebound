from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from clean_docs.evaluation import load_evaluation_tasks, run_evaluation


ROOT = Path(__file__).parents[1]


def _quickstart(readme: str) -> str:
    start = readme.index("## Install and audit")
    end = readme.index("\n## ", start + 3)
    return "# Quickstart fixture\n\n" + readme[start:end].strip() + "\n"


def test_human_quickstart_installs_and_runs_from_declared_docs(tmp_path: Path) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = _quickstart(readme)
    for command in (
        "python -m venv .venv",
        'pip install -e ".[dev]"',
        "clean-docs audit",
    ):
        assert command in quickstart

    package = tmp_path / "clean-docs"
    package.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", package / "pyproject.toml")
    shutil.copy2(ROOT / "README.md", package / "README.md")
    shutil.copytree(ROOT / "src", package / "src")
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    venv = tmp_path / ".venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv)],
        check=True,
        env=environment,
    )
    pip = venv / "bin/pip"
    subprocess.run(
        [
            str(pip), "install", "--disable-pip-version-check", "--no-deps",
            "--no-build-isolation", "-e", f"{package}[dev]",
        ],
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    target = tmp_path / "only-quickstart-docs"
    target.mkdir()
    (target / "README.md").write_text(quickstart, encoding="utf-8")

    result = subprocess.run(
        [str(venv / "bin/clean-docs"), "--root", str(target), "audit"],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "audit: 1 active document(s), 0 archived, 0 finding(s)" in result.stdout


def test_agent_configuration_round_trip_uses_only_contributor_bundle() -> None:
    tasks = load_evaluation_tasks(ROOT / ".clean-docs/eval.yml")
    task = next(task for task in tasks if task.id == "manifest-round-trip")
    assert task.context == (Path(".clean-docs/context/contributor.md"),)

    report = run_evaluation(
        ROOT, ROOT / ".clean-docs.yml", ROOT / ".clean-docs/eval.yml"
    )
    result = next(result for result in report.agent_tasks if result.id == task.id)
    assert result.ok
    assert result.detail == "configuration passes schema validation and check"


def test_limitation_retrieval_cites_canonical_limit_without_inference() -> None:
    report = run_evaluation(
        ROOT, ROOT / ".clean-docs.yml", ROOT / ".clean-docs/eval.yml"
    )
    result = next(
        result for result in report.agent_tasks if result.id == "limitation-retrieval"
    )
    response = (ROOT / ".clean-docs/evaluation/responses/limitation.txt").read_text()
    assert result.ok
    assert "README.md#current-limits" in response
    assert "clean-docs enforces network isolation" not in response.lower()
