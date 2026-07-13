from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from clean_docs.cli import main


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(root), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "-qm", message,
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _region_repository(tmp_path: Path) -> Path:
    root = tmp_path / "region-repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "src/commands.py").write_text(
        'COMMANDS = [{"name": "serve", "job": "Run the service"}]\n'
    )
    (root / "README.md").write_text(
        "# Service\n\n<!-- clean-docs:begin commands -->\n"
        "<!-- clean-docs:end commands -->\n"
    )
    (root / ".clean-docs.yml").write_text("""\
version: 1
bindings:
  - id: commands
    type: region
    doc: README.md
    region: commands
    extractor: python-literal
    source: {path: src/commands.py, symbol: COMMANDS}
    renderer: markdown-table
    columns: [name, job]
""")
    assert main(["--root", str(root), "derive", "--write"]) == 0
    return root


def _symbol_repository(tmp_path: Path) -> Path:
    root = tmp_path / "symbol-repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "src/api.py").write_text(
        "def public_api():\n    return True\n\n"
        "def _helper():\n    return 1\n"
    )
    (root / "README.md").write_text(
        "# Service\n\n## API\n\nThe public API is defined in `src/api.py`.\n"
    )
    (root / ".clean-docs.yml").write_text("""\
version: 1
bindings:
  - id: public-api
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/api.py, symbol: public_api}
""")
    return root


def test_changed_bound_evidence_has_stable_required_finding_and_sarif(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _region_repository(tmp_path)
    capsys.readouterr()
    base = _commit(root, "base")
    source = root / "src/commands.py"
    source.write_text(
        'COMMANDS = [{"name": "serve", "job": "Run the service"}, '
        '{"name": "inspect", "job": "Inspect state"}]\n'
    )
    head = _commit(root, "add command")

    args = [
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--format", "json",
    ]
    assert main(args) == 1
    first = json.loads(capsys.readouterr().out)
    assert first["gaps"] == []
    assert len(first["required"]) == 1
    finding = first["required"][0]
    assert finding["rule"] == "binding-drift"
    assert finding["repair"] == "clean-docs drive --binding commands"

    assert main(args) == 1
    second = json.loads(capsys.readouterr().out)
    assert second == first

    sarif_args = args[:-1] + ["sarif"]
    assert main(sarif_args) == 1
    sarif = json.loads(capsys.readouterr().out)
    result = sarif["runs"][0]["results"][0]
    assert result["partialFingerprints"]["cleanDocsFindingId"] == finding["id"]
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "README.md"


def test_changed_new_public_surface_is_a_separate_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text() + '\nsub.add_parser("serve")\n')
    head = _commit(root, "add command")

    assert main([
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--format", "json",
    ]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["required"] == []
    assert len(result["gaps"]) == 1
    assert result["gaps"][0]["rule"] == "new-public-surface"
    assert "serve" in result["gaps"][0]["message"]


def test_changed_private_refactor_stays_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return 1", "return 2"))
    head = _commit(root, "private refactor")

    assert main([
        "--root", str(root), "check", "--changed", "--base", base, "--head", head,
        "--format", "json",
    ]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["required"] == []
    assert result["gaps"] == []
