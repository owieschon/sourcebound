from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from clean_docs import claims as claim_module
from clean_docs.applicability import classify_document
from clean_docs.claims import scan_source_claims
from clean_docs.changed import check_changed
from clean_docs.cli import main
from clean_docs.errors import ConfigurationError
from clean_docs.manifest import load_manifest
from clean_docs.outcomes import build_outcome_receipt


COUNT_CASES = (
    ("widgets", 2),
    ("gadgets", 3),
    ("sprockets", 4),
    ("batches", 5),
    ("queues", 6),
    ("workers", 7),
    ("routes", 8),
    ("events", 9),
    ("reports", 10),
    ("tasks", 11),
    ("rules", 12),
    ("fields", 13),
    ("models", 14),
    ("jobs", 15),
    ("hooks", 16),
    ("checks", 17),
    ("records", 18),
    ("groups", 5),
)


def _claim_repository(tmp_path: Path) -> Path:
    root = tmp_path / "claim-repository"
    (root / "component").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source_lines = [
        f"{subject.upper()} = {list(range(value))!r}"
        for subject, value in COUNT_CASES
    ]
    source_lines.extend(
        (
            "ACCOUNTS = Table(name='accounts', fields={"
            "'id': Field(), 'team_id': Field()})",
            "INSIGHTS = Table(name='insights', fields={"
            "'id': Field(), 'team_id': Field(), 'query': Field()})",
        )
    )
    (root / "component/catalog.py").write_text("\n".join(source_lines) + "\n")

    doc_lines = ["# Fixture claims", ""]
    for subject, value in COUNT_CASES:
        documented = 4 if subject == "groups" else value
        doc_lines.extend(
            (
                f"## {subject.title()}",
                "",
                f"The fixture contains {documented} {subject}.",
                "",
            )
        )
    doc_lines.extend(
        (
            "## Accounts",
            "",
            "### Columns",
            "",
            "Column | Type",
            "`id` | integer",
            "",
            "## Insights",
            "",
            "### Columns",
            "",
            "Column | Type",
            "`id` | integer",
            "`team_id` | integer",
            "`legacy` | text",
            "",
        )
    )
    (root / "component/reference.md").write_text("\n".join(doc_lines))
    (root / "README.md").write_text("# Fixture\n\n## API\n\nSee `catalog`.\n")

    check_lines: list[str] = []
    for subject, _value in COUNT_CASES:
        check_lines.extend(
            (
                f"  - id: {subject}-count",
                "    kind: count",
                "    doc: component/reference.md",
                f"    anchor: {subject}",
                f"    subject: {subject}",
                "    source: component/catalog.py",
                f"    locator: {subject.upper()}#count",
            )
        )
    for subject in ("accounts", "insights"):
        check_lines.extend(
            (
                f"  - id: {subject}-columns",
                "    kind: identifier-set",
                "    doc: component/reference.md",
                f"    anchor: {subject}",
                f"    subject: {subject}",
                "    source: component/catalog.py",
                f"    locator: {subject.upper()}.fields#keys",
            )
        )
    (root / ".sourcebound.yml").write_text(
        "version: 1\n"
        "bindings:\n"
        "  - id: catalog\n"
        "    type: symbol\n"
        "    doc: README.md\n"
        "    anchor: api\n"
        "    source: {path: component/catalog.py}\n"
        "source_claim_checks:\n"
        + "\n".join(check_lines)
        + "\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "claim fixture",
        ],
        check=True,
    )
    return root


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            message,
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _changed_claim_repository(tmp_path: Path) -> Path:
    root = tmp_path / "changed-claim-repository"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "src/widgets.py").write_text("WIDGETS = ['one', 'two']\n")
    (root / "src/gadgets.py").write_text("GADGETS = ['one', 'two']\n")
    (root / "docs/widgets.md").write_text(
        "# Widgets\n\n## Inventory\n\nThe service contains 2 widgets.\n"
    )
    (root / "docs/gadgets.md").write_text(
        "# Gadgets\n\n## Inventory\n\nThe service contains 2 gadgets.\n"
    )
    (root / "README.md").write_text("# Fixture\n\n## API\n\nSee `widgets`.\n")
    (root / ".sourcebound.yml").write_text("""\
version: 1
bindings:
  - id: widgets
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/widgets.py}
source_claim_checks:
  - id: widget-count
    kind: count
    doc: docs/widgets.md
    anchor: inventory
    subject: widgets
    source: src/widgets.py
    locator: WIDGETS#count
  - id: gadget-count
    kind: count
    doc: docs/gadgets.md
    anchor: inventory
    subject: gadgets
    source: src/gadgets.py
    locator: GADGETS#count
""")
    return root


def test_twenty_source_claim_rows_replay_with_three_true_mismatches(
    tmp_path: Path,
) -> None:
    root = _claim_repository(tmp_path)
    manifest = load_manifest(root / ".sourcebound.yml")

    report = scan_source_claims(root, manifest.source_claim_checks)

    assert len(report.results) == 20
    assert len([item for item in report.results if item.status == "current"]) == 17
    drift = [item for item in report.results if item.status == "drift"]
    assert {item.id for item in drift} == {
        "groups-count",
        "accounts-columns",
        "insights-columns",
    }
    assert all(item.source_digest and item.document_digest for item in drift)
    assert all(item.source_line >= 1 and item.locator for item in drift)
    assert report.missing == ()
    assert not report.ok


def test_unconfigured_discovery_is_assessment_only(
    tmp_path: Path,
) -> None:
    root = _claim_repository(tmp_path)

    report = scan_source_claims(root)

    assert report.authority == "assessment"
    assert report.ok
    assert report.results == ()
    assert sum(count for _status, count in report.candidate_totals) == 20
    assert len([item for item in report.candidates if item.status == "drift"]) == 3
    assert all(item.authority == "assessment" for item in report.candidates)
    assert report.as_dict()["candidate_population"] == 20
    assert report.as_dict()["candidate_shown"] == 20
    assert report.as_dict()["candidate_truncated"] == 0


def test_discovery_uses_locator_specificity_across_repository_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "locator-specificity"
    (root / "engine").mkdir(parents=True)
    (root / "guide/service").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "engine/schema.py").write_text(
        "ORDERS = Table(fields={'id': Field(), 'state': Field()})\n"
    )
    (root / "guide/service/fixtures.py").write_text(
        "BATCH_DATA = [Item(records=['one', 'two']), Item(records=['three'])]\n"
    )
    (root / "guide/service/reference.md").write_text("""\
# Service reference

## Batch volume

The fixture contains 2 batches. It includes 2 records.

## Orders

### Columns

Column | Type
`id` | integer
`legacy` | text
""")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = scan_source_claims(root)

    drift = {
        (item.subject, item.source, item.locator)
        for item in report.candidates
        if item.status == "drift"
    }
    assert drift == {
        ("records", "guide/service/fixtures.py", "BATCH_DATA.records#count"),
        ("order", "engine/schema.py", "ORDERS.fields#keys"),
    }
    current = {
        (item.subject, item.source, item.locator)
        for item in report.candidates
        if item.status == "current"
    }
    assert current == {
        ("batches", "guide/service/fixtures.py", "BATCH_DATA#count"),
    }


def test_mapping_fact_uses_effective_python_keys_once() -> None:
    facts = claim_module._source_facts(
        "catalog.py",
        (
            "FIELDS = {'id': 'first', 'id': 'replacement', 'name': 'visible'}\n"
            "FLAGS = {'ready', 'ready', 'blocked'}\n"
        ),
    )

    keys = next(fact for fact in facts if fact.locator == "FIELDS#keys")
    count = next(fact for fact in facts if fact.locator == "FIELDS#count")
    set_count = next(fact for fact in facts if fact.locator == "FLAGS#count")

    assert keys.value == ("id", "name")
    assert count.value == 2
    assert set_count.value == 2


def test_candidate_rank_requires_ownership_and_precedes_drift_status(
    tmp_path: Path,
) -> None:
    root = tmp_path / "candidate-ranking"
    (root / "docs").mkdir(parents=True)
    (root / "src").mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "docs/widgets.md").write_text(
        "# Widgets\n\n## Inventory\n\nThe service contains 2 widgets.\n"
    )
    (root / "src/widgets.py").write_text("WIDGETS = ['one', 'two']\n")
    for index in range(101):
        module = root / "deep/a/b/c/d" / f"module-{index:03d}"
        module.mkdir(parents=True)
        (module / "guide.md").write_text(
            "# Module\n\n## Items\n\nThe module contains 1 items.\n"
        )
        (module / "catalog.py").write_text("ITEMS = ['one', 'two']\n")
    unrelated_doc = claim_module.DocumentClaim(
        "count",
        "connectors/factorial/guide.md",
        "sync-modes",
        1,
        "days",
        30,
        "doc",
    )
    unrelated_fact = claim_module.SourceFact(
        "count",
        "connectors/llama/settings.py",
        "DAY_INCREMENTAL#count",
        1,
        ("day", "incremental"),
        4,
        "source",
    )

    assert claim_module._relationship_rank(unrelated_doc, unrelated_fact) == 0

    report = scan_source_claims(root)
    payload = report.as_dict()

    assert payload["candidate_population"] == 102
    assert payload["candidate_shown"] == 100
    assert payload["candidate_truncated"] == 2
    assert any(
        item.doc == "docs/widgets.md"
        and item.source == "src/widgets.py"
        and item.status == "current"
        for item in report.candidates
    )


def test_enforcement_reads_only_accepted_relationship_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _claim_repository(tmp_path)
    manifest = load_manifest(root / ".sourcebound.yml")

    def reject_repository_scan(_root: Path) -> list[Path]:
        raise AssertionError("enforcement must not scan the repository")

    monkeypatch.setattr(claim_module, "_repository_files", reject_repository_scan)
    report = scan_source_claims(
        root,
        manifest.source_claim_checks,
        discover=False,
    )

    assert len(report.results) == 20
    assert report.candidates == ()


def test_ambiguous_or_missing_relationship_fails_closed(
    tmp_path: Path,
) -> None:
    root = _claim_repository(tmp_path)
    manifest = load_manifest(root / ".sourcebound.yml")
    source = root / "component/catalog.py"
    source.write_text(source.read_text().replace("GROUPS =", "RENAMED_GROUPS ="))

    report = scan_source_claims(root, manifest.source_claim_checks)

    assert not report.ok
    assert [item.id for item in report.missing] == ["groups-count"]
    assert report.missing[0].detail == "source locator was not found"


def test_accepted_source_symlink_cannot_escape_the_repository(
    tmp_path: Path,
) -> None:
    root = _changed_claim_repository(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("WIDGETS = ['one', 'two']\n")
    source = root / "src/widgets.py"
    source.unlink()
    source.symlink_to(outside)
    manifest = load_manifest(root / ".sourcebound.yml")

    report = scan_source_claims(
        root,
        manifest.source_claim_checks,
        discover=False,
    )

    assert [item.id for item in report.missing] == ["widget-count"]
    assert [item.id for item in report.results] == ["gadget-count"]


def test_claims_cli_distinguishes_assessment_from_enforcement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _claim_repository(tmp_path)

    assert main(["--root", str(root), "claims", "--format", "json"]) == 1
    captured = capsys.readouterr()
    enforced = json.loads(captured.out)
    assert enforced["schema"] == "sourcebound.source-claims.v1"
    assert enforced["authority"] == "enforced"
    assert enforced["ok"] is False

    (root / ".sourcebound.yml").unlink()
    assert main(["--root", str(root), "claims", "--format", "json"]) == 0
    captured = capsys.readouterr()
    assessment = json.loads(captured.out)
    assert assessment["authority"] == "assessment"
    assert assessment["ok"] is True
    assert assessment["results"] == []


def test_changed_check_scopes_enforced_claims_to_affected_relationships(
    tmp_path: Path,
) -> None:
    root = _changed_claim_repository(tmp_path)
    base = _commit(root, "current claims")
    (root / "src/widgets.py").write_text("WIDGETS = ['one', 'two', 'three']\n")
    head = _commit(root, "add widget")

    report = check_changed(
        root,
        root / ".sourcebound.yml",
        base=base,
        head=head,
        use_cache=False,
    )

    assert not report.ok
    assert report.dependencies["source-claim:widget-count"] == ("src/widgets.py",)
    assert "source-claim:gadget-count" not in report.dependencies
    assert len(report.required) == 1
    assert report.required[0].rule == "source-claim-drift"
    assert report.required[0].doc == "docs/widgets.md"
    assert report.required[0].source == "src/widgets.py"


def test_changed_check_accepts_source_and_document_updated_together(
    tmp_path: Path,
) -> None:
    root = _changed_claim_repository(tmp_path)
    base = _commit(root, "current claims")
    (root / "src/widgets.py").write_text("WIDGETS = ['one', 'two', 'three']\n")
    (root / "docs/widgets.md").write_text(
        "# Widgets\n\n## Inventory\n\nThe service contains 3 widgets.\n"
    )
    head = _commit(root, "add documented widget")

    report = check_changed(
        root,
        root / ".sourcebound.yml",
        base=base,
        head=head,
        use_cache=False,
    )

    assert report.ok
    assert report.required == ()
    assert report.dependencies["source-claim:widget-count"] == (
        "docs/widgets.md",
        "src/widgets.py",
    )


def test_check_enforces_accepted_claims_without_changing_documents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _claim_repository(tmp_path)
    before = (root / "component/reference.md").read_bytes()

    assert main(["--root", str(root), "check", "--format", "json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    source_claims = [
        item for item in payload["results"]
        if item["provenance"]["extractor"].startswith("source-claim-")
    ]
    assert len(source_claims) == 20
    assert len([item for item in source_claims if item["status"] == "drift"]) == 3
    assert (root / "component/reference.md").read_bytes() == before


def test_verify_receipt_reports_accepted_source_claim_state(
    tmp_path: Path,
) -> None:
    root = _claim_repository(tmp_path)

    receipt = build_outcome_receipt(root, root / ".sourcebound.yml")
    payload = receipt.as_dict()

    assert not receipt.ok
    assert payload["source_claims"] == {
        "total": 20,
        "current": 17,
        "drifted": 3,
        "missing": 0,
    }


def test_source_claim_locator_kind_is_validated(
    tmp_path: Path,
) -> None:
    root = _changed_claim_repository(tmp_path)
    manifest = root / ".sourcebound.yml"
    manifest.write_text(
        manifest.read_text().replace("WIDGETS#count", "WIDGETS#keys")
    )

    with pytest.raises(
        ConfigurationError,
        match=r"locator must end with #count for count",
    ):
        load_manifest(manifest)


def test_historical_change_records_do_not_enter_current_claim_discovery() -> None:
    profile = classify_document(
        Path("CHANGES.md"),
        "# Version 2\n\n`feature()` now supports 3 modes.\n",
    )

    assert profile.role == "evidence"
