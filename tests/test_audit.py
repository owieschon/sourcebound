from __future__ import annotations

import subprocess
from pathlib import Path

from clean_docs.audit import audit


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
