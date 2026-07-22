from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest

from sourcebound.audit import AuditFinding, audit, finding_fingerprint, write_audit_baseline
from sourcebound.cli import main
from sourcebound.corpus import _active_predecessor_markers, scan_corpus
from sourcebound.errors import ConfigurationError
from sourcebound.policy import REGISTER_PROFILE, ensure_purpose_contract


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
        if "sourcebound:allow preamble-contract" not in content:
            content = content.replace(
                "\n",
                '\n<!-- sourcebound:allow preamble-contract '
                'reason="Fixture isolates a different audit rule" -->\n',
                1,
            )
        if (
            path.name == "README.md"
            and allow_readme_routing
            and "sourcebound:allow readme-routing" not in content
        ):
            content = content.replace(
                "\n",
                '\n<!-- sourcebound:allow readme-routing '
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
        '<!-- sourcebound:allow doc-length reason="Lookup rows moved to the generated reference" -->\n'
    ) + "\n".join(f"line {index}" for index in range(130))
    (root / "REFERENCE.md").write_text(long_doc)
    _track(root)

    report = audit(root)

    assert report.findings == ()
    assert report.ignored_documents == ("docs/archive/REPORT.md",)


def test_repeated_editorial_allowance_reason_is_visible_without_blocking(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    reason = (
        '<!-- sourcebound:allow section-length reason="This section keeps one '
        'tightly coupled procedure together" -->'
    )
    for name in ("ONE.md", "TWO.md", "THREE.md"):
        (root / name).write_text(f"# {name}\n\n{reason}\n\nCurrent guidance.\n")
    _track(root)

    report = audit(root)

    assert report.findings == ()
    repeated = [
        finding
        for finding in report.advisories
        if finding.rule == "repeated-allowance-reason"
    ]
    assert len(repeated) == 1
    assert "appears 3 times across 3 documents" in repeated[0].detail


def test_allowance_examples_in_code_fences_do_not_suppress_or_repeat(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    example = (
        '```markdown\n<!-- sourcebound:allow doc-length reason="Repeated example '
        'that must stay inert" -->\n```'
    )
    for name in ("ONE.md", "TWO.md", "THREE.md"):
        (root / name).write_text(f"# {name}\n\n{example}\n\nCurrent guidance.\n")
    _track(root)

    report = audit(root)

    assert not any(
        finding.rule == "repeated-allowance-reason"
        for finding in report.advisories
    )


def test_archive_still_rejects_active_predecessor_markers(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    archive = root / "docs/archive"
    archive.mkdir(parents=True)
    predecessor = "clean" + "-docs"
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (archive / "REPORT.md").write_text(
        "# Historical report\n\n"
        f"<!-- {predecessor}:policy register-v2 -->\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.ignored_documents == ("docs/archive/REPORT.md",)
    assert [
        (finding.rule, finding.path, finding.line)
        for finding in report.findings
    ] == [("predecessor-marker", "docs/archive/REPORT.md", 3)]


def test_comprehensiveness_is_not_a_length_allowance(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    body = "\n".join(f"line {index}" for index in range(160))
    (root / "GUIDE.md").write_text(
        "# Guide\n\n"
        '<!-- sourcebound:allow doc-length reason="Everything stays together for completeness" -->\n'
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
        "<!-- sourcebound:policy register-v2 -->\n"
        '<!-- sourcebound:allow preamble-contract reason="Fixture isolates the page budget" -->\n'
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
        "<!-- sourcebound:policy register-v2 -->\n"
        '<!-- sourcebound:allow preamble-contract reason="Fixture isolates reference depth" -->\n'
        "<!-- sourcebound:purpose -->\n"
        "Project maps repository facts for maintainers who must catch stale documentation.\n"
        "<!-- sourcebound:end purpose -->\n"
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
        "# Project\n\n<!-- sourcebound:policy register-v2 -->\n"
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
        "<!-- sourcebound:allow audience reason=\"This page documents the workflow vocabulary\" -->\n"
        "The next executor can pick up this branch from the worktree.\n\n"
        "The value was recorded in (Program 7).\n"
    )
    _track(root)

    report = audit(root)

    assert [(finding.rule, finding.line) for finding in report.advisories] == [
        ("provenance", 9),
    ]


def test_audit_gates_ignored_predecessor_markers_in_configured_repositories(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "README.md").write_text(
        "# Project\n\n"
        f"<!-- {predecessor}:policy register-v2 -->\n"
        "Current repository guidance stays attached to its defining source.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert [
        (finding.rule, finding.path, finding.line, finding.detail)
        for finding in report.findings
        if finding.rule == "predecessor-marker"
    ] == [
        (
            "predecessor-marker",
            "README.md",
            3,
            "predecessor policy marker is ignored; migrate it to a sourcebound marker",
        ),
    ]


@pytest.mark.parametrize("separator", ["-", "_"])
def test_corpus_orders_predecessor_markers_before_other_document_findings(
    tmp_path: Path,
    separator: str,
) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + separator + "docs"
    (root / "STATUS.md").write_text(
        "# Status\n\n"
        f"<!-- {predecessor}:policy register-v2 -->\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert [
        (finding.rule, finding.doc, finding.line)
        for finding in scan_corpus(root)
    ] == [
        ("predecessor-marker", "STATUS.md", 3),
        ("surface", "STATUS.md", 1),
    ]


def test_audit_does_not_confuse_current_markers_or_plain_prose_for_predecessors(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n\n"
        "<!-- sourcebound:policy register-v2 -->\n"
        "Clean docs help readers, but only explicit current markers activate policy.\n"
    )
    _track(root)

    report = audit(root)

    assert "predecessor-marker" not in {
        finding.rule for finding in (*report.findings, *report.advisories)
    }


def test_corpus_ignores_predecessor_markers_in_fenced_examples(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        "Use this example to recognize the predecessor marker before replacing it.\n\n"
        "```markdown\n"
        f"<!-- {predecessor}:policy register-v2 -->\n"
        "```\n"
    )
    _track(root)

    report = audit(root)

    assert "predecessor-marker" not in {
        finding.rule for finding in (*report.findings, *report.advisories)
    }


@pytest.mark.parametrize(
    "example",
    [
        "- Example:\n\n    ~~~markdown\n"
        "    <!-- sourcebound:role reference -->\n"
        "    <!-- {predecessor}:policy register-v2 -->\n"
        "    ~~~~~\n",
        "> ```markdown\n"
        "> <!-- sourcebound:role reference -->\n"
        "> <!-- {predecessor}:policy register-v2 -->\n"
        "> `````\n",
        "- > ~~~markdown\n"
        "  > <!-- sourcebound:role reference -->\n"
        "  > <!-- {predecessor}:policy register-v2 -->\n"
        "  > ~~~~~\n",
        "- > ```markdown\n"
        "  > <!-- sourcebound:role reference -->\n"
        "  > <!-- {predecessor}:policy register-v2 -->\n"
        "  > `````\n",
    ],
)
def test_corpus_masks_authority_inside_container_fences(
    tmp_path: Path,
    example: str,
) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n" + example.format(predecessor=predecessor)
    )
    _track(root)

    report = audit(root)
    profile = next(item for item in report.document_profiles if item.path == "README.md")

    assert profile.role == "overview"
    assert "predecessor-marker" not in {
        finding.rule for finding in (*report.findings, *report.advisories)
    }


@pytest.mark.parametrize(
    "opening",
    [
        "> ```markdown\n> example\n\n",
        "- Example:\n\n    ```markdown\n    example\n",
    ],
)
def test_container_fence_does_not_mask_authority_after_container_exit(
    opening: str,
) -> None:
    predecessor = "clean" + "-docs"
    text = opening + f"<!-- {predecessor}:policy register-v2 -->\n"

    assert [
        (line, marker.group())
        for line, marker in _active_predecessor_markers(text)
    ] == [(text.count("\n"), f"<!-- {predecessor}:policy register-v2 -->")]


def test_corpus_ignores_inline_examples_but_finds_active_predecessor_markers(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "_docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        f"Replace `<!-- {predecessor}:policy register-v2 -->` when it appears as a comment.\n"
        f"<!-- {predecessor}:policy register-v2 -->\n"
    )
    _track(root)
    active_line = next(
        line_number
        for line_number, line in enumerate(
            (root / "README.md").read_text().splitlines(), start=1
        )
        if line.startswith(f"<!-- {predecessor}:")
    )

    report = audit(root)

    assert [
        (finding.rule, finding.path, finding.line)
        for finding in (*report.findings, *report.advisories)
        if finding.rule == "predecessor-marker"
    ] == [("predecessor-marker", "README.md", active_line)]


def test_corpus_handles_long_unclosed_backtick_runs_in_bounded_time(
) -> None:
    predecessor = "clean" + "-docs"
    text = "x" + ("`" * 1_000_000) + f"<!-- {predecessor}:policy register-v2 -->\n"

    started = time.monotonic()
    markers = list(_active_predecessor_markers(text))
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert [(line, marker.group()) for line, marker in markers] == [
        (1, f"<!-- {predecessor}:policy register-v2 -->")
    ]


def test_corpus_handles_many_escaped_backticks_in_linear_time() -> None:
    predecessor = "clean" + "-docs"
    text = (r"\`" * 100_000) + f"<!-- {predecessor}:policy register-v2 -->\n"

    started = time.monotonic()
    markers = list(_active_predecessor_markers(text))
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert [(line, marker.group()) for line, marker in markers] == [
        (1, f"<!-- {predecessor}:policy register-v2 -->")
    ]


@pytest.mark.parametrize("indent", ["    ", "\t", "  \t"])
def test_corpus_ignores_predecessor_markers_in_indented_code(
    tmp_path: Path,
    indent: str,
) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        f"{indent}<!-- {predecessor}:policy register-v2 -->\n"
    )
    _track(root)

    report = audit(root)

    assert "predecessor-marker" not in {
        finding.rule for finding in (*report.findings, *report.advisories)
    }


def test_corpus_keeps_three_space_indented_comments_active(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        f"   <!-- {predecessor}:policy register-v2 -->\n"
    )
    _track(root)
    active_line = next(
        line_number
        for line_number, line in enumerate(
            (root / "README.md").read_text().splitlines(), start=1
        )
        if line.startswith(f"   <!-- {predecessor}:")
    )

    report = audit(root)

    assert [
        (finding.rule, finding.path, finding.line)
        for finding in (*report.findings, *report.advisories)
        if finding.rule == "predecessor-marker"
    ] == [("predecessor-marker", "README.md", active_line)]


def test_corpus_keeps_indented_list_comments_active(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        "- Replace active legacy comments.\n"
        f"    <!-- {predecessor}:policy register-v2 -->\n"
    )
    _track(root)
    marker_line = next(
        number
        for number, line in enumerate((root / "README.md").read_text().splitlines(), 1)
        if predecessor in line
    )

    report = audit(root)

    assert [
        (finding.rule, finding.path, finding.line)
        for finding in (*report.findings, *report.advisories)
        if finding.rule == "predecessor-marker"
    ] == [("predecessor-marker", "README.md", marker_line)]


def test_corpus_keeps_comments_between_escaped_backticks_active(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        f"\\`<!-- {predecessor}:policy register-v2 -->\\`\n"
    )
    _track(root)
    marker_line = next(
        number
        for number, line in enumerate((root / "README.md").read_text().splitlines(), 1)
        if predecessor in line
    )

    report = audit(root)

    assert [
        (finding.rule, finding.path, finding.line)
        for finding in (*report.findings, *report.advisories)
        if finding.rule == "predecessor-marker"
    ] == [("predecessor-marker", "README.md", marker_line)]


def test_corpus_ignores_predecessor_markers_in_multiline_code_spans(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        "`example\n"
        f"<!-- {predecessor}:purpose -->\n"
        "ends`\n"
    )
    _track(root)

    report = audit(root)

    assert "predecessor-marker" not in {
        finding.rule for finding in (*report.findings, *report.advisories)
    }


def test_corpus_does_not_close_fences_with_trailing_content(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    (root / "README.md").write_text(
        "# Migration\n\n"
        "```markdown\n"
        "```not-a-close\n"
        f"<!-- {predecessor}:purpose -->\n"
        "```\n"
    )
    _track(root)

    report = audit(root)

    assert "predecessor-marker" not in {
        finding.rule for finding in (*report.findings, *report.advisories)
    }


@pytest.mark.parametrize("separator", ["-", "_"])
@pytest.mark.parametrize(
    "comment",
    [
        "<!-- {marker}:purpose -->",
        "{{/* {marker}:policy register-v2 */}}",
    ],
)
def test_corpus_finds_markdown_and_mdx_predecessor_markers(
    tmp_path: Path,
    separator: str,
    comment: str,
) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + separator + "docs"
    (root / "README.mdx").write_text(
        "# Migration\n\n" + comment.format(marker=predecessor) + "\n"
    )
    _track(root)

    report = audit(root)

    assert [
        (finding.rule, finding.path, finding.line)
        for finding in (*report.findings, *report.advisories)
        if finding.rule == "predecessor-marker"
    ] == [("predecessor-marker", "README.mdx", 3)]


@pytest.mark.parametrize(
    ("separator", "comment"),
    [
        (" ", "<!-- {marker}:policy register-v2 -->"),
        ("-", "<!-- {marker} policy register-v2 -->"),
        ("_", "{{/* {marker} policy register-v2 */}}"),
        (None, "{{/* sourcebound:policy register-v2 */}}"),
    ],
)
def test_corpus_ignores_malformed_and_current_policy_comments(
    tmp_path: Path,
    separator: str | None,
    comment: str,
) -> None:
    root = _repo(tmp_path)
    marker = "sourcebound" if separator is None else "clean" + separator + "docs"
    text = comment.format(marker=marker)
    (root / "README.mdx").write_text(f"# Project\n\n{text}\n")
    _track(root)

    report = audit(root)

    assert "predecessor-marker" not in {
        finding.rule for finding in (*report.findings, *report.advisories)
    }


def test_audit_requires_the_purpose_contract_before_body_content(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n"
        "<!-- sourcebound:policy register-v2 -->\n"
        '<!-- sourcebound:allow preamble-contract reason="Fixture isolates purpose policy" -->\n'
        '<!-- sourcebound:allow readme-routing reason="Fixture isolates purpose policy" -->\n\n'
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
        "<!-- sourcebound:policy register-v2 -->\n"
        '<!-- sourcebound:allow preamble-contract reason="Fixture isolates booster policy" -->\n'
        '<!-- sourcebound:allow readme-routing reason="Fixture isolates booster policy" -->\n\n'
        "<!-- sourcebound:purpose -->\n"
        "Use this page when source claims can drift. It gives maintainers a checked repair path.\n"
        "<!-- sourcebound:end purpose -->\n\nA powerful workflow.\n"
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
            "<!-- sourcebound:policy register-v2 -->\n"
            "<!-- sourcebound:purpose -->\n"
            f"{purpose}\n"
            "<!-- sourcebound:end purpose -->\n"
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
            "<!-- sourcebound:policy register-v2 -->\n"
            "<!-- sourcebound:purpose -->\n"
            f"Use this reference when looking up {subject}. "
            "The page keeps exact values in one literal lookup surface.\n"
            "<!-- sourcebound:end purpose -->\n"
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
    bundle = root / ".sourcebound/context/contributor.md"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(
        "# Context bundle\n\n"
        "Canonical factual guidance with enough distinct words for corpus analysis.\n"
    )
    _track(root)

    report = audit(root)

    assert report.findings == ()
    assert report.documents == ("README.md",)
    assert report.ignored_documents == (".sourcebound/context/contributor.md",)


def test_generated_reader_output_is_reference_not_authored_task(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    generated = root / "docs/generated/system-flow.md"
    generated.parent.mkdir(parents=True)
    generated.write_text(
        "<!-- sourcebound:role reference -->\n"
        '<figure data-layout="position annotation verification">\n'
        "<figcaption>Repository facts flow into a deterministic check.</figcaption>\n"
        "</figure>\n"
    )
    tutorial = root / "docs/generated/tutorial.md"
    tutorial.write_text(
        "# Queue tutorial\n\n"
        "Follow this generated exercise to learn the queue recovery sequence.\n"
    )
    _track(root)

    report = audit(root, preview_policy=True)

    profile = next(
        item for item in report.document_profiles if item.path == "docs/generated/system-flow.md"
    )
    assert profile.role == "reference"
    tutorial_profile = next(
        item for item in report.document_profiles if item.path == "docs/generated/tutorial.md"
    )
    assert tutorial_profile.role == "tutorial"
    assert not any(
        finding.path == "docs/generated/system-flow.md"
        and finding.rule in {"purpose-contract", "nominalization-density"}
        for finding in report.advisories
    )


@pytest.mark.parametrize(
    "filename",
    [
        "REFERENCES.md",
        "SCHEMAS.md",
        "STANDARDS.md",
        "SPECS.md",
        "POLICIES.md",
        "CONTRACTS.md",
    ],
)
def test_plural_lookup_filenames_remain_reference_pages(
    tmp_path: Path,
    filename: str,
) -> None:
    root = _repo(tmp_path)
    (root / filename).write_text(
        f"# {Path(filename).stem.title()}\n\n"
        "Look up the exact repository contract in this page.\n"
    )
    _track(root)

    report = audit(root, preview_policy=True)

    profile = next(item for item in report.document_profiles if item.path == filename)
    assert profile.role == "reference"
    assert not any(
        finding.path == filename and finding.rule == "purpose-contract"
        for finding in report.advisories
    )


def test_help_actions_and_architecture_receipts_keep_their_reader_jobs(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    pages = {
        "docs/help/index.md": "# Help\n\nChoose the task that matches the current operation.\n",
        "docs/help/review-and-approve.md": "# Review and approve\n\nReview the exact payload before approval.\n",
        "docs/help/read-a-receipt.md": "# Read a receipt\n\nUse the recorded outcome to check the operation.\n",
        "docs/help/review-a-recovery.md": "# Review a recovery\n\nApprove only the supported recovery payload.\n",
        "docs/operations/recovery.md": "# Recovery\n\nDiagnose the failed operation, apply the bounded repair, then verify the result.\n",
        "docs/help/inspect-receipts.md": "# Inspect receipts\n\nInspect the outcome without changing it.\n",
        "docs/help/developer-reference.md": "# Developer reference\n\nLook up the current integration boundary.\n",
        "docs/decisions/0001-split-receipts.md": "# Split receipts\n\n## Decision\n\nKeep public and private evidence separate.\n",
        "artifacts/evidence/local-receipt.md": "# Local receipt\n\nObserved result from the local verification run.\n",
    }
    for relative, content in pages.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _track(root)

    report = audit(root)
    profiles = {profile.path: profile.role for profile in report.document_profiles}

    assert profiles == {
        "artifacts/evidence/local-receipt.md": "evidence",
        "docs/decisions/0001-split-receipts.md": "architecture",
        "docs/help/index.md": "component-overview",
        "docs/help/developer-reference.md": "reference",
        "docs/help/inspect-receipts.md": "task",
        "docs/help/read-a-receipt.md": "task",
        "docs/help/review-and-approve.md": "task",
        "docs/help/review-a-recovery.md": "task",
        "docs/operations/recovery.md": "troubleshooting",
    }
    assert not any(
        finding.rule == "process-artifact"
        for finding in report.advisories
    )


def test_audit_classifies_audits_as_evidence_and_flags_unanchored_current_claims(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "AUDIT.md").write_text(
        "# Security audit\n\nThe current result closes every reproduced hole.\n"
    )
    _track(root)

    report = audit(root)

    profiles = {profile.path: profile.role for profile in report.document_profiles}
    assert profiles["AUDIT.md"] == "evidence"
    assert [
        (finding.rule, finding.path, finding.detail)
        for finding in report.advisories
        if finding.rule == "evidence-time-horizon"
    ] == [
        (
            "evidence-time-horizon",
            "AUDIT.md",
            "replace relative-time evidence claims with a capture date or immutable commit",
        )
    ]


def test_audit_accepts_dated_evidence(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "AUDIT.md").write_text(
        "# Security audit\n\nCaptured 2026-07-21.\n\n"
        "The current result closes every reproduced hole.\n"
    )
    _track(root)

    report = audit(root)

    assert "evidence-time-horizon" not in {
        finding.rule for finding in report.advisories
    }


@pytest.mark.parametrize(
    "claim",
    [
        "The build passes today.",
        "The build currently passes.",
        "This archive is not current proof, but the current build passes.",
    ],
)
def test_audit_flags_affirmative_relative_claims_per_clause(
    tmp_path: Path,
    claim: str,
) -> None:
    root = _repo(tmp_path)
    (root / "AUDIT.md").write_text(f"# Build audit\n\n{claim}\n")
    _track(root)

    report = audit(root)

    assert "evidence-time-horizon" in {
        finding.rule for finding in report.advisories
    }


def test_audit_accepts_only_a_commit_that_exists_in_the_repository(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "seed.txt").write_text("seed\n")
    _track(root)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "seed",
        ],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (root / "AUDIT.md").write_text(
        f"# Security audit\n\nCommit {commit}.\n\n"
        "The current result closes every reproduced hole.\n"
    )
    _track(root)

    report = audit(root)

    assert "evidence-time-horizon" not in {
        finding.rule for finding in report.advisories
    }


def test_audit_accepts_a_multiline_snapshot_receipt(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "seed.txt").write_text("seed\n")
    _track(root)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "seed",
        ],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (root / "AUDIT.md").write_text(
        "# Security audit\n\n"
        "> **Snapshot, not current authority.** This audit records commit\n"
        f"> [{commit[:7]}](https://example.invalid/commit/{commit})\n"
        "> as inspected on 2026-07-21.\n\n"
        "The current result closes every reproduced hole.\n"
    )
    _track(root)

    report = audit(root)

    assert "evidence-time-horizon" not in {
        finding.rule for finding in report.advisories
    }


@pytest.mark.parametrize(
    "invalid_anchor",
    [
        "Captured 2026-99-99.",
        "Captured 2099-01-01.",
        "Commit " + ("a" * 40) + ".",
    ],
)
def test_audit_rejects_invalid_evidence_anchors(
    tmp_path: Path,
    invalid_anchor: str,
) -> None:
    root = _repo(tmp_path)
    (root / "AUDIT.md").write_text(
        f"# Security audit\n\n{invalid_anchor}\n\n"
        "The current result closes every reproduced hole.\n"
    )
    _track(root)

    report = audit(root)

    assert "evidence-time-horizon" in {
        finding.rule for finding in report.advisories
    }


def test_evidence_time_horizon_ignores_examples_and_negated_boundaries(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    evidence = root / "evidence/README.md"
    evidence.parent.mkdir()
    evidence.write_text(
        "# Historical receipts\n\n"
        "Inspect a release-scoped receipt without mistaking it for a claim about the current build.\n"
        "Past receipts are not current proof and must not be treated as current behavior.\n\n"
        "```text\nThe current result passes.\nCaptured 2026-99-99.\n```\n"
        "Current documentation, not this archive, owns supported behavior.\n"
    )
    _track(root)

    report = audit(root)

    assert "evidence-time-horizon" not in {
        finding.rule for finding in report.advisories
    }


@pytest.mark.parametrize(
    ("path", "expected_role"),
    [
        ("docs/EVALUATION.md", "task"),
        ("docs/REVIEW_LEDGER.md", "reference"),
        ("contracts/API.md", "reference"),
        ("schemas/EVENTS.md", "reference"),
        ("standards/WRITING.md", "reference"),
        ("policies/SECURITY.md", "reference"),
        ("apis/HTTP.md", "reference"),
    ],
)
def test_ambiguous_operational_names_and_reference_directories_keep_reader_roles(
    tmp_path: Path,
    path: str,
    expected_role: str,
) -> None:
    root = _repo(tmp_path)
    document = root / path
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(
        "# Document\n\nUse this page to inspect the supported interface.\n"
    )
    _track(root)

    report = audit(root)

    assert report.document_profiles[0].role == expected_role


@pytest.mark.parametrize(
    "unrelated_anchor",
    ["A prior run completed on 2026-01-02.", "Example commit " + ("b" * 40) + "."],
)
def test_audit_does_not_let_later_dates_or_commits_anchor_current_evidence(
    tmp_path: Path,
    unrelated_anchor: str,
) -> None:
    root = _repo(tmp_path)
    (root / "AUDIT.md").write_text(
        "# Security audit\n\n"
        "The current result closes every reproduced hole.\n\n"
        + "\n".join(f"Context line {index}." for index in range(12))
        + f"\n\n{unrelated_anchor}\n"
    )
    _track(root)

    report = audit(root)

    assert "evidence-time-horizon" in {
        finding.rule for finding in report.advisories
    }


def test_top_level_dispatch_is_process_residue_but_domain_dispatch_help_is_not(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "DISPATCH.md").write_text(
        "# Executor dispatch\n\n"
        "The next executor should pick up this branch and verify the worktree.\n"
    )
    help_page = root / "docs/help/check-an-uncertain-dispatch.md"
    help_page.parent.mkdir(parents=True)
    help_page.write_text(
        "# Check an uncertain dispatch\n\n"
        "Inspect the delivery record before confirming the dispatch state.\n"
    )
    _track(root)

    report = audit(root)
    process_paths = {
        finding.path
        for finding in report.advisories
        if finding.rule == "process-artifact"
    }

    assert process_paths == {"DISPATCH.md"}


def test_explicit_evidence_role_keeps_an_intentional_generated_report(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    report_path = root / "generated/setup-report.md"
    report_path.parent.mkdir()
    report_path.write_text(
        "# Generated setup report\n\n"
        "<!-- sourcebound:role evidence -->\n\n"
        "Captured 2026-07-21.\n\nThe report records the generated fixture result.\n"
    )
    _track(root)

    report = audit(root)

    assert not any(
        finding.rule == "process-artifact"
        for finding in (*report.findings, *report.advisories)
    )


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


def test_hidden_markdown_still_rejects_active_predecessor_markers(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    predecessor = "clean" + "-docs"
    workflow_note = root / ".github/WORKFLOW.md"
    workflow_note.parent.mkdir(parents=True)
    workflow_note.write_text(
        "# Workflow\n\n"
        f"<!-- {predecessor}:policy register-v2 -->\n"
    )
    _track(root)

    report = audit(root)

    assert [(finding.rule, finding.path) for finding in report.advisories] == [
        ("predecessor-marker", ".github/WORKFLOW.md"),
    ]


def test_packaged_standard_assets_are_not_reader_documents(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    asset = root / "src/sourcebound/standards/exemplars.md"
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
        "src/sourcebound/standards/exemplars.md",
        "build/lib/sourcebound/standards/exemplars.md",
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
        "evidence-time-horizon": 1,
        "process-artifact": 1,
    }
    assert report.findings == ()
    assert not report.repository_integrity_enforced
    assert report.policy_preview
    assert dict(report.advisory_totals) == {
        "broken-local-link": 1,
        "evidence-time-horizon": 1,
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
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "README.md").write_text(
        "# Project\n\n[Missing](docs/missing.md)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.repository_integrity_enforced
    assert [(finding.rule, finding.path) for finding in report.findings] == [
        ("broken-local-link", "README.md"),
    ]


def test_manifest_keeps_test_fixture_machine_paths_advisory(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    fixture = root / "src/__tests__/paths.test.ts"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        "const paths = ['/" + "Users/alice/project', 'src/index.ts']\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.repository_integrity_enforced
    assert not any(
        finding.rule == "local-path-residue" for finding in report.findings
    )
    assert any(
        finding.rule == "local-path-residue"
        and finding.path == "src/__tests__/paths.test.ts"
        for finding in report.advisories
    )


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
        "<!-- sourcebound:role template -->\n"
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
        "# Project\n\n<!-- sourcebound:role brochure -->\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    assert [
        (finding.rule, finding.detail) for finding in audit(root).findings
    ] == [
        ("invalid-document-role", "unsupported sourcebound role: brochure"),
    ]


def test_role_and_register_examples_do_not_activate_policy(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    tutorial = root / "docs/tutorial.md"
    tutorial.parent.mkdir()
    tutorial.write_text(
        "# Tutorial\n\n"
        "Show readers the marker syntax without activating it.\n\n"
        "```markdown\n"
        "<!-- sourcebound:role reference -->\n"
        f"{REGISTER_PROFILE}\n"
        "```\n"
        "Use the next step to verify the example.\n"
    )
    _track(root)

    report = audit(root)

    assert report.document_profiles[0].role == "tutorial"
    assert report.document_profiles[0].registered is False
    assert report.findings == ()


def test_mdx_exported_marker_strings_do_not_activate_authority(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    tutorial = root / "docs/tutorial.mdx"
    tutorial.parent.mkdir()
    tutorial.write_text(
        'export const example = "<!-- sourcebound:role reference -->"\n\n'
        'export const policy = "<!-- sourcebound:policy register-v2 -->"\n\n'
        "# Tutorial\n\nFollow the steps to verify the example.\n"
    )
    _track(root)

    report = audit(root)

    assert report.document_profiles[0].role == "tutorial"
    assert report.document_profiles[0].registered is False
    assert report.findings == ()


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
            "<!-- sourcebound:purpose -->\n"
            "Maintainers use this page to inspect the current system boundary before changing it.\n"
            "<!-- sourcebound:end purpose -->\n\n"
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
        "<!-- sourcebound:purpose -->\n"
        "Operators use this page to diagnose and recover a failing service.\n"
        "<!-- sourcebound:end purpose -->\n\n"
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


def test_corpus_advisories_are_bounded_without_hiding_totals(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    assert len([
        finding
        for finding in report.advisory_occurrences
        if finding.rule == "process-artifact"
    ]) == 12
    assert report.ok

    assert main(["--root", str(root), "audit", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len([
        finding
        for finding in payload["advisory_occurrences"]
        if finding["rule"] == "process-artifact"
    ]) == 12


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
    source = root / "src/example file.ts"
    source.parent.mkdir()
    source.write_text("export const value = 1\nexport const other = 2\n")
    tracked = docs / "present.md"
    tracked.write_text("# Present\n")
    (docs / "guide.md").write_text("# Guide\n")
    (root / "README.md").write_text(
        "# Project\n\n"
        "[Sparse target](docs/present.md)\n"
        "[Repository root](/docs/present.md)\n"
        "[Missing root document](/docs/missing-root.md)\n"
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
        ("broken-local-link", "target does not exist: /docs/missing-root.md"),
        ("broken-local-link", "target does not exist: …"),
        ("broken-local-link", "target does not exist: docs/<package>/README.md"),
    ]
    assert dict(report.advisory_totals)["broken-local-link"] == 5
    assert not report.repository_integrity_enforced


def test_local_link_fragments_resolve_rendered_markdown_anchors(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    docs = root / "docs"
    docs.mkdir()
    (docs / "target.md").write_text(
        "# Café guide\n\n"
        "## Use `sourcebound check`\n\n"
        "## Server &amp; client components\n\n"
        "## Repeated heading\n\n"
        "## Repeated heading\n\n"
        '<a id="manual-anchor"></a>\n'
    )
    (root / "README.md").write_text(
        "# Project\n\n"
        "[Encoded heading](docs/target.md#caf%C3%A9-guide)\n"
        "[Inline code heading](docs/target.md#use-sourcebound-check)\n"
        "[Punctuation spacing](docs/target.md#server--client-components)\n"
        "[Duplicate heading](docs/target.md#repeated-heading-1)\n"
        "[Explicit anchor](docs/target.md#manual-anchor)\n"
        "[Same page](#project)\n"
        "[Source lines](src/example%20file.ts#L1-L2)\n"
        "[Missing fragment](docs/target.md#missing-heading)\n"
        "[External fragment](https://example.com/docs#not-local)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert [
        (finding.rule, finding.detail)
        for finding in report.advisories
        if finding.rule == "broken-local-fragment"
    ] == [
        (
            "broken-local-fragment",
            "target fragment does not exist: docs/target.md#missing-heading",
        )
    ]


def test_registered_repository_keeps_inferred_fragments_advisory(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "README.md").write_text(
        "# Project\n\n[Missing section](#not-a-section)\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.findings == ()
    assert [finding.rule for finding in report.advisories] == [
        "broken-local-fragment"
    ]


def test_duplicate_primary_headings_are_an_information_architecture_advisory(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n\n"
        "## Context request\n\nFirst owner.\n\n"
        "### Detail\n\n"
        "## Context request\n\nSecond owner.\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert [
        (finding.rule, finding.line)
        for finding in report.advisories
        if finding.rule == "duplicate-heading"
    ] == [("duplicate-heading", 9)]


def test_duplicate_lower_or_different_level_headings_do_not_trigger_primary_advisory(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n\n"
        "## Contract\n\n"
        "### Contract\n\n"
        "### Detail\n\n"
        "### Detail\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert not any(
        finding.rule == "duplicate-heading" for finding in report.advisories
    )


def test_inline_document_paths_remain_advisory_without_an_intent_contract(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    docs = root / "docs"
    docs.mkdir()
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "STATUS.md").write_text("# Status\n")
    (docs / "present.md").write_text("# Present\n")
    (docs / "guide.md").write_text(
        "# Guide\n\n"
        '<!-- sourcebound:allow-inline-document target="docs/generated-later.md" '
        'reason="The documented command creates this reserved output" -->\n'
        '<!-- sourcebound:allow-inline-document target="docs/weak.md" reason="future" -->\n'
        '`<!-- sourcebound:allow-inline-document target="docs/inline-grant.md" '
        'reason="Inline code must not grant an exception" -->`\n'
        "Read `docs/present.md` and root `STATUS.md`.\n"
        "A setup command creates `docs/generated-later.md`.\n"
        "A vague exception cannot hide `docs/weak.md`.\n"
        "Inline example cannot hide `docs/inline-grant.md`.\n"
        "The stale receipt is `docs/PROGRAM_REPORT_99.md`.\n"
        "Ignore `module.py:12`, `docs/*.md`, and `docs/<name>.md`.\n\n"
        "```markdown\n"
        "docs/FENCED_MISSING.md\n```\n"
    )
    _track(root)

    report = audit(root)

    assert [
        (finding.rule, finding.path, finding.detail)
        for finding in report.advisories
        if finding.rule == "missing-inline-document"
    ] == [
        (
            "missing-inline-document",
            "docs/guide.md",
            "verify whether this inline document path should exist: docs/weak.md",
        ),
        (
            "missing-inline-document",
            "docs/guide.md",
            "verify whether this inline document path should exist: docs/inline-grant.md",
        ),
        (
            "missing-inline-document",
            "docs/guide.md",
            "verify whether this inline document path should exist: docs/PROGRAM_REPORT_99.md",
        ),
    ]


def test_fenced_inline_document_allowance_does_not_grant_an_exception(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    docs = root / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\n"
        "```markdown\n"
        '<!-- sourcebound:allow-inline-document target="docs/fenced-grant.md" '
        'reason="Fenced examples must not grant an exception" -->\n'
        "```\n\n"
        "Read `docs/fenced-grant.md`.\n"
    )
    _track(root)

    report = audit(root)

    assert any(
        finding.rule == "missing-inline-document"
        and finding.path == "docs/guide.md"
        and finding.detail.endswith("docs/fenced-grant.md")
        for finding in report.advisories
    )
    assert report.ok


def test_inline_document_negative_and_runtime_examples_never_become_gates(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "GUIDE.md").write_text(
        "# Path states\n\n"
        "The historical `docs/OLD.md` no longer exists.\n"
        "Without `rules.md`, the command uses its fallback.\n"
        "Each run may create `dispatch.md`; a user can add `notes.md`.\n"
    )
    _track(root)

    report = audit(root)
    inline = [
        finding
        for finding in report.advisories
        if finding.rule == "missing-inline-document"
    ]

    assert report.ok
    assert {finding.detail.rsplit(": ", 1)[-1] for finding in inline} == {
        "docs/OLD.md",
        "rules.md",
        "dispatch.md",
    }
    assert dict(report.advisory_totals)["missing-inline-document"] == 4


def test_placeholder_links_are_role_scoped_and_parse_complete_destinations(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    agent_doc = root / "AGENTS.md"
    agent_doc.write_text(
        "# Agent procedure\n\n"
        "[Docs]([area docs url])\n"
        "[Real bracket path](docs/[version]/guide.md)\n"
        "`[Inline]([inline placeholder])`\n\n"
        "```markdown\n[Fenced]([fenced placeholder])\n```\n"
    )
    guide = root / "GUIDE.md"
    guide.write_text("# Guide\n\n[Docs]([area docs url])\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)
    advisories = {
        (finding.rule, finding.path, finding.detail)
        for finding in report.advisories
    }

    assert (
        "placeholder-link",
        "AGENTS.md",
        "template destination is unresolved: [area docs url]",
    ) in advisories
    assert (
        "broken-local-link",
        "GUIDE.md",
        "target does not exist: [area docs url]",
    ) in advisories
    assert (
        "broken-local-link",
        "AGENTS.md",
        "target does not exist: docs/[version]/guide.md",
    ) in advisories
    assert not any("inline placeholder" in item[2] for item in advisories)
    assert not any("fenced placeholder" in item[2] for item in advisories)


def test_frontmatter_requires_document_start_and_closing_delimiter(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    skill = root / "skills/deploy/guide.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: deploy\n---\n# Deploy\n\nRun the deployment check.\n")
    later_rule = root / "GUIDE.md"
    later_rule.write_text("# Guide\n\nA horizontal rule follows.\n\n---\n")
    malformed = root / "BROKEN.md"
    malformed.write_text(
        "---\nname: broken\n"
        "<!-- sourcebound:role reference -->\n"
        "# Broken\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)
    profiles = {item.path: item.role for item in report.document_profiles}

    assert profiles["skills/deploy/guide.md"] == "agent-procedure"
    assert profiles["GUIDE.md"] == "task"
    assert profiles["BROKEN.md"] == "reference"
    assert any(
        finding.rule == "malformed-frontmatter"
        and finding.path == "BROKEN.md"
        for finding in report.findings
    )


def test_audit_checks_structurally_valid_mdx_without_executing_templates(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("# Project\n")
    (root / "guide.md").write_text("# Linked guide\n")
    (root / "guide.mdx").write_text(
        "---\n"
        "title: MDX guide\n"
        "---\n\n"
        "import Escaping from '../../outside.js'\n\n"
        "# MDX guide\n\n"
        "<Callout tone=\"[not a link](missing-attribute.md)\">\n"
        "Read [the guide](guide.md).\n"
        "Read [the missing page](missing-real.md).\n"
        "</Callout>\n\n"
        "```md\n"
        "[not a link](missing-fence.md)\n"
        "```\n\n"
        "{/* [not a link](missing-comment.md) */}\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.ok
    assert report.documents == ("README.md", "guide.md", "guide.mdx")
    assert report.unsupported_documents == ()
    mdx_link_findings = [
        finding
        for finding in (*report.findings, *report.advisories)
        if finding.rule == "broken-local-link" and finding.path == "guide.mdx"
    ]
    assert [finding.detail for finding in mdx_link_findings] == [
        "target does not exist: missing-real.md"
    ]


def test_audit_fails_closed_on_malformed_mdx(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "README.md").write_text("# Project\n")
    (root / "broken.mdx").write_text("# Broken\n\n<Callout>\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert not report.ok
    assert report.unsupported_documents == ("broken.mdx",)
    assert any(
        finding.rule == "unsupported-mdx"
        and finding.path == "broken.mdx"
        and "closing tag" in finding.detail
        for finding in report.findings
    )


def test_audit_never_counts_mdx_as_checked_when_runtime_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "README.md").write_text("# Project\n")
    (root / "guide.mdx").write_text("# Guide\n\n<Component />\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    monkeypatch.setattr(
        "sourcebound.audit.parser_availability",
        lambda: (False, "Node.js executable not found"),
    )

    report = audit(root)

    assert report.documents == ("README.md",)
    assert report.unsupported_documents == ("guide.mdx",)
    assert any(
        finding.rule == "unsupported-mdx"
        and "Node.js executable not found" in finding.detail
        for finding in report.findings
    )


def test_audit_needs_no_node_for_markdown_only_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_mdx_runtime_check() -> tuple[bool, str]:
        raise AssertionError("Markdown audit invoked the MDX adapter")

    root = _repo(tmp_path)
    (root / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (root / "README.md").write_text("# Project\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    monkeypatch.setattr(
        "sourcebound.audit.parser_availability",
        unexpected_mdx_runtime_check,
    )

    report = audit(root)

    assert report.ok
    assert report.documents == ("README.md",)
    assert report.unsupported_documents == ()


def test_mdx_template_placeholder_is_advisory_not_a_broken_link(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    template = root / "templates/prompt.mdx"
    template.parent.mkdir()
    template.write_text(
        "# Prompt template\n\n"
        "{/* sourcebound:role template */}\n\n"
        "Read [the generated destination]({docs_url}).\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.ok
    assert any(
        finding.rule == "placeholder-link"
        and finding.path == "templates/prompt.mdx"
        for finding in report.advisories
    )
    assert not any(
        finding.rule == "broken-local-link"
        and finding.path == "templates/prompt.mdx"
        for finding in (*report.findings, *report.advisories)
    )


def test_agent_documentation_is_active_while_tool_context_stays_internal(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    skill = root / ".agents/skills/inspect/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Inspect\n\n[Missing](references/missing.md)\n")
    context = root / ".sourcebound/context/contributor.md"
    context.parent.mkdir(parents=True)
    context.write_text("# Generated context\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert report.documents == (".agents/skills/inspect/SKILL.md",)
    assert report.ignored_documents == (".sourcebound/context/contributor.md",)
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
    assert baseline_path == root / ".sourcebound/audit-baseline.json"

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


def test_audit_baseline_v2_is_line_stable_and_uses_multiset_identity(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        "# Project\n\n"
        "## Broken links\n\n"
        "[Missing](docs/missing.md)\n"
        "[Missing again](docs/missing.md)\n"
    )
    _track(root)
    baseline_path = write_audit_baseline(root)
    baseline = json.loads(baseline_path.read_text())

    assert baseline["schema"] == "sourcebound.audit-baseline.v2"
    assert all("line_hint" in item and "line" not in item for item in baseline["findings"])
    assert len({item["duplicate_ordinal"] for item in baseline["findings"]}) == 2

    text = readme.read_text()
    readme.write_text(text.replace("## Broken links", "Intro.\n\n## Broken links"))
    moved = audit(root)
    assert moved.ok
    assert len([
        item for item in moved.baselined_findings
        if item.rule == "broken-local-link"
    ]) == 2

    readme.write_text(
        readme.read_text().replace("[Missing](docs/missing.md)\n", "", 1)
    )
    repaired = audit(root)
    assert not repaired.ok
    assert len([
        item for item in repaired.baselined_findings
        if item.rule == "broken-local-link"
    ]) == 1
    assert len([
        item for item in repaired.stale_baseline
        if item.rule == "broken-local-link"
    ]) == 1


def test_audit_baseline_v2_detects_changed_identity_and_duplicate_entries(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("# Project\n\n[Missing](docs/missing.md)\n")
    _track(root)
    baseline_path = write_audit_baseline(root)
    baseline = json.loads(baseline_path.read_text())

    readme.write_text(readme.read_text().replace("missing.md", "moved.md"))
    report = audit(root)
    assert len(report.findings) == 1
    assert len(report.stale_baseline) == 1

    baseline["findings"].append(dict(baseline["findings"][0]))
    baseline_path.write_text(json.dumps(baseline))
    with pytest.raises(ConfigurationError, match="duplicate"):
        audit(root)


def test_audit_reads_v1_baseline_and_update_migrates_to_v2(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("# Project\n\n[Missing](docs/missing.md)\n")
    _track(root)
    finding = next(
        item for item in audit(root, use_baseline=False).findings
        if item.rule == "broken-local-link"
    )
    legacy_payload = json.dumps(
        {
            "detail": finding.detail,
            "line": finding.line,
            "path": finding.path,
            "rule": finding.rule,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    baseline_path = root / ".sourcebound/audit-baseline.json"
    baseline_path.parent.mkdir()
    baseline_path.write_text(json.dumps({
        "schema": "sourcebound.audit-baseline.v1",
        "findings": [{
            "fingerprint": hashlib.sha256(legacy_payload.encode()).hexdigest(),
            "rule": finding.rule,
            "path": finding.path,
            "line": finding.line,
            "detail": finding.detail,
        }],
    }))

    assert audit(root).ok
    write_audit_baseline(root)
    assert json.loads(baseline_path.read_text())["schema"] == (
        "sourcebound.audit-baseline.v2"
    )


def test_finding_fingerprint_ignores_display_line() -> None:
    first = AuditFinding("broken-local-link", "README.md", 4, "target does not exist: x")
    moved = AuditFinding("broken-local-link", "README.md", 40, "target does not exist: x")

    assert finding_fingerprint(first) == finding_fingerprint(moved)


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

    baseline = root / ".sourcebound/audit-baseline.json"
    assert main(["--root", str(root), "audit", "--update-baseline"]) == 0
    baseline.write_text(
        '{"schema":"sourcebound.audit-baseline.v1","findings":['
        '{"fingerprint":"tampered","rule":"broken-local-link",'
        '"path":"README.md","line":1,"detail":"target does not exist: missing.md"}]}'
    )
    assert main(["--root", str(root), "audit"]) == 2
    assert "fingerprint does not match" in capsys.readouterr().err
