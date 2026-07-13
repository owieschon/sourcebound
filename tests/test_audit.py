from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from clean_docs.audit import audit, write_audit_baseline
from clean_docs.cli import main


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _track(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)


def test_audit_needs_no_manifest_and_reports_corpus_failures(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("# Project\n\n[Missing](docs/missing.md)\n")
    (root / "STATUS.md").write_text("# Status\n")
    _track(root)

    report = audit(root)

    assert {finding.rule for finding in report.findings} == {
        "broken-local-link",
        "process-artifact",
    }
    assert len(report.findings) == 2


def test_archive_and_reasoned_length_allowance_are_explicit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    archive = root / "docs/archive"
    archive.mkdir(parents=True)
    (archive / "REPORT.md").write_text("# Historical report\n")
    long_doc = "# Reference\n\n" + (
        '<!-- clean-docs:allow doc-length reason="Canonical generated reference stays whole" -->\n'
    ) + "\n".join(f"line {index}" for index in range(130))
    (root / "REFERENCE.md").write_text(long_doc)
    _track(root)

    report = audit(root)

    assert report.findings == ()
    assert report.ignored_documents == ("docs/archive/REPORT.md",)


def test_audit_runs_corpus_rules_and_accepts_named_reasoned_allowances(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "REFERENCE.md").write_text(
        "# Reference\n\n"
        "<!-- clean-docs:allow audience reason=\"This page documents the workflow vocabulary\" -->\n"
        "The next executor can pick up this branch from the worktree.\n\n"
        "The value was recorded in (Program 7).\n"
    )
    _track(root)

    report = audit(root)

    assert [(finding.rule, finding.line) for finding in report.findings] == [
        ("provenance", 6),
    ]


def test_generated_context_bundles_are_not_canonical_corpus_pages(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n\nCanonical factual guidance with enough distinct words for corpus analysis.\n"
    )
    bundle = root / ".clean-docs/context/contributor.md"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(
        "# Context bundle\n\n"
        "Canonical factual guidance with enough distinct words for corpus analysis.\n"
    )
    _track(root)

    report = audit(root)

    assert report.findings == ()
    assert report.documents == ("README.md",)
    assert report.ignored_documents == (".clean-docs/context/contributor.md",)


def test_hidden_configuration_markdown_is_not_reader_documentation(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    command = root / ".agent/commands/STATUS.md"
    command.parent.mkdir(parents=True)
    command.write_text("# Status command\n\nReport operational state.\n")
    (root / "README.md").write_text("# Project\n")
    _track(root)

    report = audit(root)

    assert report.ok
    assert report.documents == ("README.md",)
    assert report.ignored_documents == (".agent/commands/STATUS.md",)


def test_exact_baseline_fails_on_new_and_resolved_findings(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("# Project\n\n[Missing](docs/missing.md)\n")
    _track(root)

    baseline_path = write_audit_baseline(root)
    report = audit(root)

    assert report.ok
    assert report.findings == ()
    assert [item.rule for item in report.baselined_findings] == ["broken-local-link"]
    assert report.stale_baseline == ()
    assert baseline_path == root / ".clean-docs/audit-baseline.json"

    (root / "STATUS.md").write_text("# Status\n")
    _track(root)
    report = audit(root)
    assert not report.ok
    assert [item.rule for item in report.findings] == ["process-artifact"]
    assert report.stale_baseline == ()

    (root / "docs").mkdir()
    (root / "docs/missing.md").write_text("# Present\n")
    _track(root)
    report = audit(root)
    assert not report.ok
    assert [item.rule for item in report.findings] == ["process-artifact"]
    assert [item.rule for item in report.stale_baseline] == ["broken-local-link"]


def test_update_baseline_is_explicit_and_tampering_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    (root / "STATUS.md").write_text("# Status\n")
    _track(root)

    assert main(["--root", str(root), "audit"]) == 1
    capsys.readouterr()
    assert main(["--root", str(root), "audit", "--update-baseline"]) == 0
    capsys.readouterr()
    assert audit(root).ok

    baseline = root / ".clean-docs/audit-baseline.json"
    baseline.write_text(baseline.read_text().replace('"line": 1', '"line": 2'))
    assert main(["--root", str(root), "audit"]) == 2
    assert "fingerprint does not match" in capsys.readouterr().err
