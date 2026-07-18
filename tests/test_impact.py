from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from clean_docs.cli import main
from clean_docs.impact import build_impact_plan


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            message,
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _symbol_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "src/api.py").write_text(
        "def public_api(timeout: int = 5):\n"
        "    return timeout\n\n"
        "def _normalize(value: int):\n"
        "    return value\n"
    )
    (root / "README.md").write_text(
        "# Fixture\n\n## API\n\n`public_api` is the supported entry point.\n"
    )
    (root / ".clean-docs.yml").write_text(
        """\
version: 1
bindings:
  - id: public-api
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/api.py, symbol: public_api}
"""
    )
    return root


def _projection_repository(tmp_path: Path) -> Path:
    root = tmp_path / "projection-repository"
    (root / "src").mkdir(parents=True)
    (root / ".clean-docs").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "src/actions.py").write_text(
        'ACTIONS = [{"name": "report", "job": "Report status"}]\n'
    )
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- clean-docs:begin actions -->\n"
        "<!-- clean-docs:end actions -->\n"
    )
    (root / ".clean-docs.yml").write_text(
        """\
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: python-literal
    source: {path: src/actions.py, symbol: ACTIONS}
    renderer: markdown-table
    columns: [name, job]
projections:
  llms_txt:
    output: llms.txt
    include: [README.md]
"""
    )
    (root / ".clean-docs/eval.yml").write_text(
        """\
version: 1
tasks:
  - id: read-projection
    audience: agent
    prompt: Name the documented action.
    context: [llms.txt]
    scorer: {type: structured-output, expected: {action: report}}
"""
    )
    assert main(["--root", str(root), "derive", "--write"]) == 0
    assert main(["--root", str(root), "project"]) == 0
    return root


def test_private_refactor_produces_coverage_complete_stable_no_impact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return value", "return int(value)"))
    head = _commit(root, "refactor private helper")

    first = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )
    second = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert first.as_dict() == second.as_dict()
    assert first.digest == second.digest
    assert first.impact == "none"
    assert first.coverage_complete
    assert first.no_impact
    assert [item.path for item in first.artifacts] == ["src/api.py"]
    assert first.artifacts[0].coverage == "graph-covered"
    assert first.artifacts[0].decision == "traversed accepted documentation relationships"
    assert first.unknown == ()

    assert main(
        [
            "--root",
            str(root),
            "plan",
            "--base",
            base,
            "--head",
            head,
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "clean-docs.impact-plan.v1"
    assert payload["digest"] == first.digest
    assert payload["no_impact"] is True


def test_public_implementation_refactor_does_not_become_interface_work(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return timeout", "return int(timeout)"))
    head = _commit(root, "refactor public implementation")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "none"
    assert not any(
        event.kind == "public-symbol-changed" for event in plan.events
    )
    assert {item.rule for item in plan.unrelated} == {"no-public-contract-delta"}


def test_unparseable_supported_source_is_unknown(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/broken.py"
    source.write_text("def public_api(\n")
    head = _commit(root, "break source syntax")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "unknown"
    assert plan.artifacts[0].adapter == "python-ast:failed"
    assert plan.artifacts[0].coverage == "unknown"
    assert {item.rule for item in plan.unknown} == {
        "unsupported-public-candidate"
    }


def test_unsupported_public_candidate_is_unknown_not_no_impact(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    (root / "src/Service.java").write_text(
        "public final class Service { public void start() {} }\n"
    )
    head = _commit(root, "add unsupported public service")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "unknown"
    assert not plan.coverage_complete
    assert not plan.no_impact
    assert plan.artifacts[0].path == "src/Service.java"
    assert plan.artifacts[0].may_expose_public_surface
    assert plan.artifacts[0].coverage == "unknown"
    assert {item.rule for item in plan.unknown} == {"unsupported-public-candidate"}


def test_internal_unsupported_script_does_not_expand_the_plan(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    (root / "scripts").mkdir()
    base = _commit(root, "base")
    (root / "scripts/format.sh").write_text("#!/bin/sh\nprintf '%s\\n' formatted\n")
    head = _commit(root, "add internal formatter")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "none"
    assert plan.artifacts[0].coverage == "unrelated-covered"
    assert {item.rule for item in plan.unrelated} == {
        "no-public-contract-delta"
    }


def test_unsupported_runtime_control_is_unknown(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    (root / "Dockerfile").write_text("FROM python:3.14\n")
    head = _commit(root, "change runtime container")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "unknown"
    assert plan.artifacts[0].may_expose_public_surface
    assert {item.rule for item in plan.unknown} == {
        "unsupported-public-candidate"
    }


def test_workflow_job_change_is_supported_advisory_impact(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- clean-docs:begin repository-surface -->\n"
        "<!-- clean-docs:end repository-surface -->\n"
    )
    with (root / ".clean-docs.yml").open("a") as manifest:
        manifest.write(
            """\
  - id: repository-surface
    type: region
    doc: docs/SURFACE.md
    region: repository-surface
    extractor: repository-overview
    source: {path: .}
    renderer: markdown-fragment
"""
        )
    workflow = root / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: CI\non: [push]\njobs:\n"
        "  test:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: python -m pytest\n"
    )
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "base")
    workflow.write_text(workflow.read_text().replace("pytest", "pytest -q"))
    head = _commit(root, "change test job")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "recommended"
    assert plan.coverage_complete
    assert plan.required == ()
    assert plan.artifacts[0].adapter == "github-actions-static"
    assert {event.kind for event in plan.events} == {"ci-job-changed"}
    assert {item.rule for item in plan.recommended} == {
        "public-contract-change"
    }


def test_malformed_workflow_cannot_become_no_impact(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    workflow = root / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("jobs: [not-a-mapping]\n")
    head = _commit(root, "add malformed workflow")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "unknown"
    assert plan.artifacts[0].adapter == "github-actions-static:failed"
    assert {item.rule for item in plan.unknown} == {
        "unsupported-public-candidate"
    }


def test_public_default_change_reaches_reference_and_migration_obligations(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("timeout: int = 5", "timeout: int = 10"))
    head = _commit(root, "change public default")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "required"
    event = next(item for item in plan.events if item.kind == "public-symbol-changed")
    assert event.coverage == "bound"
    finding = next(item for item in plan.required if item.rule == "public-contract-change")
    assert finding.obligations == ("review-migration", "review-reference")
    assert "binding:public-api" in finding.graph_roots


def test_binding_change_traverses_projection_and_evaluation(
    tmp_path: Path,
) -> None:
    root = _projection_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/actions.py"
    source.write_text(source.read_text().replace("report", "publish"))
    head = _commit(root, "rename action")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "required"
    assert {item.rule for item in plan.required} >= {
        "binding-drift",
        "projection-refresh",
    }
    assert {item.rule for item in plan.recommended} == {"evaluation-replay"}
    assert {edge.kind for edge in plan.edges} >= {
        "affects",
        "serves",
        "projects-to",
        "verified-by",
    }


def test_generated_projection_change_does_not_trigger_itself(
    tmp_path: Path,
) -> None:
    root = _projection_repository(tmp_path)
    base = _commit(root, "base")
    projection = root / "llms.txt"
    projection.write_text(projection.read_text() + "\nmanual edit\n")
    head = _commit(root, "touch generated projection")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=base, head=head
    )

    assert plan.impact == "none"
    assert plan.coverage_complete
    assert plan.artifacts[0].coverage == "generated"
    assert {item.rule for item in plan.unrelated} == {"generated-output"}
    assert not any(item.rule == "projection-refresh" for item in plan.required)


def test_plan_uses_merge_base_for_diverged_and_stacked_history(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    common = _commit(root, "common")
    subprocess.run(["git", "-C", str(root), "switch", "-qc", "feature"], check=True)
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return value", "return int(value)"))
    feature = _commit(root, "feature refactor")
    subprocess.run(["git", "-C", str(root), "switch", "-q", "main"], check=True)
    (root / "notes.txt").write_text("main moved\n")
    main_head = _commit(root, "advance main")

    plan = build_impact_plan(
        root, root / ".clean-docs.yml", base=main_head, head=feature
    )

    assert plan.requested_base == main_head
    assert plan.merge_base == common
    assert plan.head == feature
    assert [item.path for item in plan.artifacts] == ["src/api.py"]
