from __future__ import annotations

import json
import subprocess
from pathlib import Path

from clean_docs.inventory import scan_inventory


def test_python_and_typescript_ecosystem_adapters_share_inventory_types(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "app.py").write_text(
        "class Settings(BaseSettings):\n"
        "    api_url: str\n\n"
        "@app.command('serve')\n"
        "def serve():\n"
        "    pass\n\n"
        "@server.tool()\n"
        "def lookup():\n"
        "    pass\n"
    )
    (root / "cli.ts").write_text(
        "program.command('ship').option('--dry-run')\n"
        "server.tool('inspect', {}, () => ({}))\n"
    )
    (root / "openapi.json").write_text(
        json.dumps({"openapi": "3.1.0", "paths": {"/items": {"get": {}}}})
    )
    (root / "config.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "Config",
                "properties": {"timeout": {"type": "integer"}},
            }
        )
    )
    (root / "package.json").write_text(
        json.dumps({"name": "fixture", "version": "1.0.0", "bin": {"fixture": "cli.js"}})
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    items = scan_inventory(root).items
    observed = {(item.kind, item.name, item.adapter) for item in items}

    assert ("cli-command", "serve", "python-cli-framework") in observed
    assert ("config-key", "api_url", "python-settings-ast") in observed
    assert ("mcp-tool", "lookup", "python-ast") in observed
    assert ("cli-command", "ship", "typescript-cli-framework") in observed
    assert ("cli-option", "--dry-run", "typescript-cli-framework") in observed
    assert ("mcp-tool", "inspect", "typescript-mcp") in observed
    assert ("api-endpoint", "GET /items", "openapi") in observed
    assert ("schema", "Config", "json-schema") in observed
    assert ("config-key", "timeout", "json-schema") in observed
    assert ("package", "fixture", "node-package") in observed
