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
        "schema",
        "test-suite",
    } <= {item.kind for item in first.items}
    assert all(item.coverage == "standard-gap" for item in first.items)
    assert all(len(item.digest) == 64 for item in first.items)


def test_typescript_package_inventory_needs_no_project_execution(tmp_path: Path) -> None:
    root = tmp_path / "typescript-repo"
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({
        "name": "fixture-cli",
        "version": "2.0.0",
        "bin": {"fixture": "dist/cli.js"},
        "scripts": {"test": "vitest run", "build": "tsc"},
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
    assert any(item.kind == "api-symbol" and item.name == "start" for item in report.items)
    assert any(item.kind == "test-suite" for item in report.items)


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
    assert all(item.coverage == "bound" for item in scan_inventory(root).items)

    ignored_id = scan_inventory(root).items[0].id
    (root / ".clean-docs-ignore.yml").write_text(
        f"version: 1\nignore:\n  - id: {json.dumps(ignored_id)}\n"
        "    reason: This surface is internal to the fixture.\n"
    )
    ignored = next(item for item in scan_inventory(root).items if item.id == ignored_id)
    assert ignored.coverage == "ignored"
