from __future__ import annotations

from pathlib import Path

import pytest

from clean_docs.cli import main


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "facts.txt").write_text("current\n")
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- sourcebound:begin fact -->\nstale\n<!-- sourcebound:end fact -->\n"
    )
    (root / ".sourcebound.yml").write_text("""\
version: 1
bindings:
  - id: fact
    type: region
    doc: README.md
    region: fact
    extractor: file
    source: {path: facts.txt}
    renderer: scalar
""")
    return root


def test_cli_exit_codes_distinguish_drift_configuration_and_extraction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _fixture(tmp_path)

    assert main(["--root", str(root), "check"]) == 1
    capsys.readouterr()

    manifest = root / ".sourcebound.yml"
    valid = manifest.read_text()
    manifest.write_text(valid.replace("version: 1", "version: 9"))
    assert main(["--root", str(root), "check"]) == 2
    assert "manifest version must be 1" in capsys.readouterr().err

    manifest.write_text(valid.replace("facts.txt", "missing.txt"))
    assert main(["--root", str(root), "check"]) == 3
    assert "cannot read source" in capsys.readouterr().err


def test_changed_check_flags_fail_closed_when_changed_mode_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _fixture(tmp_path)

    assert main([
        "--root", str(root), "check", "--base", "HEAD~1", "--head", "HEAD",
    ]) == 2
    assert "require check --changed" in capsys.readouterr().err

    assert main([
        "--root", str(root), "check", "--changed", "--base", "HEAD~1",
    ]) == 2
    assert "requires both --base and --head" in capsys.readouterr().err
