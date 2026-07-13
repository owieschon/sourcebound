from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from clean_docs.audit import write_audit_baseline
from clean_docs.doctor import build_diagnostic_bundle
from clean_docs.engine import drive
from clean_docs.outcomes import build_outcome_receipt
from clean_docs.performance import benchmark_changed_check


PROJECT = Path(__file__).parents[1]


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


def _fixture(tmp_path: Path) -> tuple[Path, Path, str, str]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "cli.py").write_text("parser.add_parser('serve')\n")
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- clean-docs:purpose -->\n"
        "Use this fixture when testing support receipts. It gives operators one repository surface whose changed evidence can be measured.\n"
        "<!-- clean-docs:end purpose -->\n\n## Repository surface\n\n"
        "<!-- clean-docs:begin repository-surface -->\n"
        "<!-- clean-docs:end repository-surface -->\n"
    )
    manifest = root / ".clean-docs.yml"
    manifest.write_text(
        """\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: README.md
    region: repository-surface
    extractor: repository-inventory
    source: {path: .}
    renderer: markdown-table
    columns: [kind, name, source, locator]
"""
    )
    results, findings = drive(root, manifest)
    assert any(item.changed for item in results)
    assert not findings
    base = _commit(root, "baseline")
    (root / "cli.py").write_text(
        "parser.add_parser('serve')\nparser.add_parser('ship')\n"
    )
    head = _commit(root, "public change")
    results, findings = drive(root, manifest)
    assert any(item.changed for item in results)
    assert not findings
    return root, manifest, base, head


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT / "src")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )


def test_local_outcome_receipt_reports_baseline_and_changed_impact(
    tmp_path: Path,
) -> None:
    root, manifest, base, head = _fixture(tmp_path)

    baseline = build_outcome_receipt(root, manifest)
    changed = build_outcome_receipt(root, manifest, base=base, head=head)

    assert baseline.ok
    assert baseline.as_dict()["outcomes"] == {
        "protected_baseline_current": True,
        "coverage_complete": True,
        "direct_coverage_complete": False,
        "drift_caught_before_merge": 0,
    }
    assert not changed.ok
    assert changed.as_dict()["outcomes"]["drift_caught_before_merge"] >= 1
    assert changed.as_dict()["network_requests"] == 0


def test_local_outcome_receipt_exposes_accepted_hygiene_debt(tmp_path: Path) -> None:
    root, manifest, _base, _head = _fixture(tmp_path)
    (root / "STATUS.md").write_text(
        "# Existing status\n\n<!-- clean-docs:purpose -->\n"
        "Use this page when checking the fixture's existing process debt. It preserves one accepted hygiene finding for the receipt.\n"
        "<!-- clean-docs:end purpose -->\n"
    )
    subprocess.run(["git", "-C", str(root), "add", "STATUS.md"], check=True)
    write_audit_baseline(root)

    receipt = build_outcome_receipt(root, manifest)

    assert receipt.ok
    assert receipt.as_dict()["documentation"] == {
        "active": 2,
        "archived": 0,
        "hygiene_findings": 0,
        "baselined_hygiene_findings": 1,
    }


def test_verify_writes_the_same_local_receipt_it_prints(tmp_path: Path) -> None:
    root, _manifest, _base, _head = _fixture(tmp_path)

    command = _run(root, "verify", "--out", "outcome.json")

    assert command.returncode == 0, command.stderr
    assert command.stdout == (root / "outcome.json").read_text()
    assert json.loads(command.stdout)["schema"] == "clean-docs.outcome.v1"


def test_outcome_does_not_claim_complete_baseline_with_standard_gaps(
    tmp_path: Path,
) -> None:
    root = tmp_path / "gapped"
    root.mkdir()
    (root / "README.md").write_text(
        "# Gapped\n\n<!-- clean-docs:purpose -->\n"
        "Use this page when changing the fixture. Without its contract, callers can guess; "
        "after reading, they can use the declared API.\n"
        "<!-- clean-docs:end purpose -->\n\n## API\n"
    )
    (root / "api.py").write_text("def public_api():\n    return True\n")
    manifest = root / ".clean-docs.yml"
    manifest.write_text(
        "version: 1\nbindings:\n  - id: api\n    type: symbol\n"
        "    doc: README.md\n    anchor: api\n"
        "    source: {path: api.py, symbol: public_api}\n"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    receipt = build_outcome_receipt(root, manifest)
    payload = receipt.as_dict()

    assert receipt.ok
    assert payload["coverage"]["standard_gaps"] > 0
    assert payload["outcomes"]["coverage_complete"] is False
    assert payload["outcomes"]["protected_baseline_current"] is False


def test_benchmark_reports_reproducible_time_and_memory_budget(tmp_path: Path) -> None:
    root, manifest, base, head = _fixture(tmp_path)

    receipt = benchmark_changed_check(
        root,
        manifest,
        base=base,
        head=head,
        iterations=3,
    )

    assert receipt.ok
    assert receipt.required >= 1
    assert receipt.p95_seconds <= receipt.time_budget_seconds
    assert receipt.peak_memory_mb <= receipt.memory_budget_mb
    assert receipt.as_dict()["network_requests"] == 0


def test_diagnostic_bundle_excludes_repository_and_environment_content(
    tmp_path: Path,
) -> None:
    root, manifest, _base, _head = _fixture(tmp_path)
    secret = "ghp_" + "B" * 24
    os.environ["CLEAN_DOCS_TEST_SECRET"] = secret
    try:
        bundle = build_diagnostic_bundle(root, manifest).as_dict()
    finally:
        os.environ.pop("CLEAN_DOCS_TEST_SECRET")

    serialized = json.dumps(bundle)
    assert bundle["schema"] == "clean-docs.diagnostic.v1"
    assert bundle["network_requests"] == 0
    assert secret not in serialized
    assert "environment variables" in bundle["excluded_data"]
    assert "source contents" in bundle["excluded_data"]
