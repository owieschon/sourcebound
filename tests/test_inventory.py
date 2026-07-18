from __future__ import annotations

import json
import subprocess
from pathlib import Path

from clean_docs.cli import main
from clean_docs.engine import evaluate, write_results
from clean_docs.inventory import scan_inventory


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
    source = root / "src/service/cli.py"
    source.write_text(source.read_text().replace("return True", "return False", 1))
    implementation_only = next(
        item for item in scan_inventory(root).items if item.name == "public_api"
    )
    assert implementation_only.digest == public_api.digest

    source.write_text(
        source.read_text().replace("def public_api():", "def public_api(timeout=5):")
    )
    signature_change = next(
        item for item in scan_inventory(root).items if item.name == "public_api"
    )
    assert signature_change.digest != public_api.digest


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

    start = next(item for item in report.items if item.name == "start")
    (root / "src/index.ts").write_text(
        "throw new Error('must not execute');\n"
        "export function start(timeout = 5) { return timeout }\n"
    )
    changed = next(
        item for item in scan_inventory(root).items if item.name == "start"
    )
    assert changed.digest != start.digest


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
        "# Fixture\n\n<!-- clean-docs:begin repository-surface -->\nstale\n"
        "<!-- clean-docs:end repository-surface -->\n"
    )
    manifest = root / ".clean-docs.yml"
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
    (root / ".clean-docs-ignore.yml").write_text(
        f"version: 1\nignore:\n  - id: {json.dumps(ignored_id)}\n"
        "    reason: This surface is internal to the fixture.\n"
    )
    ignored = next(item for item in scan_inventory(root).items if item.id == ignored_id)
    assert ignored.coverage == "ignored"


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
        "<!-- clean-docs:begin repository-surface -->\nstale\n"
        "<!-- clean-docs:end repository-surface -->\n"
    )
    manifest = root / ".clean-docs.yml"
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
    assert "| api-symbol | 200 |" in first.expected
    assert "and 197 more" in first.expected
    assert len(first.expected.splitlines()) < 15
    write_results(root, [first])
    before = readme.read_text()

    (source / "module_199.py").write_text("def zzzz_replacement():\n    return 199\n")
    second = evaluate(root, manifest)[0]

    assert second.changed
    assert before.split("<!-- clean-docs:inventory-sha256", 1)[0] == (
        second.expected.split("<!-- clean-docs:inventory-sha256", 1)[0]
    )


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
        "<!-- clean-docs:begin repository-surface -->\n"
        "stale\n"
        "<!-- clean-docs:end repository-surface -->\n"
    )
    manifest = root / ".clean-docs.yml"
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
