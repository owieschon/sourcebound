from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from clean_docs.audit import audit, write_audit_baseline
from clean_docs.cli import main
from clean_docs.policy import ensure_purpose_contract


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _track(root: Path, *, allow_readme_routing: bool = True) -> None:
    for path in root.rglob("*.md"):
        content = path.read_text()
        if len([line for line in content.splitlines() if line.strip()]) == 1:
            content = content.rstrip() + f"\n\nUse {path.stem} when its repository details are required.\n"
        content = ensure_purpose_contract(content, fallback=True)
        if "clean-docs:allow preamble-contract" not in content:
            content = content.replace(
                "\n",
                '\n<!-- clean-docs:allow preamble-contract '
                'reason="Fixture isolates a different audit rule" -->\n',
                1,
            )
        if (
            path.name == "README.md"
            and allow_readme_routing
            and "clean-docs:allow readme-routing" not in content
        ):
            content = content.replace(
                "\n",
                '\n<!-- clean-docs:allow readme-routing '
                'reason="Fixture isolates a different audit rule" -->\n',
                1,
            )
        path.write_text(content)
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
        '<!-- clean-docs:allow doc-length reason="Lookup rows moved to the generated reference" -->\n'
    ) + "\n".join(f"line {index}" for index in range(130))
    (root / "REFERENCE.md").write_text(long_doc)
    _track(root)

    report = audit(root)

    assert report.findings == ()
    assert report.ignored_documents == ("docs/archive/REPORT.md",)


def test_comprehensiveness_is_not_a_length_allowance(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    body = "\n".join(f"line {index}" for index in range(160))
    (root / "GUIDE.md").write_text(
        "# Guide\n\n"
        '<!-- clean-docs:allow doc-length reason="Everything stays together for completeness" -->\n'
        f"{body}\n"
    )
    _track(root)

    assert "invalid-length-allowance" in {
        finding.rule for finding in audit(root).findings
    }


def test_readme_budget_and_reference_exemption_resolve_by_depth(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    readme = (
        "# Project\n\n"
        "<!-- clean-docs:policy register-v2 -->\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates the page budget" -->\n'
        + "\n".join(f"overview line {index}" for index in range(95))
    )
    reference = "# Reference\n\n" + "\n".join(
        f"| key-{index} | value-{index} |" for index in range(180)
    )
    (root / "README.md").write_text(readme)
    (root / "REFERENCE.md").write_text(reference)
    _track(root)

    findings = audit(root).findings

    assert any(item.rule == "doc-length" and item.path == "README.md" for item in findings)
    assert not any(item.rule == "doc-length" and item.path == "REFERENCE.md" for item in findings)


def test_readme_requires_routing_and_moves_large_reference_blocks(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    block = "\n".join(f"key_{index}: value" for index in range(13))
    (root / "README.md").write_text(
        "# Project\n\n"
        "<!-- clean-docs:policy register-v2 -->\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates reference depth" -->\n'
        "<!-- clean-docs:purpose -->\n"
        "Project maps repository facts for maintainers who must catch stale documentation.\n"
        "<!-- clean-docs:end purpose -->\n"
        "```yaml\n"
        f"{block}\n"
        "```\n"
    )
    _track(root, allow_readme_routing=False)

    rules = {finding.rule for finding in audit(root).findings}

    assert {"readme-routing", "readme-reference-depth"} <= rules


def test_assurance_dedup_points_to_the_canonical_boundary(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    canonical = root / "docs/learn/deep-dive-the-deterministic-seam.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(
        "# Boundary\n\nDeterministic code owns the gate result in this canonical explanation.\n"
    )
    (root / "README.md").write_text(
        "# Project\n\n<!-- clean-docs:policy register-v2 -->\n"
        "Deterministic code owns the gate result in this overview.\n"
    )
    _track(root)

    assert any(
        finding.rule == "assurance-dedup" and finding.path == "README.md"
        for finding in audit(root).findings
    )


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
        ("provenance", 9),
    ]


def test_audit_requires_the_purpose_contract_before_body_content(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates purpose policy" -->\n'
        '<!-- clean-docs:allow readme-routing reason="Fixture isolates purpose policy" -->\n\n'
        "Body content arrives first.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert [(finding.rule, finding.line) for finding in report.findings] == [
        ("purpose-contract", 1),
    ]


def test_audit_applies_sentence_policy_to_reader_documents(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates booster policy" -->\n'
        '<!-- clean-docs:allow readme-routing reason="Fixture isolates booster policy" -->\n\n'
        "<!-- clean-docs:purpose -->\n"
        "Use this page when source claims can drift. It gives maintainers a checked repair path.\n"
        "<!-- clean-docs:end purpose -->\n\nA powerful workflow.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert [(finding.rule, finding.line) for finding in audit(root).findings] == [
        ("prohibited-booster", 9),
    ]


def test_audit_ignores_purpose_markers_when_comparing_prose(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(ensure_purpose_contract(
        "# Project\n\nUse this page for project behavior.\n"
    ))
    (root / "GUIDE.md").write_text(ensure_purpose_contract(
        "# Guide\n\nUse this page for guide behavior.\n"
    ))
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert not any(finding.rule == "near-dup" for finding in audit(root).findings)


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


def test_packaged_standard_assets_are_not_reader_documents(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    asset = root / "src/clean_docs/standards/exemplars.md"
    asset.parent.mkdir(parents=True)
    asset.write_text("# Prompt exemplars\n\nInternal before and after pairs.\n")
    (root / "README.md").write_text("# Project\n")
    _track(root)

    report = audit(root)

    assert report.ok
    assert report.documents == ("README.md",)
    assert report.ignored_documents == ()


def test_fixture_markdown_and_ambiguous_operational_names_are_not_process_history(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    scripts = root / "scripts"
    scripts.mkdir()
    (root / "README.md").write_text(
        "# Project\n\nUse this guide when changing the project. Without its constraints, "
        "a change can drift; after reading, maintainers can verify the supported path.\n"
    )
    (root / "ARCHITECTURE_NOTES.md").write_text(
        "# Architecture constraints\n\nUse these notes before changing deployment boundaries. "
        "Without the active constraints, a change can break isolation; after reading, "
        "operators can verify the safe topology.\n"
    )
    (root / "DEPLOYMENT_PLAN.md").write_text(
        "# Deployment plan\n\nUse this plan when preparing a deployment. Without its current "
        "gates, an unsafe release can proceed; after reading, operators can verify readiness.\n"
    )
    (scripts / "links.fixture.md").write_text(
        "Negative control: `scripts/does-not-exist.py`\n"
    )
    _track(root)

    report = audit(root)

    assert report.ok
    assert report.documents == (
        "ARCHITECTURE_NOTES.md",
        "DEPLOYMENT_PLAN.md",
        "README.md",
    )


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
