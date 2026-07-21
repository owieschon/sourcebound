from __future__ import annotations

import json
from pathlib import Path

import pytest

from clean_docs.cli import main
from clean_docs.inventory import scan_inventory


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "explained-service"\nversion = "1.0.0"\n'
    )
    (root / "README.md").write_text("# Explained service\n")
    return root


def test_explain_describes_required_policy_repair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)

    assert main([
        "--root", str(root), "explain", "broken-local-link", "--format", "json"
    ]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["kind"] == "policy-rule"
    assert result["state"] == "required"
    assert result["required"] is True
    assert "Fix the target path" in result["repair"]


def test_explain_distinguishes_gap_and_reasoned_ignore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)
    identifier = next(
        item.id for item in scan_inventory(root).items if item.kind == "package"
    )

    assert main(["--root", str(root), "explain", identifier, "--format", "json"]) == 0
    gap = json.loads(capsys.readouterr().out)
    assert gap["state"] == "standard-gap"
    assert gap["required"] is False
    assert gap["evidence"]["adapter"] == "python-package"

    reason = "This package is documented by an external generated reference."
    (root / ".sourcebound-ignore.yml").write_text(
        "version: 1\nignore:\n"
        f"  - id: {json.dumps(identifier)}\n"
        f"    reason: {reason}\n"
    )
    assert main(["--root", str(root), "explain", identifier, "--format", "json"]) == 0
    ignored = json.loads(capsys.readouterr().out)
    assert ignored["state"] == "ignored"
    assert reason in ignored["summary"]


def test_inventory_rejects_an_invalid_coverage_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)
    (root / ".sourcebound-ignore.yml").write_text(
        "version: 1\nignore:\n  - id: missing-id\n    reason: too short\n"
    )

    assert main(["--root", str(root), "inventory"]) == 2

    captured = capsys.readouterr()
    assert "unknown inventory id" in captured.err


def test_explain_rejects_an_unknown_identifier(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)

    assert main(["--root", str(root), "explain", "not-a-finding"]) == 2

    captured = capsys.readouterr()
    assert "unknown finding or inventory id" in captured.err


def test_explain_names_catalog_visibility_and_completion_boundaries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repository(tmp_path)
    for identifier, expected in (
        ("cataloged", "does not check prose"),
        ("coverage-complete", "alias"),
        ("direct-coverage-complete", "direct binding"),
        ("direct-policy-complete", "selected by direct policy"),
    ):
        assert main(["--root", str(root), "explain", identifier, "--format", "json"]) == 0
        assert expected in json.loads(capsys.readouterr().out)["summary"]
