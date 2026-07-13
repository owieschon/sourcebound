from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from clean_docs.cli import main


def _python_repo(tmp_path: Path) -> Path:
    root = tmp_path / "python-repo"
    (root / "src/service").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "baseline-service"\nversion = "1.0.0"\n'
    )
    (root / "src/service/cli.py").write_text("""\
def build_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    sub.add_parser("serve")
    sub.add_parser("inspect")
    return parser
""")
    (root / "tests/test_cli.py").write_text("def test_cli():\n    assert True\n")
    (root / "README.md").write_text("""\
# Baseline service

Author-owned introduction.

## Commands

- obsolete-command

## Usage

Keep this author-owned procedure.
""")
    duplicate = "# Shared guide\n\nOne canonical explanation.\n"
    (root / "docs/GUIDE.md").write_text(duplicate)
    (root / "docs/GUIDE_COPY.md").write_text(duplicate)
    (root / "docs/HANDOFF.md").write_text("# Handoff\n\nTemporary process state.\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(root), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "-qm", "fixture",
        ],
        check=True,
    )
    return root


def _block_network(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError(f"network access attempted with {args!r} {kwargs!r}")


def test_init_dry_run_is_read_only_then_default_init_writes_and_verifies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _python_repo(tmp_path)
    before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    monkeypatch.setattr(socket, "create_connection", _block_network)
    monkeypatch.setattr(socket.socket, "connect", _block_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _block_network)

    assert main([
        "--root", str(root), "init", "--no-model", "--dry-run", "--format", "json"
    ]) == 0
    planned = json.loads(capsys.readouterr().out)
    after_dry_run = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    assert after_dry_run == before
    assert planned["schema"] == "clean-docs.content-plan.v1"
    assert planned["facts"]
    assert {item["action"] for item in planned["operations"]} == {"write", "move"}
    assert all(item["digest"] for item in planned["facts"])
    generated_rows = {
        (item["kind"], item["name"], item["source"], item["locator"])
        for item in planned["facts"]
    }
    assert generated_rows

    assert main(["--root", str(root), "init", "--no-model", "--format", "json"]) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["digest"] == planned["digest"]
    readme = (root / "README.md").read_text()
    assert "obsolete-command" not in readme
    assert "| cli-command | serve | src/service/cli.py | serve |" in readme
    assert "Keep this author-owned procedure." in readme
    assert all(
        f"| {kind} | {name} | {source} | {locator} |" in readme
        for kind, name, source, locator in generated_rows
    )
    assert (root / ".clean-docs.yml").is_file()
    assert (root / "llms.txt").is_file()
    assert (root / "docs/GUIDE.md").is_file()
    assert not (root / "docs/GUIDE_COPY.md").exists()
    assert (root / "docs/archive/clean-docs-init/GUIDE_COPY.md").is_file()
    assert (root / "docs/archive/clean-docs-init/HANDOFF.md").is_file()
    assert main(["--root", str(root), "check"]) == 0
    capsys.readouterr()
    assert main(["--root", str(root), "audit"]) == 0
    capsys.readouterr()

    assert main(["--root", str(root), "init", "--no-model", "--format", "json"]) == 0
    rerun = json.loads(capsys.readouterr().out)
    assert rerun["operations"] == []


def test_typescript_repository_bootstraps_without_python_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "typescript-repo"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "package.json").write_text(json.dumps({
        "name": "typed-service",
        "version": "1.0.0",
        "bin": {"typed": "dist/index.js"},
        "scripts": {"test": "vitest run"},
    }))
    (root / "src/index.ts").write_text("export function start() { return true }\n")
    (root / "openapi.json").write_text(json.dumps({
        "openapi": "3.1.0",
        "paths": {"/health": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }))
    (root / "docs/guide.md").write_text("# Guide\n\nRun the typed command.\n")
    (root / "README.md").write_text("# Typed service\n\n[Guide](docs/guide.md)\n")

    assert main(["--root", str(root), "init", "--no-model"]) == 0
    capsys.readouterr()

    readme = (root / "README.md").read_text()
    assert "| package | typed-service | package.json | package |" in readme
    assert "| cli-command | typed | package.json | bin.typed |" in readme
    assert "| api-symbol | start | src/index.ts | start |" in readme
    assert "| api-endpoint | GET /health | openapi.json | GET /health |" in readme
    assert main(["--root", str(root), "check"]) == 0


def test_init_refuses_to_replace_an_existing_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "configured-repo"
    root.mkdir()
    manifest = "version: 1\nbindings: []\n"
    (root / ".clean-docs.yml").write_text(manifest)
    (root / "README.md").write_text("# Configured repository\n")

    assert main(["--root", str(root), "init", "--no-model"]) == 2

    captured = capsys.readouterr()
    assert "cannot replace an existing manifest" in captured.err
    assert (root / ".clean-docs.yml").read_text() == manifest
    assert not (root / "llms.txt").exists()


def test_missing_language_adapter_blocks_all_init_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "go-repo"
    root.mkdir()
    original = "# Go service\n"
    (root / "README.md").write_text(original)
    (root / "main.go").write_text("package main\n\nfunc main() {}\n")

    assert main([
        "--root", str(root), "init", "--no-model", "--dry-run", "--format", "json"
    ]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["ok"] is False
    assert plan["gaps"] == ["language adapter missing: Go"]

    assert main(["--root", str(root), "init", "--no-model"]) == 2

    captured = capsys.readouterr()
    assert "cannot initialize unsupported surfaces" in captured.err
    assert (root / "README.md").read_text() == original
    assert not (root / ".clean-docs.yml").exists()
    assert not (root / "llms.txt").exists()
