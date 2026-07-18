from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from clean_docs.audit import audit, write_audit_baseline
from clean_docs.cli import main
from clean_docs.policy import REGISTER_PROFILE, ensure_purpose_contract


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
        if REGISTER_PROFILE not in content:
            content = content.rstrip() + f"\n\n{REGISTER_PROFILE}\n"
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
    }
    assert {finding.rule for finding in report.advisories} >= {
        "process-artifact",
    }


def test_audit_includes_untracked_markdown_but_honors_gitignore(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ".gitignore").write_text("ignored.md\n")
    (root / "README.md").write_text("# Project\n\nCurrent repository guide.\n")
    _track(root)
    untracked = ensure_purpose_contract(
        "# New guide\n\nMaintainers read this guide before changing the Acorn queue.\n",
        fallback=True,
    )
    (root / "NEW.md").write_text(untracked + "\n[Missing](missing.md)\n")
    (root / "ignored.md").write_text("# Ignored\n\n[Missing](also-missing.md)\n")

    report = audit(root)

    assert "NEW.md" in report.documents
    assert "ignored.md" not in report.documents
    assert any(
        finding.path == "NEW.md" and finding.rule == "broken-local-link"
        for finding in report.advisories
    )


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
        finding.rule for finding in audit(root).advisories
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

    findings = audit(root).advisories

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
        for finding in audit(root).advisories
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

    assert [(finding.rule, finding.line) for finding in report.advisories] == [
        ("provenance", 9),
    ]


def test_audit_requires_the_purpose_contract_before_body_content(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n"
        "<!-- clean-docs:policy register-v2 -->\n"
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
        "<!-- clean-docs:policy register-v2 -->\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates booster policy" -->\n'
        '<!-- clean-docs:allow readme-routing reason="Fixture isolates booster policy" -->\n\n'
        "<!-- clean-docs:purpose -->\n"
        "Use this page when source claims can drift. It gives maintainers a checked repair path.\n"
        "<!-- clean-docs:end purpose -->\n\nA powerful workflow.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert [(finding.rule, finding.line) for finding in audit(root).findings] == [
        ("prohibited-booster", 10),
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


def test_audit_rejects_a_repeated_stock_purpose_shell_across_the_corpus(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    pages = {
        "README.md": (
            "Use this guide when operators need the Acorn queue map. "
            "It keeps each route tied to the current worker contract."
        ),
        "GUIDE.md": (
            "Use this guide when maintainers repair the Birch cache. "
            "It names the invalidation boundary and the recovery check."
        ),
        "REFERENCE.md": (
            "Use this reference when contributors inspect Cedar settings. "
            "It lists the accepted keys and their defining schema."
        ),
    }
    for path, purpose in pages.items():
        (root / path).write_text(
            f"# {Path(path).stem.title()}\n\n"
            "<!-- clean-docs:policy register-v2 -->\n"
            "<!-- clean-docs:purpose -->\n"
            f"{purpose}\n"
            "<!-- clean-docs:end purpose -->\n"
        )
    _track(root)

    findings = [
        finding for finding in audit(root).findings
        if finding.rule == "purpose-template"
    ]

    assert {finding.path for finding in findings} == {"README.md", "GUIDE.md"}


def test_audit_allows_two_literal_pages_to_share_a_purpose_opening(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    for path, subject in (("CLI.md", "commands"), ("REFERENCE.md", "manifest fields")):
        (root / path).write_text(
            f"# {Path(path).stem.title()}\n\n"
            "<!-- clean-docs:policy register-v2 -->\n"
            "<!-- clean-docs:purpose -->\n"
            f"Use this reference when looking up {subject}. "
            "The page keeps exact values in one literal lookup surface.\n"
            "<!-- clean-docs:end purpose -->\n"
        )
    _track(root)

    assert not any(
        finding.rule == "purpose-template" for finding in audit(root).findings
    )


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


def test_vcsless_audit_skips_build_outputs_and_test_fixtures(tmp_path: Path) -> None:
    root = tmp_path / "published"
    root.mkdir()
    (root / "README.md").write_text(ensure_purpose_contract(
        "# Project\n\n"
        "Project checks source-bound prose for maintainers who need stale claims to fail.\n"
    ))
    for relative in (
        "src/clean_docs/standards/exemplars.md",
        "build/lib/clean_docs/standards/exemplars.md",
        "tests/fixtures/v10_upgrade/README.md",
        "dist/generated/README.md",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Internal fixture\n\n[Broken](missing.md)\n")

    report = audit(root)

    assert report.ok
    assert report.documents == ("README.md",)


def test_unregistered_documents_preview_compatible_policy_without_gating_it(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    long_body = "\n".join(f"A powerful status line {index}." for index in range(180))
    (root / "STATUS.md").write_text(f"# Current status\n\n{long_body}\n")
    (root / "README.md").write_text(
        "# Project\n\n"
        "A powerful guide with no purpose marker.\n\n"
        "[Missing](docs/missing.md)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assessment = audit(root)
    report = audit(root, preview_policy=True)

    assert assessment.findings == ()
    assert dict(assessment.advisory_totals) == {
        "broken-local-link": 1,
        "process-artifact": 1,
    }
    assert report.findings == ()
    assert not report.repository_integrity_enforced
    assert report.policy_preview
    assert dict(report.advisory_totals) == {
        "broken-local-link": 1,
        "preamble-contract": 1,
        "prohibited-booster": 1,
        "process-artifact": 1,
        "purpose-contract": 1,
        "readme-routing": 1,
    }


def test_manifest_accepts_repository_integrity_findings_as_gates(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ".clean-docs.yml").write_text("version: 1\nbindings: []\n")
    (root / "README.md").write_text(
        "# Project\n\n[Missing](docs/missing.md)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.repository_integrity_enforced
    assert [(finding.rule, finding.path) for finding in report.findings] == [
        ("broken-local-link", "README.md"),
    ]


def test_cli_separates_assessment_from_policy_compatibility_preview(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n\nA powerful guide.\n\n[Missing](docs/missing.md)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert main(["--root", str(root), "audit", "--format", "json"]) == 0
    assessment = json.loads(capsys.readouterr().out)
    assert assessment["enforcement"]["repository_integrity"] is False
    assert assessment["policy_preview"] is False
    assert assessment["findings"] == []
    assert assessment["advisory_totals"] == {"broken-local-link": 1}

    assert main([
        "--root",
        str(root),
        "audit",
        "--preview-policy",
        "--format",
        "json",
    ]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["policy_preview"] is True
    assert preview["advisory_totals"]["prohibited-booster"] == 1


def test_registered_document_activates_the_packaged_register(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        f"# Project\n\n{REGISTER_PROFILE}\n\nA powerful guide with no purpose block.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert {finding.rule for finding in audit(root).findings} == {
        "preamble-contract",
        "prohibited-booster",
        "purpose-contract",
        "readme-routing",
    }


def test_registration_does_not_turn_runtime_templates_into_reader_pages(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    template = root / "services/mcp/templates/env-context.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        f"{REGISTER_PROFILE}\n\n{{{{defined_groups}}}}\n{{{{metadata}}}}\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.ok
    assert report.findings == ()
    assert report.advisories == ()
    assert [(profile.path, profile.role) for profile in report.document_profiles] == [
        ("services/mcp/templates/env-context.md", "template"),
    ]


def test_explicit_role_overrides_a_heuristic_without_suppressing_integrity(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Generated prompt input\n\n"
        "<!-- clean-docs:role template -->\n"
        f"{REGISTER_PROFILE}\n"
        "{{runtime_instructions}}\n"
        "[Missing](missing.md)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.document_profiles[0].role == "template"
    assert {finding.rule for finding in report.findings} == {"broken-local-link"}


def test_invalid_explicit_role_fails_instead_of_silently_using_a_guess(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n\n<!-- clean-docs:role brochure -->\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert [
        (finding.rule, finding.detail) for finding in audit(root).findings
    ] == [
        ("invalid-document-role", "unsupported clean-docs role: brochure"),
    ]


def test_agent_procedure_keeps_its_execution_contract_under_registration(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    skill = root / ".agents/skills/repair/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: repair\ndescription: Repair one bound document.\n---\n\n"
        f"{REGISTER_PROFILE}\n\n"
        "The next executor must use the worktree, verify the diff budget, and stop on drift.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.ok
    assert report.findings == ()
    assert report.advisories == ()
    assert report.document_profiles[0].role == "agent-procedure"


def test_architecture_and_reference_density_are_not_page_length_failures(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    for name, title in (
        ("ARCHITECTURE.md", "Architecture"),
        ("API_REFERENCE.md", "API reference"),
    ):
        body = "\n".join(f"| field-{index} | boundary-{index} |" for index in range(180))
        (root / name).write_text(
            f"# {title}\n\n"
            f"{REGISTER_PROFILE}\n"
            "<!-- clean-docs:purpose -->\n"
            "Maintainers use this page to inspect the current system boundary before changing it.\n"
            "<!-- clean-docs:end purpose -->\n\n"
            f"{body}\n"
        )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert not {
        finding.rule
        for finding in [*report.findings, *report.advisories]
    } & {"doc-length", "section-length"}
    assert {profile.role for profile in report.document_profiles} == {
        "architecture",
        "reference",
    }


def test_support_page_keeps_complete_operational_sequences(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    support = root / "docs" / "SUPPORT.md"
    support.parent.mkdir()
    support.write_text(
        "# Support\n\n"
        f"{REGISTER_PROFILE}\n"
        "<!-- clean-docs:purpose -->\n"
        "Operators use this page to diagnose and recover a failing service.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "## Recover the service\n\n"
        + "\n".join(f"{index}. Run recovery check {index}." for index in range(45))
        + "\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    profiles = {profile.path: profile for profile in report.document_profiles}
    assert profiles["docs/SUPPORT.md"].role == "troubleshooting"
    assert "section-length" not in {finding.rule for finding in report.findings}


def test_contributor_and_compromise_records_keep_their_native_jobs(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "CONTRIBUTING.md").write_text(
        "# Contributing\n\nChoose a product area, then follow its local checks.\n"
    )
    (root / "COMPROMISES.md").write_text(
        "# Compromises\n\nDeliberate scope cuts and the follow-up each one implies.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root, preview_policy=True)

    profiles = {profile.path: profile.role for profile in report.document_profiles}
    assert profiles == {
        "COMPROMISES.md": "architecture",
        "CONTRIBUTING.md": "component-overview",
    }
    assert "purpose-contract" not in dict(report.advisory_totals)


def test_corpus_advisories_are_bounded_without_hiding_totals(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    for index in range(12):
        (root / f"STATUS-{index}.md").write_text(
            f"# Status {index}\n\nRecorded state for run {index}.\n"
        )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    process = [
        finding for finding in report.advisories
        if finding.rule == "process-artifact"
    ]
    assert len(process) == 3
    assert dict(report.advisory_totals)["process-artifact"] == 12
    assert report.ok


def test_audit_uses_canonical_document_identity_for_symlink_aliases(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    canonical = root / "AGENTS.md"
    canonical.write_text(
        "# Agent contract\n\n"
        "Repository agents use this contract before changing source-owned documentation.\n"
    )
    (root / "CLAUDE.md").symlink_to("AGENTS.md")
    _track(root)

    report = audit(root)

    assert report.ok
    assert report.documents == ("AGENTS.md",)
    assert not any(finding.rule == "near-duplicate" for finding in report.findings)


def test_link_checks_use_repository_identity_and_ignore_literal_examples(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    docs = root / "docs"
    docs.mkdir()
    tracked = docs / "present.md"
    tracked.write_text("# Present\n")
    (docs / "guide.md").write_text("# Guide\n")
    (root / "README.md").write_text(
        "# Project\n\n"
        "[Sparse target](docs/present.md)\n"
        "[Repository root](/docs/present.md)\n"
        "[Extensionless](docs/guide)\n"
        "[Published route](/handbook/engineering/start)\n"
        "[Template ellipsis](…)\n"
        "[Template path](docs/<package>/README.md)\n"
        "[Angle-wrapped missing](<docs/also-missing.md>)\n"
        "`![literal](inline-missing.png)`\n\n"
        "```markdown\n"
        "[Fenced literal](fenced-missing.md)\n"
        "```\n\n"
        "[Actually missing](docs/missing.md)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    tracked.unlink()

    report = audit(root)

    link_findings = [
        finding for finding in report.advisories
        if finding.rule == "broken-local-link"
    ]
    assert [(finding.rule, finding.detail) for finding in link_findings] == [
        ("broken-local-link", "target does not exist: <docs/also-missing.md>"),
        ("broken-local-link", "target does not exist: docs/missing.md"),
    ]
    assert not report.repository_integrity_enforced


def test_audit_discloses_mdx_without_claiming_to_check_it(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("# Project\n")
    (root / "guide.mdx").write_text("# MDX guide\n\n<Component />\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.ok
    assert report.documents == ("README.md",)
    assert report.unsupported_documents == ("guide.mdx",)


def test_agent_documentation_is_active_while_tool_context_stays_internal(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    skill = root / ".agents/skills/inspect/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Inspect\n\n[Missing](references/missing.md)\n")
    context = root / ".clean-docs/context/contributor.md"
    context.parent.mkdir(parents=True)
    context.write_text("# Generated context\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.documents == (".agents/skills/inspect/SKILL.md",)
    assert report.ignored_documents == (".clean-docs/context/contributor.md",)
    assert [(finding.rule, finding.path) for finding in report.advisories] == [
        ("broken-local-link", ".agents/skills/inspect/SKILL.md"),
    ]


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
    assert {
        profile.path: profile.role for profile in report.document_profiles
    }["DEPLOYMENT_PLAN.md"] == "plan"


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
    assert report.ok
    assert report.findings == ()
    assert [item.rule for item in report.advisories] == ["process-artifact"]
    assert report.stale_baseline == ()

    (root / "docs").mkdir()
    (root / "docs/missing.md").write_text("# Present\n")
    _track(root)
    report = audit(root)
    assert not report.ok
    assert report.findings == ()
    assert [item.rule for item in report.advisories] == ["process-artifact"]
    assert [item.rule for item in report.stale_baseline] == ["broken-local-link"]


def test_update_baseline_is_explicit_and_tampering_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    (root / "STATUS.md").write_text("# Status\n")
    _track(root)

    assert main(["--root", str(root), "audit"]) == 0
    capsys.readouterr()
    assert main(["--root", str(root), "audit", "--update-baseline"]) == 0
    capsys.readouterr()
    assert audit(root).ok

    baseline = root / ".clean-docs/audit-baseline.json"
    assert main(["--root", str(root), "audit", "--update-baseline"]) == 0
    baseline.write_text(
        '{"schema":"clean-docs.audit-baseline.v1","findings":['
        '{"fingerprint":"tampered","rule":"broken-local-link",'
        '"path":"README.md","line":1,"detail":"target does not exist: missing.md"}]}'
    )
    assert main(["--root", str(root), "audit"]) == 2
    assert "fingerprint does not match" in capsys.readouterr().err
