from __future__ import annotations

import json
import subprocess
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

import sourcebound.impact as impact_module
import sourcebound.extractors.inventory as inventory_extractor
from sourcebound import __version__
from sourcebound.cli import main
from sourcebound.impact import build_impact_plan
from sourcebound.snapshot import RepositorySnapshot


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
    (root / ".sourcebound.yml").write_text(
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
    (root / ".sourcebound").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "src/actions.py").write_text(
        'ACTIONS = [{"name": "report", "job": "Report status"}]\n'
    )
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- sourcebound:begin actions -->\n"
        "<!-- sourcebound:end actions -->\n"
    )
    (root / ".sourcebound.yml").write_text(
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
    (root / ".sourcebound/eval.yml").write_text(
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


def _review_contract_repository(
    tmp_path: Path,
    *,
    project: Path = Path("."),
) -> tuple[Path, Path]:
    root = tmp_path / "review-repository"
    project_root = root if project == Path(".") else root / project
    (project_root / "src").mkdir(parents=True)
    (project_root / "docs").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (project_root / "src/stable.py").write_text(
        "def stable_api():\n    return 'stable'\n"
    )
    (project_root / "src/delivery.py").write_text(
        "PAGE_LENGTH = 8000\n"
        "UNRELATED_LIMIT = 10\n\n"
        "class Delivery:\n"
        "    def page(self):\n"
        "        return PAGE_LENGTH\n\n"
        "    def unrelated(self):\n"
        "        return UNRELATED_LIMIT\n"
    )
    (project_root / "README.md").write_text(
        "# Fixture\n\n## API\n\n`stable_api` is the supported entry point.\n"
    )
    (project_root / "docs/delivery.md").write_text(
        "# Delivery\n\n"
        "## Fetching pages\n\n"
        "Fetch the next page from the returned offset.\n"
    )
    (project_root / ".sourcebound.yml").write_text(
        """\
version: 1
bindings:
  - id: stable-api
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/stable.py, symbol: stable_api}
review_contracts:
  - id: delivery-paging
    mode: observe
    sources:
      - id: page-length
        path: src/delivery.py
        extractor: python-symbol
        locator: PAGE_LENGTH
      - id: page-method
        path: src/delivery.py
        extractor: python-symbol
        locator: Delivery.page
    targets:
      - id: fetching-pages
        path: docs/delivery.md
        extractor: markdown-section
        locator: "#fetching-pages"
"""
    )
    return root, project_root


def test_python_interface_fingerprints_request_stable_empty_ast_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_dump = impact_module.ast.dump
    requested: list[bool] = []

    def versioned_dump(
        node: impact_module.ast.AST,
        *,
        include_attributes: bool = False,
        show_empty: bool = False,
    ) -> str:
        requested.append(show_empty)
        return original_dump(node, include_attributes=include_attributes)

    monkeypatch.setattr(impact_module.ast, "dump", versioned_dump)
    node = impact_module.ast.parse(
        "@decorator()\ndef public_api(value: int = 1) -> str:\n    return str(value)\n"
    ).body[0]

    payload = impact_module._python_interface_payload(node)

    assert requested
    assert all(requested)
    assert payload["arguments"]


def test_impact_plan_materializes_each_immutable_revision_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _projection_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/actions.py"
    source.write_text(source.read_text().replace("report", "publish"))
    head = _commit(root, "change action")
    counts: Counter[str] = Counter()
    original = RepositorySnapshot.materialized_root

    @contextmanager
    def counted(
        snapshot: RepositorySnapshot,
        *,
        paths: tuple[Path, ...] = (),
    ) -> Iterator[Path]:
        counts[snapshot.label] += 1
        with original(snapshot, paths=paths) as materialized:
            yield materialized

    monkeypatch.setattr(RepositorySnapshot, "materialized_root", counted)

    plan = build_impact_plan(
        root,
        root / ".sourcebound.yml",
        base=base,
        head=head,
        use_cache=False,
    )

    assert plan.coverage_complete
    assert counts == Counter({base: 1, head: 1})


def test_private_refactor_produces_coverage_complete_stable_no_impact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return value", "return int(value)"))
    head = _commit(root, "refactor private helper")

    first = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)
    second = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert first.as_dict() == second.as_dict()
    assert first.digest == second.digest
    assert first.impact == "none"
    assert first.coverage_complete
    assert first.no_impact
    assert [item.path for item in first.artifacts] == ["src/api.py"]
    assert first.artifacts[0].coverage == "graph-covered"
    assert (
        first.artifacts[0].decision == "traversed accepted documentation relationships"
    )
    assert first.unknown == ()

    assert (
        main(
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
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "sourcebound.impact-plan.v2"
    assert payload["producer"] == {
        "name": "sourcebound",
        "version": __version__,
    }
    assert payload["digest"] == first.digest
    assert payload["no_impact"] is True


def test_review_contract_recommends_review_for_selected_source_change(
    tmp_path: Path,
) -> None:
    root, project_root = _review_contract_repository(tmp_path)
    base = _commit(root, "base")
    source = project_root / "src/delivery.py"
    source.write_text(
        source.read_text().replace(
            "return PAGE_LENGTH",
            "return PAGE_LENGTH // 2",
        )
    )
    head = _commit(root, "change selected source")

    plan = build_impact_plan(
        root,
        project_root / ".sourcebound.yml",
        base=base,
        head=head,
    )

    result = plan.review_contracts[0]
    payload_result = plan.as_dict()["review_contracts"][0]
    assert result.state == "review-recommended"
    assert result.semantic_correctness_checked is False
    assert payload_result["id"] == "delivery-paging"
    assert payload_result["semantic_correctness_checked"] is False
    assert {item.id: item.state for item in result.sources} == {
        "page-length": "unchanged",
        "page-method": "changed",
    }
    assert result.targets[0].state == "unchanged"
    assert plan.impact == "recommended"
    assert plan.coverage_complete
    assert plan.required == ()
    assert plan.unknown == ()
    assert {item.rule for item in plan.recommended} == {"review-contract"}
    source_artifact = next(
        artifact for artifact in plan.artifacts if artifact.path == "src/delivery.py"
    )
    assert source_artifact.coverage == "adapter-covered"
    assert source_artifact.graph_roots == ()
    assert {
        (edge.source, edge.target, edge.kind)
        for edge in plan.edges
        if "review-contract:delivery-paging" in {edge.source, edge.target}
    } == {
        (
            "artifact:src/delivery.py",
            "review-contract:delivery-paging",
            "affects",
        ),
        (
            "review-contract:delivery-paging",
            "artifact:docs/delivery.md",
            "requests-review",
        ),
    }


def test_review_contract_records_relevant_target_cochange_without_claiming_truth(
    tmp_path: Path,
) -> None:
    root, project_root = _review_contract_repository(tmp_path)
    base = _commit(root, "base")
    source = project_root / "src/delivery.py"
    source.write_text(
        source.read_text().replace(
            "return PAGE_LENGTH",
            "return PAGE_LENGTH // 2",
        )
    )
    target = project_root / "docs/delivery.md"
    target.write_text(
        target.read_text().replace(
            "returned offset",
            "returned continuation offset",
        )
    )
    head = _commit(root, "change source and target")

    plan = build_impact_plan(
        root,
        project_root / ".sourcebound.yml",
        base=base,
        head=head,
    )

    result = plan.review_contracts[0]
    assert result.state == "cochanged"
    assert result.semantic_correctness_checked is False
    assert result.targets[0].state == "changed"
    assert not any(finding.rule == "review-contract" for finding in plan.recommended)
    assert plan.impact == "none"
    assert plan.coverage_complete


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("return UNRELATED_LIMIT", "return UNRELATED_LIMIT + 1"),
        ("UNRELATED_LIMIT = 10", "UNRELATED_LIMIT = 11"),
    ],
)
def test_review_contract_ignores_unselected_source_changes(
    tmp_path: Path,
    before: str,
    after: str,
) -> None:
    root, project_root = _review_contract_repository(tmp_path)
    base = _commit(root, "base")
    source = project_root / "src/delivery.py"
    source.write_text(source.read_text().replace(before, after))
    head = _commit(root, "change unrelated source")

    plan = build_impact_plan(
        root,
        project_root / ".sourcebound.yml",
        base=base,
        head=head,
    )

    assert plan.review_contracts[0].state == "unaffected"
    assert not any(finding.rule == "review-contract" for finding in plan.recommended)
    assert plan.impact == "none"
    assert plan.coverage_complete
    artifact = next(item for item in plan.artifacts if item.path == "src/delivery.py")
    assert artifact.coverage == "adapter-covered"
    assert "review-contract:delivery-paging" not in artifact.graph_roots


def test_unknown_review_contract_is_advisory_only(tmp_path: Path) -> None:
    root, project_root = _review_contract_repository(tmp_path)
    base = _commit(root, "base")
    source = project_root / "src/delivery.py"
    source.write_text(
        source.read_text().replace(
            "return PAGE_LENGTH",
            "return PAGE_LENGTH // 2",
        )
    )
    (project_root / "docs/delivery.md").write_text("# Delivery\n")
    head = _commit(root, "remove declared target")

    plan = build_impact_plan(
        root,
        project_root / ".sourcebound.yml",
        base=base,
        head=head,
    )

    assert plan.review_contracts[0].state == "unknown"
    assert plan.impact == "recommended"
    assert plan.coverage_complete
    assert plan.required == ()
    assert plan.unknown == ()
    finding = next(item for item in plan.recommended if item.rule == "review-contract")
    assert finding.classification == "recommended"
    assert finding.obligations == ("review-declared-targets",)


def test_review_contract_keeps_result_paths_project_relative(
    tmp_path: Path,
) -> None:
    project = Path("packages/widget")
    root, project_root = _review_contract_repository(
        tmp_path,
        project=project,
    )
    base = _commit(root, "base")
    source = project_root / "src/delivery.py"
    source.write_text(
        source.read_text().replace(
            "return PAGE_LENGTH",
            "return PAGE_LENGTH // 2",
        )
    )
    head = _commit(root, "change selected project source")

    plan = build_impact_plan(
        root,
        project_root / ".sourcebound.yml",
        base=base,
        head=head,
        project=project,
    )

    result = plan.review_contracts[0]
    assert {item.path for item in result.sources} == {"src/delivery.py"}
    assert {item.path for item in result.targets} == {"docs/delivery.md"}
    assert {item.path for item in plan.artifacts} == {"packages/widget/src/delivery.py"}
    finding = next(item for item in plan.recommended if item.rule == "review-contract")
    assert set(finding.paths) == {
        "packages/widget/src/delivery.py",
        "packages/widget/docs/delivery.md",
    }
    assert (
        "artifact:packages/widget/src/delivery.py",
        "review-contract:delivery-paging",
        "affects",
    ) in {(edge.source, edge.target, edge.kind) for edge in plan.edges}


def test_public_implementation_refactor_does_not_become_interface_work(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(
        source.read_text().replace("return timeout", "return int(timeout)")
    )
    head = _commit(root, "refactor public implementation")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "none"
    assert not any(event.kind == "public-symbol-changed" for event in plan.events)
    assert {item.rule for item in plan.unrelated} == {"no-public-contract-delta"}


def test_unparseable_supported_source_is_unknown(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/broken.py"
    source.write_text("def public_api(\n")
    head = _commit(root, "break source syntax")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert plan.artifacts[0].adapter == "python-ast:failed"
    assert plan.artifacts[0].coverage == "unknown"
    assert {item.rule for item in plan.unknown} == {"unsupported-public-candidate"}


def test_unsupported_public_candidate_is_unknown_not_no_impact(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    (root / "src/Service.java").write_text(
        "public final class Service { public void start() {} }\n"
    )
    head = _commit(root, "add unsupported public service")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

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

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "none"
    assert plan.artifacts[0].coverage == "unrelated-covered"
    assert {item.rule for item in plan.unrelated} == {"no-public-contract-delta"}


def test_valid_mdx_change_is_classified_as_a_direct_document_change(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    mdx = root / "docs/guide.mdx"
    mdx.parent.mkdir()
    mdx.write_text("# Guide\n\n<Callout>Old behavior</Callout>\n")
    base = _commit(root, "base")
    mdx.write_text("# Guide\n\n<Callout>New behavior</Callout>\n")
    head = _commit(root, "change unsupported MDX")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)
    payload = plan.as_dict()

    assert plan.impact == "none"
    assert plan.coverage_complete
    assert plan.unsupported_documents == ()
    assert payload["unsupported_documents"] == []
    assert plan.artifacts[0].adapter == "mdx-static"
    assert plan.artifacts[0].coverage == "document-direct"
    assert {item.rule for item in plan.unrelated} == {"direct-document-change"}


def test_malformed_mdx_change_is_unknown_and_disclosed(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    mdx = root / "docs/guide.mdx"
    mdx.parent.mkdir()
    mdx.write_text("# Guide\n\n<Callout>Old behavior</Callout>\n")
    base = _commit(root, "base")
    mdx.write_text("# Guide\n\n<Callout>New behavior\n")
    head = _commit(root, "break MDX")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert not plan.coverage_complete
    assert plan.unsupported_documents == ("docs/guide.mdx",)
    assert plan.artifacts[0].adapter == "mdx-static:failed"
    assert plan.artifacts[0].coverage == "unknown"
    assert {item.rule for item in plan.unknown} == {"unsupported-document-format"}


def test_document_line_moves_do_not_invent_semantic_events(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    readme = root / "README.md"
    readme.write_text(readme.read_text() + "\nSee [the source](src/api.py).\n")
    base = _commit(root, "base")
    readme.write_text(
        readme.read_text().replace(
            "\nSee [the source]", "\nRead this first.\n\nSee [the source]"
        )
    )
    head = _commit(root, "move link down")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "none"
    assert plan.events == ()
    assert plan.artifacts[0].coverage == "graph-covered"
    assert {item.rule for item in plan.unrelated} == {"no-public-contract-delta"}


def test_unsupported_runtime_control_is_unknown(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    (root / "Dockerfile").write_text("FROM python:3.14\n")
    head = _commit(root, "change runtime container")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert plan.artifacts[0].may_expose_public_surface
    assert {item.rule for item in plan.unknown} == {"unsupported-public-candidate"}


def test_makefile_comment_change_is_supported_and_has_no_public_impact(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    makefile = root / "Makefile"
    makefile.write_text("# Run the suite.\ntest:\n\tpython -m pytest\n")
    base = _commit(root, "add make target")
    makefile.write_text(makefile.read_text().replace("Run the suite", "Run all tests"))
    head = _commit(root, "clarify make target comment")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "none"
    assert plan.coverage_complete
    assert plan.events == ()
    assert plan.artifacts[0].adapter == "makefile-static"
    assert plan.artifacts[0].coverage == "adapter-covered"


def test_makefile_recipe_change_emits_a_public_target_event(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    with (root / ".sourcebound.yml").open("a") as manifest:
        manifest.write(
            "  - id: repository-surface\n"
            "    type: region\n"
            "    doc: docs/SURFACE.md\n"
            "    region: repository-surface\n"
            "    extractor: repository-overview\n"
            "    source: {path: .}\n"
            "    renderer: markdown-fragment\n"
        )
    makefile = root / "Makefile"
    makefile.write_text(
        ".PHONY: test\nPYTHON := python3\n"
        "test: MODE = full\ntest:\n\t$(PYTHON) -m pytest\n"
        "docker/build:\n\tdocker build .\n"
    )
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "add make target")
    makefile.write_text(makefile.read_text().replace("python3", "pypy3"))
    head = _commit(root, "change referenced make variable")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "recommended"
    assert plan.coverage_complete
    assert {event.kind for event in plan.events} == {"make-target-changed"}
    assert {event.locator for event in plan.events} == {"test"}
    assert plan.artifacts[0].adapter == "makefile-static"
    assert {item.rule for item in plan.recommended} == {"public-contract-change"}


def test_dynamic_makefile_stays_unknown_instead_of_claiming_static_coverage(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    (root / "Makefile").write_text(
        "include generated.mk\n$(PUBLIC_TARGET):\n\t@true\n"
    )
    head = _commit(root, "add dynamic make target")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert plan.artifacts[0].adapter == "makefile-static:failed"
    assert {item.rule for item in plan.unknown} == {"unsupported-public-candidate"}


def test_dynamic_makefile_base_cannot_be_hidden_by_a_static_head(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    makefile = root / "Makefile"
    makefile.write_text("include generated.mk\n$(PUBLIC_TARGET):\n\t@true\n")
    base = _commit(root, "add dynamic make target")
    makefile.write_text("test:\n\tpython -m pytest\n")
    head = _commit(root, "replace dynamic target with static target")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert plan.artifacts[0].adapter == "makefile-static:failed"


def test_unrelated_make_assignment_change_is_unknown_semantic_residue(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    makefile = root / "Makefile"
    makefile.write_text("UNUSED := one\ntest:\n\tpython -m pytest\n")
    base = _commit(root, "add make target")
    makefile.write_text(makefile.read_text().replace("UNUSED := one", "UNUSED := two"))
    head = _commit(root, "change untraced make variable")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert plan.artifacts[0].adapter == "makefile-static:failed"
    assert {item.rule for item in plan.unknown} == {"unsupported-public-candidate"}


def test_make_target_event_cannot_hide_unaccounted_semantic_residue(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    with (root / ".sourcebound.yml").open("a") as manifest:
        manifest.write(
            "  - id: repository-surface\n"
            "    type: region\n"
            "    doc: docs/SURFACE.md\n"
            "    region: repository-surface\n"
            "    extractor: repository-overview\n"
            "    source: {path: .}\n"
            "    renderer: markdown-fragment\n"
        )
    makefile = root / "Makefile"
    makefile.write_text(
        "PYTHON := python3\nUNUSED := one\ntest:\n\t$(PYTHON) -m pytest\n"
    )
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "add make target")
    makefile.write_text(
        makefile.read_text()
        .replace("PYTHON := python3", "PYTHON := pypy3")
        .replace("UNUSED := one", "UNUSED := two")
    )
    head = _commit(root, "change traced and untraced make variables")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert not plan.coverage_complete
    assert {event.locator for event in plan.events} == {"test"}
    assert plan.artifacts[0].adapter == "makefile-static:failed"
    assert {item.rule for item in plan.unknown} == {"unsupported-public-candidate"}


@pytest.mark.parametrize("operation", ["add", "remove"])
def test_unchanged_assignment_can_move_into_or_out_of_target_evidence(
    tmp_path: Path, operation: str
) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    with (root / ".sourcebound.yml").open("a") as manifest:
        manifest.write(
            "  - id: repository-surface\n"
            "    type: region\n"
            "    doc: docs/SURFACE.md\n"
            "    region: repository-surface\n"
            "    extractor: repository-overview\n"
            "    source: {path: .}\n"
            "    renderer: markdown-fragment\n"
        )
    makefile = root / "Makefile"
    assignment = "PYTHON := python3\n"
    target = "test:\n\t$(PYTHON) -m pytest\n"
    makefile.write_text(assignment + (target if operation == "remove" else ""))
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "base make state")
    makefile.write_text(assignment + (target if operation == "add" else ""))
    head = _commit(root, f"{operation} make target")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact in {"recommended", "required"}
    assert plan.coverage_complete
    assert plan.unknown == ()
    expected_kind = "make-target-added" if operation == "add" else "make-target-removed"
    assert {event.kind for event in plan.events} == {expected_kind}
    assert plan.artifacts[0].adapter == "makefile-static"


@pytest.mark.parametrize("operation", ["add", "remove"])
def test_phony_only_target_is_visible_across_makefile_lifecycle(
    tmp_path: Path, operation: str
) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    with (root / ".sourcebound.yml").open("a") as manifest:
        manifest.write(
            "  - id: repository-surface\n"
            "    type: region\n"
            "    doc: docs/SURFACE.md\n"
            "    region: repository-surface\n"
            "    extractor: repository-overview\n"
            "    source: {path: .}\n"
            "    renderer: markdown-fragment\n"
        )
    makefile = root / "Makefile"
    if operation == "remove":
        makefile.write_text(".PHONY: ghost\n")
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "base makefile lifecycle")
    if operation == "add":
        makefile.write_text(".PHONY: ghost\n")
    else:
        makefile.unlink()
    head = _commit(root, f"{operation} phony-only makefile")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    expected_kind = "make-target-added" if operation == "add" else "make-target-removed"
    assert plan.coverage_complete
    assert plan.unknown == ()
    assert {event.kind for event in plan.events} == {expected_kind}
    assert {event.locator for event in plan.events} == {"ghost"}


def test_makefile_path_target_recipe_change_is_a_public_event(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    with (root / ".sourcebound.yml").open("a") as manifest:
        manifest.write(
            "  - id: repository-surface\n"
            "    type: region\n"
            "    doc: docs/SURFACE.md\n"
            "    region: repository-surface\n"
            "    extractor: repository-overview\n"
            "    source: {path: .}\n"
            "    renderer: markdown-fragment\n"
        )
    makefile = root / "Makefile"
    makefile.write_text("docker/build:\n\tdocker build .\n")
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "add path target")
    makefile.write_text("docker/build:\n\tdocker build --pull .\n")
    head = _commit(root, "change path target")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "recommended"
    assert {event.locator for event in plan.events} == {"docker/build"}


def test_workflow_job_change_is_supported_advisory_impact(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    with (root / ".sourcebound.yml").open("a") as manifest:
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

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "recommended"
    assert plan.coverage_complete
    assert plan.required == ()
    assert plan.artifacts[0].adapter == "github-actions-static"
    assert {event.kind for event in plan.events} == {"ci-job-changed"}
    assert {item.rule for item in plan.recommended} == {"public-contract-change"}


def test_workflow_path_filter_is_unknown_without_a_run_receipt(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    guide = root / "docs/guide.md"
    guide.parent.mkdir()
    guide.write_text("# Guide\n\nFirst version.\n")
    workflow = root / ".github/workflows/specialized.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: Specialized\n"
        "on:\n"
        "  pull_request:\n"
        "    paths: ['src/**']\n"
        "jobs:\n"
        "  contract:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: python -m pytest tests/test_contract.py\n"
    )
    base = _commit(root, "add specialized workflow")
    guide.write_text("# Guide\n\nChanged procedure.\n")
    head = _commit(root, "change documentation procedure")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    finding = next(
        item for item in plan.unknown if item.rule == "ci-path-filter-unverified"
    )
    assert plan.impact == "unknown"
    assert finding.paths == (".github/workflows/specialized.yml", "docs/guide.md")
    assert finding.obligations == ("verify-specialized-ci-run",)
    assert "docs/guide.md" in finding.message


def test_impact_reuses_changed_inventory_for_repository_overview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _symbol_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/SURFACE.md").write_text(
        "# Surface\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    with (root / ".sourcebound.yml").open("a") as manifest:
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
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(
        source.read_text().replace("return timeout", "return int(timeout)")
    )
    head = _commit(root, "refactor implementation")

    def unexpected_rescan(_root: Path) -> object:
        raise AssertionError("repository-overview rescanned the head inventory")

    monkeypatch.setattr(inventory_extractor, "scan_inventory", unexpected_rescan)

    plan = build_impact_plan(
        root,
        root / ".sourcebound.yml",
        base=base,
        head=head,
        use_cache=False,
    )

    assert plan.impact == "none"


def test_malformed_workflow_cannot_become_no_impact(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    workflow = root / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("jobs: [not-a-mapping]\n")
    head = _commit(root, "add malformed workflow")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "unknown"
    assert plan.artifacts[0].adapter == "github-actions-static:failed"
    assert {item.rule for item in plan.unknown} == {"unsupported-public-candidate"}


def test_public_default_change_reaches_reference_and_migration_obligations(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(
        source.read_text().replace("timeout: int = 5", "timeout: int = 10")
    )
    head = _commit(root, "change public default")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "required"
    event = next(item for item in plan.events if item.kind == "public-symbol-changed")
    assert event.coverage == "bound"
    finding = next(
        item for item in plan.required if item.rule == "public-contract-change"
    )
    assert finding.obligations == ("review-migration", "review-reference")
    assert "binding:public-api" in finding.graph_roots


def test_typescript_signature_change_is_public_interface_work(
    tmp_path: Path,
) -> None:
    root = tmp_path / "typescript-repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "src/api.ts").write_text(
        "export interface PromptOptions {\n  version?: number\n}\n"
    )
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- sourcebound:begin repository-surface -->\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    (root / ".sourcebound.yml").write_text(
        """\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-overview
    source: {path: .}
    renderer: markdown-fragment
"""
    )
    (root / ".sourcebound-ignore.yml").write_text(
        """\
version: 1
ignore:
  - id: api-symbol:src/api.ts:PromptOptions
    reason: Public API reference is maintained outside this fixture.
"""
    )
    assert main(["--root", str(root), "derive", "--write"]) == 0
    base = _commit(root, "base")
    source = root / "src/api.ts"
    source.write_text(
        source.read_text().replace(
            "  version?: number\n", "  version?: number\n  label?: string\n"
        )
    )
    head = _commit(root, "add TypeScript interface member")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "none"
    event = next(item for item in plan.events if item.kind == "public-symbol-changed")
    assert event.coverage == "ignored"
    assert {item.rule for item in plan.unrelated} == {"ignored-public-contract"}


def test_binding_change_traverses_projection_and_evaluation(
    tmp_path: Path,
) -> None:
    root = _projection_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/actions.py"
    source.write_text(source.read_text().replace("report", "publish"))
    head = _commit(root, "rename action")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

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


def test_explicit_only_llms_context_does_not_refresh_for_an_excluded_binding(
    tmp_path: Path,
) -> None:
    root = _projection_repository(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/CANONICAL.md").write_text("# Canonical\n\nFixed context.\n")
    manifest = root / ".sourcebound.yml"
    manifest.write_text(
        manifest.read_text().replace(
            "    output: llms.txt\n    include: [README.md]",
            "    output: llms.txt\n    include_bound: false\n    include: [docs/CANONICAL.md]",
        )
    )
    assert main(["--root", str(root), "project"]) == 0
    base = _commit(root, "use explicit-only context")
    source = root / "src/actions.py"
    source.write_text(source.read_text().replace("report", "publish"))
    head = _commit(root, "rename action")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert "binding-drift" in {item.rule for item in plan.required}
    assert "projection-refresh" not in {item.rule for item in plan.required}


def test_generated_projection_change_does_not_trigger_itself(
    tmp_path: Path,
) -> None:
    root = _projection_repository(tmp_path)
    base = _commit(root, "base")
    projection = root / "llms.txt"
    projection.write_text(projection.read_text() + "\nmanual edit\n")
    head = _commit(root, "touch generated projection")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert plan.impact == "none"
    assert plan.coverage_complete
    assert plan.artifacts[0].coverage == "generated"
    assert {item.rule for item in plan.unrelated} == {"generated-output"}
    assert not any(item.rule == "projection-refresh" for item in plan.required)


def test_visual_record_change_triggers_both_audience_projections(
    tmp_path: Path,
) -> None:
    root = _projection_repository(tmp_path)
    (root / "docs/visuals").mkdir(parents=True)
    (root / "docs/assets").mkdir(parents=True)
    (root / "docs/assets/queue.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    record = root / "docs/visuals/queue-flow.yml"
    record.write_text(
        """\
schema: sourcebound.visual.v1
id: queue-flow
kind: diagram
src: docs/assets/queue.png
width: 1200
height: 800
alt: Queue A sends work to queue B
caption: Work moves from queue A to queue B.
description: Queue A validates each item, then sends accepted work to queue B.
annotations: []
"""
    )
    manifest = root / ".sourcebound.yml"
    manifest.write_text(
        manifest.read_text()
        + """\
  visuals:
    - id: queue-flow
      source: docs/visuals/queue-flow.yml
      human_output: docs/generated/queue-flow.mdx
      agent_output: .sourcebound/visuals/queue-flow.md
"""
    )
    assert main(["--root", str(root), "project"]) == 0
    base = _commit(root, "add visual")
    record.write_text(
        record.read_text().replace("sends accepted work", "sends validated work")
    )
    head = _commit(root, "clarify visual")

    plan = build_impact_plan(root, root / ".sourcebound.yml", base=base, head=head)

    assert {item.rule for item in plan.required} >= {"projection-refresh"}
    assert {
        edge.target
        for edge in plan.edges
        if edge.kind == "projects-to"
        and edge.source == "artifact:docs/visuals/queue-flow.yml"
    } == {
        "projection:.sourcebound/visuals/queue-flow.md",
        "projection:docs/generated/queue-flow.mdx",
    }


def test_public_disposition_is_limited_to_one_historical_finding(
    tmp_path: Path,
) -> None:
    root = tmp_path / "retired-command-repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "src/api.py").write_text("def current_entry():\n    return 1\n")
    (root / "README.md").write_text(
        "# Fixture\n\n## API\n\nRun `current-entry` after installation.\n"
    )
    manifest = root / ".sourcebound.yml"
    manifest.write_text(
        """\
version: 1
bindings:
  - id: current-api
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/api.py, symbol: current_entry}
"""
    )
    (root / "pyproject.toml").write_text(
        "[project.scripts]\nhistoric-entry = 'fixture:main'\n"
    )
    base = _commit(root, "base public command")
    (root / "pyproject.toml").write_text(
        "[project.scripts]\ncurrent-entry = 'fixture:main'\n"
    )
    (root / ".sourcebound-ignore.yml").write_text(
        """\
version: 1
ignore:
  - id: cli-command:pyproject.toml:project.scripts.current-entry
    reason: This fixture records the current command in README.md.
"""
    )
    first_head = _commit(root, "rename public command")
    first = build_impact_plan(root, manifest, base=base, head=first_head)
    manifest.write_text(
        manifest.read_text()
        + f"""\
public_dispositions:
  - base: {base}
    kind: event
    subject: {next(item.id for item in first.events if item.kind == "command-removed")}
    documentation: README.md
    replacement: current-entry
    reason: The installation page names the supported command after the rename.
"""
    )
    head = _commit(root, "record command migration")

    plan = build_impact_plan(root, manifest, base=base, head=head)

    assert plan.coverage_complete
    assert not plan.unknown
    disposition = next(
        item for item in plan.unrelated if item.rule == "declared-public-disposition"
    )
    assert "README.md" in disposition.message
    assert "current-entry" in disposition.message


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
        root, root / ".sourcebound.yml", base=main_head, head=feature
    )

    assert plan.requested_base == main_head
    assert plan.merge_base == common
    assert plan.head == feature
    assert [item.path for item in plan.artifacts] == ["src/api.py"]
