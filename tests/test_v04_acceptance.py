from __future__ import annotations

import os
import site
import shutil
import subprocess
import sys
from pathlib import Path

from clean_docs.evaluation import load_evaluation_tasks, run_evaluation


ROOT = Path(__file__).parents[1]


def test_human_quickstart_installs_and_runs_from_declared_docs(tmp_path: Path) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("## Install in the repository you want to protect")
    end = readme.index("\n## ", start + 3)
    quickstart = readme[start:end]
    for command in (
        "gh release download --repo owieschon/clean-docs",
        "python3 -m venv .venv",
        'python -m pip install "$release_dir"/clean_docs-*.whl',
        "clean-docs audit",
        "clean-docs init --no-model",
        "clean-docs check",
        "clean-docs verify",
    ):
        assert command in quickstart
    assert "git clone" not in quickstart
    assert "pip install -e" not in quickstart

    package = tmp_path / "clean-docs"
    package.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", package / "pyproject.toml")
    shutil.copy2(ROOT / "README.md", package / "README.md")
    shutil.copytree(ROOT / "src", package / "src")
    environment = dict(os.environ)
    # Python 3.12 no longer seeds setuptools into a new venv. Expose the
    # running test environment's pinned build backend without using the network.
    environment["PYTHONPATH"] = os.pathsep.join(site.getsitepackages())
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
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    (target / "README.md").write_text(
        "# Acorn queue\n\n"
        "<!-- clean-docs:purpose -->\n"
        "Acorn maintainers use this page to locate the queue's public surface and catch stale "
        "entry points before they merge.\n"
        "<!-- clean-docs:end purpose -->\n",
        encoding="utf-8",
    )
    (target / "queue.py").write_text(
        "def enqueue(job: str) -> str:\n    return job\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(target), "add", "."], check=True)

    results = []
    for arguments in (
        ("audit",),
        ("init", "--no-model"),
        ("check",),
        ("verify",),
    ):
        results.append(subprocess.run(
            [str(venv / "bin/clean-docs"), "--root", str(target), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        ))

    assert [result.returncode for result in results] == [0, 0, 0, 0], [
        result.stdout + result.stderr for result in results
    ]
    assert "audit: 1 active document(s), 0 archived, 0 finding(s)" in results[0].stdout
    assert '"ok": true' in results[-1].stdout


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
    assert "README.md#current-boundaries" in response
    assert "clean-docs enforces network isolation" not in response.lower()
