from __future__ import annotations

from pathlib import Path

from clean_docs.evaluation import load_evaluation_tasks, run_evaluation
from scripts.test_readme_quickstart import _quickstart_script


ROOT = Path(__file__).parents[1]


def test_human_quickstart_installs_and_runs_from_declared_docs(tmp_path: Path) -> None:
    del tmp_path
    quickstart = _quickstart_script()
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
    lifecycle = (ROOT / "scripts/test_readme_quickstart.py").read_text()
    assert '"PYTHONPATH"' in lifecycle
    assert "source_checkout_shadowed" in lifecycle
    assert "CLEAN_DOCS_CANDIDATE_WHEEL" in lifecycle


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
