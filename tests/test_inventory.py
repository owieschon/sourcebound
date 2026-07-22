from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from sourcebound.cli import main
from sourcebound.engine import evaluate, write_results
from sourcebound.errors import ConfigurationError
from sourcebound.extractors.inventory import (
    _extract_repository_overview_legacy,
    _inventory_rows_from_items,
)
from sourcebound.inventory import (
    InventoryItem,
    _makefile_is_statically_classifiable,
    scan_inventory,
)
from sourcebound.manifest import load_manifest
from sourcebound.models import RegionBinding
from sourcebound.regions import replace_region
from sourcebound.renderers import render
from sourcebound.snapshot import RepositorySnapshot


def test_inventory_does_not_promote_test_harness_arguments_to_public_cli(tmp_path: Path) -> None:
    root = tmp_path / "test-harness-surface"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "runner.py").write_text(
        "parser.add_parser('private-run')\nparser.add_argument('--private-flag')\n"
    )
    report = scan_inventory(root)
    assert not [
        item for item in report.items
        if item.kind in {"cli-command", "cli-option"} and item.source == "tests/runner.py"
    ]


def _python_repo(tmp_path: Path) -> Path:
    root = tmp_path / "python-repo"
    (root / "src/service").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    (root / "schemas").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture-service"\nversion = "1.2.3"\n'
        'requires-python = ">=3.11"\n'
        '[project.scripts]\nfixture = "service.cli:main"\n'
    )
    (root / "src/service/cli.py").write_text("""\
raise RuntimeError("inventory must not import this module")

def public_api():
    return True

@server.tool()
def inspect_account():
    return True

sub = parser.add_subparsers()
sub.add_parser("serve")
parser.add_argument("--port")
""")
    (root / "noxfile.py").write_text("def internal_build_task():\n    return True\n")
    (root / "tests/test_cli.py").write_text("def test_cli():\n    assert True\n")
    (root / "docs/guide.md").write_text("# Guide\n\n[Schema](../schemas/item.schema.json)\n")
    (root / "schemas/item.schema.json").write_text(
        json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Item"})
    )
    (root / "openapi.yaml").write_text("""\
openapi: 3.1.0
paths:
  /items:
    get:
      operationId: listItems
""")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


def test_python_inventory_is_static_typed_and_deterministic(tmp_path: Path) -> None:
    root = _python_repo(tmp_path)

    first = scan_inventory(root)
    second = scan_inventory(root)

    assert first == second
    assert first.languages == ("Python",)
    assert {
        "api-endpoint",
        "api-symbol",
        "cli-command",
        "cli-option",
        "doc-link",
        "document",
        "mcp-tool",
        "package",
        "runtime-constraint",
        "schema",
        "test-suite",
    } <= {item.kind for item in first.items}
    assert all(item.coverage == "standard-gap" for item in first.items)
    assert all(len(item.digest) == 64 for item in first.items)
    assert any(item.kind == "cli-command" and item.name == "fixture" for item in first.items)
    assert any(
        item.kind == "runtime-constraint" and item.name == "Python >=3.11"
        for item in first.items
    )
    assert not any(item.name == "internal_build_task" for item in first.items)
    public_api = next(item for item in first.items if item.name == "public_api")
    assert public_api.digest == hashlib.sha256(
        b"def public_api():\n    return True"
    ).hexdigest()


def test_repository_overview_reuse_excludes_plugin_inventory() -> None:
    core = InventoryItem(
        "api-symbol:src/api.py:serve",
        "api-symbol",
        "serve",
        "src/api.py",
        "serve",
        "python-ast",
        "a" * 64,
        "cataloged",
    )
    plugin = InventoryItem(
        "api-symbol:plugin.py:invented",
        "api-symbol",
        "invented",
        "plugin.py",
        "invented",
        "plugin:fixture",
        "b" * 64,
        "standard-gap",
    )

    rows = _inventory_rows_from_items((plugin, core))

    assert [row["name"] for row in rows] == ["serve"]


def test_typescript_package_inventory_needs_no_project_execution(tmp_path: Path) -> None:
    root = tmp_path / "typescript-repo"
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({
        "name": "fixture-cli",
        "version": "2.0.0",
        "bin": {"fixture": "dist/cli.js"},
        "scripts": {"test": "vitest run", "build": "tsc", "//note": "not a script"},
        "type": "module",
        "engines": {"node": ">=20"},
    }))
    (root / "src/index.ts").write_text(
        "throw new Error('must not execute');\nexport function start() { return true }\n"
    )
    (root / "src/index.test.ts").write_text("export const caseName = 'start';\n")

    report = scan_inventory(root)

    assert report.languages == ("TypeScript",)
    by_kind = {item.kind: item for item in report.items}
    assert by_kind["package"].name == "fixture-cli"
    assert by_kind["cli-command"].name == "fixture"
    assert by_kind["test-runner"].name == "test"
    assert {
        item.name for item in report.items if item.kind == "runtime-constraint"
    } == {"ES modules", "node >=20"}
    assert any(item.kind == "api-symbol" and item.name == "start" for item in report.items)
    assert any(item.kind == "test-suite" for item in report.items)
    assert not any(item.name == "//note" for item in report.items)


def test_makefile_inventory_is_static_and_ignores_comments_and_special_rules(
    tmp_path: Path,
) -> None:
    root = tmp_path / "make-repo"
    root.mkdir()
    makefile = root / "Makefile"
    makefile.write_text(
        "# Public development commands.\n"
        ".PHONY: test build\n"
        "PYTHON := python\n\n"
        "test: MODE = full\n"
        "test build:\n"
        "\t$(PYTHON) -m pytest\n\n"
        "docker/build:\n"
        "\tdocker build .\n"
    )

    first = scan_inventory(root)
    targets = [item for item in first.items if item.kind == "make-target"]
    assert {(item.name, item.adapter) for item in targets} == {
        ("build", "makefile-static"),
        ("docker/build", "makefile-static"),
        ("test", "makefile-static"),
    }

    before = {item.name: item.digest for item in targets}
    makefile.write_text(makefile.read_text().replace("# Public", "# Supported"))
    comment_only = {
        item.name: item.digest
        for item in scan_inventory(root).items
        if item.kind == "make-target"
    }
    assert comment_only == before

    makefile.write_text(makefile.read_text().replace("PYTHON := python", "PYTHON := pypy3"))
    recipe_change = {
        item.name: item.digest
        for item in scan_inventory(root).items
        if item.kind == "make-target"
    }
    assert recipe_change.keys() == before.keys()
    assert recipe_change["test"] != before["test"]
    assert recipe_change["build"] != before["build"]
    assert recipe_change["docker/build"] == before["docker/build"]

    before_phony = recipe_change
    makefile.write_text(makefile.read_text().replace(".PHONY: test build", ".PHONY: build"))
    after_phony = {
        item.name: item.digest
        for item in scan_inventory(root).items
        if item.kind == "make-target"
    }
    assert after_phony["test"] != before_phony["test"]
    assert after_phony["build"] == before_phony["build"]
    assert _makefile_is_statically_classifiable(makefile.read_text())
    assert not _makefile_is_statically_classifiable(
        "include generated.mk\n$(PUBLIC_TARGET):\n\t@true\n"
    )
    assert not _makefile_is_statically_classifiable(
        "ifeq ($(MODE),release)\nship:\n\t@true\nendif\n"
    )
    assert not _makefile_is_statically_classifiable("%.o: %.c\n\tcc -c $<\n")
    assert not _makefile_is_statically_classifiable("\t@echo orphan\n")

    phony_only = tmp_path / "phony-only"
    phony_only.mkdir()
    (phony_only / "Makefile").write_text(".PHONY: ghost\n")
    ghost = next(
        item
        for item in scan_inventory(phony_only).items
        if item.kind == "make-target"
    )
    assert ghost.name == "ghost"

    separated_recipe = tmp_path / "comment-separated"
    separated_recipe.mkdir()
    separated_makefile = separated_recipe / "Makefile"
    separated_makefile.write_text("test:\n# Why this runs.\n\t@echo one\n")
    before_recipe = next(
        item for item in scan_inventory(separated_recipe).items
        if item.kind == "make-target"
    )
    separated_makefile.write_text(
        separated_makefile.read_text().replace("echo one", "echo two")
    )
    after_recipe = next(
        item for item in scan_inventory(separated_recipe).items
        if item.kind == "make-target"
    )
    assert before_recipe.digest != after_recipe.digest


def test_node_monorepo_and_registered_mcp_tools_are_discovered_statically(
    tmp_path: Path,
) -> None:
    root = tmp_path / "monorepo"
    (root / "packages/api/src").mkdir(parents=True)
    (root / "packages/worker/runtime").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({
        "name": "workspace-root",
        "private": True,
        "workspaces": ["packages/*"],
    }))
    (root / "packages/api/package.json").write_text(json.dumps({
        "name": "@fixture/api",
        "version": "1.0.0",
        "scripts": {"test": "vitest run"},
    }))
    (root / "packages/worker/runtime/package.json").write_text(json.dumps({
        "name": "fixture-worker",
        "version": "1.0.0",
        "scripts": {"deploy": "worker deploy"},
    }))
    (root / "packages/api/src/server.ts").write_text(
        "server.registerTool('resolve_account', {}, handler);\n"
        "server.tool('get_account', {}, handler);\n"
    )

    report = scan_inventory(root)

    assert {
        (item.name, item.source)
        for item in report.items
        if item.kind == "package"
    } == {
        ("workspace-root", "package.json"),
        ("@fixture/api", "packages/api/package.json"),
        ("fixture-worker", "packages/worker/runtime/package.json"),
    }
    assert {
        item.name for item in report.items if item.kind == "mcp-tool"
    } == {"resolve_account", "get_account"}


def test_typescript_declaration_exports_are_discovered_statically(tmp_path: Path) -> None:
    root = tmp_path / "typescript-declarations"
    root.mkdir()
    (root / "index.d.ts").write_text(
        "export default class Queue<Value> {}\n"
        "export interface QueueOptions {}\n"
        "export type QueueSize = number\n"
    )
    (root / "index.js").write_text("export default class Queue {}\n")

    report = scan_inventory(root)

    symbols = {
        (item.name, item.adapter)
        for item in report.items
        if item.kind == "api-symbol"
    }
    assert symbols == {
        ("Queue", "typescript-static"),
        ("QueueOptions", "typescript-static"),
        ("QueueSize", "typescript-static"),
    }


def test_inventory_cli_reports_coverage_and_repository_binding_repairs_docs(
    tmp_path: Path, capsys
) -> None:
    root = _python_repo(tmp_path)
    assert main(["--root", str(root), "inventory", "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"]["standard-gap"] == len(report["items"])

    (root / "README.md").write_text(
        "# Fixture\n\n<!-- sourcebound:begin repository-surface -->\nstale\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    manifest = root / ".sourcebound.yml"
    manifest.write_text("""\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-inventory
    source: {path: .}
    renderer: markdown-table
    columns: [kind, name, source, locator]
""")
    results = evaluate(root, manifest)
    assert results[0].changed is True
    assert "| cli-command | serve | src/service/cli.py | serve |" in results[0].expected
    write_results(root, results)
    assert not any(result.changed for result in evaluate(root, manifest))
    assert all(item.coverage == "cataloged" for item in scan_inventory(root).items)

    ignored_id = scan_inventory(root).items[0].id
    (root / ".sourcebound-ignore.yml").write_text(
        f"version: 1\nignore:\n  - id: {json.dumps(ignored_id)}\n"
        "    reason: This surface is internal to the fixture.\n"
    )
    ignored = next(item for item in scan_inventory(root).items if item.id == ignored_id)
    assert ignored.coverage == "ignored"


def test_direct_policy_rejects_selected_catalog_only_surface(tmp_path: Path) -> None:
    root = _python_repo(tmp_path)
    (root / ".sourcebound.yml").write_text("""\
version: 1
bindings:
  - id: catalog
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-inventory
    source: {path: .}
    renderer: markdown-table
    columns: [kind, name, source, locator]
""")
    (root / ".sourcebound-ignore.yml").write_text("""\
version: 2
ignore: []
require_direct:
  - id: public-cli
    kinds: [cli-command]
    paths: [src/service/**]
""")
    report = scan_inventory(root)
    assert report.direct_policy and report.direct_policy.configured
    assert report.direct_policy.gaps
    assert {gap.selector for gap in report.direct_policy.gaps} == {"public-cli"}


def test_direct_policy_accepts_direct_binding_and_exact_reasoned_ignore(
    tmp_path: Path,
) -> None:
    root = _python_repo(tmp_path)
    manifest = root / ".sourcebound.yml"
    manifest.write_text(
        """\
version: 1
bindings:
  - id: serve-command
    type: symbol
    doc: docs/guide.md
    anchor: guide
    source: {path: src/service/cli.py, symbol: serve}
"""
    )
    policy = root / ".sourcebound-ignore.yml"
    policy.write_text(
        """\
version: 2
ignore: []
require_direct:
  - id: public-cli
    kinds: [cli-command]
    paths: [src/service/**]
"""
    )

    report = scan_inventory(root)

    assert report.direct_policy is not None
    assert report.direct_policy.required == 1
    assert report.direct_policy.satisfied == 1
    assert report.direct_policy.complete is True

    command = next(item for item in report.items if item.name == "serve")
    policy.write_text(
        f"""\
version: 2
ignore:
  - id: {command.id}
    reason: The generated service command is intentionally catalog-only here.
require_direct:
  - id: public-cli
    kinds: [cli-command]
    paths: [src/service/**]
"""
    )
    manifest.unlink()

    ignored_report = scan_inventory(root)

    assert ignored_report.direct_policy is not None
    assert ignored_report.direct_policy.complete is True
    assert (
        next(item for item in ignored_report.items if item.id == command.id).coverage
        == "ignored"
    )


@pytest.mark.parametrize(
    ("policy", "message"),
    [
        (
            """\
version: 2
ignore: []
require_direct:
  - id: no-match
    kinds: [cli-command]
    paths: [missing/**]
""",
            "matches no inventory items",
        ),
        (
            """\
version: 2
ignore: []
require_direct:
  - id: documents-are-not-a-direct-policy-kind
    kinds: [document]
""",
            "invalid kinds",
        ),
        (
            """\
version: 2
ignore: []
require_direct:
  - id: parent-path
    kinds: [cli-command]
    paths: [../src/**]
""",
            "invalid paths",
        ),
    ],
)
def test_direct_policy_rejects_stale_or_unsupported_selectors(
    tmp_path: Path,
    policy: str,
    message: str,
) -> None:
    root = _python_repo(tmp_path)
    (root / ".sourcebound-ignore.yml").write_text(policy)

    with pytest.raises(ConfigurationError, match=message):
        scan_inventory(root)


def test_repository_overview_stays_compact_and_tracks_the_full_catalog(
    tmp_path: Path,
) -> None:
    root = tmp_path / "large-repository"
    source = root / "src/package"
    source.mkdir(parents=True)
    for index in range(200):
        (source / f"module_{index}.py").write_text(
            f"def surface_{index}():\n    return {index}\n"
        )
    readme = root / "README.md"
    readme.write_text(
        "# Large repository\n\n"
        "<!-- sourcebound:begin repository-surface -->\nstale\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    manifest = root / ".sourcebound.yml"
    manifest.write_text("""\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-overview
    source: {path: .}
    renderer: markdown-fragment
""")

    first = evaluate(root, manifest)[0]
    assert first.changed
    assert first.provenance.extractor == "repository-overview@2"
    assert "| api-symbol | 200 |" in first.expected
    assert "and 197 more" in first.expected
    assert len(first.expected.splitlines()) < 15
    write_results(root, [first])
    before = readme.read_text()

    (source / "module_199.py").write_text("def zzzz_replacement():\n    return 199\n")
    second = evaluate(root, manifest)[0]

    assert second.changed
    assert before.split("<!-- sourcebound:inventory-sha256", 1)[0] == (
        second.expected.split("<!-- sourcebound:inventory-sha256", 1)[0]
    )


def test_repository_overview_accepts_legacy_receipts_until_surface_changes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "legacy-overview"
    source = root / "src"
    source.mkdir(parents=True)
    (source / "api.py").write_text("def publish():\n    return True\n")
    readme = root / "README.md"
    readme.write_text(
        "# Surface\n\n"
        "<!-- sourcebound:begin repository-surface -->\n"
        "stale\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    manifest = root / ".sourcebound.yml"
    manifest.write_text("""\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-overview
    source: {path: .}
    renderer: markdown-fragment
""")
    binding = load_manifest(manifest).bindings[0]
    assert isinstance(binding, RegionBinding)
    evidence = _extract_repository_overview_legacy(
        RepositorySnapshot(root), binding
    )
    readme.write_text(
        replace_region(readme.read_text(), binding.region, render(evidence, binding))
    )

    accepted = evaluate(root, manifest)[0]
    assert not accepted.changed
    assert accepted.provenance.extractor == "repository-overview@1"

    (source / "api.py").write_text("def distribute():\n    return True\n")
    changed = evaluate(root, manifest)[0]
    assert changed.changed
    assert changed.provenance.extractor == "repository-overview@2"


def test_repository_overview_ignores_unrendered_package_version_changes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "versioned-repository"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "1.0.0rc1"\n'
    )
    readme = root / "README.md"
    readme.write_text(
        "# Surface\n\n"
        "<!-- sourcebound:begin repository-surface -->\n"
        "stale\n"
        "<!-- sourcebound:end repository-surface -->\n"
    )
    manifest = root / ".sourcebound.yml"
    manifest.write_text("""\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-overview
    source: {path: .}
    renderer: markdown-fragment
""")
    initial = evaluate(root, manifest)[0]
    write_results(root, [initial])

    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "1.0.0"\n'
    )

    assert not evaluate(root, manifest)[0].changed
