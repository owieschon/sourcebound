from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from clean_docs.cli import main
from clean_docs.errors import ConfigurationError
from clean_docs.verdict import (
    build_pr_verdict,
    render_verdict_payload_sarif,
    validate_verdict_payload,
)


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


def _symbol_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "src/api.py").write_text(
        "def public_api(timeout: int = 5):\n"
        "    return timeout\n\n"
        "def _normalize(value: int):\n"
        "    return value\n"
    )
    (root / "README.md").write_text(
        "# Fixture\n\n"
        "<!-- clean-docs:purpose -->\n"
        "This repository is a verdict fixture. Maintainers use its API contract "
        "to detect documentation impact before merging a change.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "## API\n\n`public_api` is the supported entry point.\n"
    )
    (root / ".clean-docs.yml").write_text(
        """\
version: 1
bindings:
  - id: public-api
    type: symbol
    doc: README.md
    anchor: api
    source: {path: src/api.py, symbol: public_api}
"""
    )
    return root


def _region_repository(tmp_path: Path) -> Path:
    root = tmp_path / "region-repository"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "src/actions.py").write_text(
        'ACTIONS = [{"name": "report", "job": "Report status"}]\n'
    )
    (root / "README.md").write_text(
        "# Fixture\n\n"
        "<!-- clean-docs:purpose -->\n"
        "This repository records supported actions. Maintainers use the generated "
        "table to keep those actions aligned with source.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "## Actions\n\n"
        "<!-- clean-docs:begin actions -->\n"
        "| name | job |\n"
        "| --- | --- |\n"
        "| report | Report status |\n"
        "<!-- clean-docs:end actions -->\n"
    )
    (root / ".clean-docs.yml").write_text(
        """\
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: python-literal
    source: {path: src/actions.py, symbol: ACTIONS}
    renderer: markdown-table
    columns: [name, job]
"""
    )
    return root


def _command_repository(tmp_path: Path) -> Path:
    root = tmp_path / "command-repository"
    (root / "scripts").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "scripts/count.py").write_text(
        'import json\nprint(json.dumps({"collected": 340}))\n'
    )
    (root / "README.md").write_text(
        "# Fixture\n\n"
        "<!-- clean-docs:purpose -->\n"
        "This repository records one command result. Maintainers use it to exercise "
        "the static execution boundary.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "## Testing\n\n340 records.\n"
    )
    (root / ".clean-docs.yml").write_text(
        """\
version: 1
execution:
  commands: deny
  allowed_commands:
    test-summary:
      argv: [python, scripts/count.py]
      timeout_seconds: 10
      network: false
bindings:
  - id: test-count
    type: claim
    doc: README.md
    anchor: testing
    extractor: command
    command: test-summary
    assertion:
      json_path: $.collected
      operator: equals
      expected: 340
"""
    )
    return root


def _add_public_api_review_contract(
    root: Path,
    *,
    target_locator: str = "#api",
) -> None:
    manifest = root / ".clean-docs.yml"
    manifest.write_text(
        manifest.read_text()
        + f"""\
review_contracts:
  - id: public-api-guidance
    mode: observe
    sources:
      - id: public-api-function
        path: src/api.py
        extractor: python-symbol
        locator: public_api
    targets:
      - id: api-guidance
        path: README.md
        extractor: markdown-section
        locator: "{target_locator}"
"""
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _mutation_receipt(path: Path, head: str) -> None:
    plan = {
        "generator": "fixture@1",
        "class": "rename-mapping-member",
        "target_execution_required": False,
    }
    path.write_text(
        json.dumps(
            {
                "schema": "clean-docs.binding-sensitivity.v1",
                "state": "sensitive",
                "semantic_relationship_authorized": False,
                "repository": {"commit": head},
                "inputs": {
                    "relationship": {
                        "id": "fixture-relationship",
                    }
                },
                "mutation": {
                    **plan,
                    "plan_sha256": _canonical_sha256(plan),
                },
            }
        )
    )


def test_private_refactor_is_stable_and_ready_with_coverage_stated(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return value", "return int(value)"))
    head = _commit(root, "private refactor")

    first = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=base,
        head=head,
    )
    second = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=base,
        head=head,
    )

    assert first.as_dict() == second.as_dict()
    assert first.digest == second.digest
    payload = first.as_dict()
    assert first.state == "ready"
    assert payload["scope"] == "configured-contract-and-changed-surface"
    assert payload["coverage"]["catalog_only"] >= 0
    assert payload["coverage"]["unbound_prose_checked"] is False
    changed = payload["changed_surface"]
    assert changed["files"] == ["src/api.py"]
    assert changed["required"] == 0
    assert changed["gaps"] == 0
    assert changed["ignored"] == 0
    assert changed["unknown"] == 0
    assert changed["coverage_complete"] is True
    assert changed["impact"] == "none"
    assert changed["unsupported_documents"] == []
    assert changed["artifacts"][0]["path"] == "src/api.py"
    assert changed["artifacts"][0]["adapter"] == "python-ast"
    assert changed["artifacts"][0]["coverage"] == "graph-covered"
    assert payload["non_claims"] == [
        "unbound prose is not certified",
        "judgment prose is not certified",
        "mutation sensitivity is not semantic correctness",
        "review-contract co-change is not semantic correctness",
        "catalog coverage is not prose coverage",
    ]


def test_review_contract_advisory_preserves_ready_verdict_and_receipts(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    _add_public_api_review_contract(root)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace(
        "return timeout",
        "return timeout * 2",
    ))
    head = _commit(root, "change public API behavior")

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=base,
        head=head,
    )
    payload = verdict.as_dict()

    assert verdict.state == "ready"
    finding = next(
        item
        for item in payload["findings"]
        if item["rule"] == "review-contract-review-recommended"
    )
    assert finding["level"] == "note"
    mechanism = payload["mechanisms"]["review-contract"]
    assert mechanism == {
        "total": 1,
        "unaffected": 0,
        "review-recommended": 1,
        "cochanged": 0,
        "unknown": 0,
        "semantic_correctness_checked": False,
    }
    observation = payload["review_contracts"][0]
    assert observation["id"] == "public-api-guidance"
    assert observation["state"] == "review-recommended"
    assert observation["semantic_correctness_checked"] is False
    assert (
        "review-contract co-change is not semantic correctness"
        in payload["non_claims"]
    )

    sarif = json.loads(render_verdict_payload_sarif(payload))
    sarif_finding = next(
        result
        for result in sarif["runs"][0]["results"]
        if result["ruleId"] == "review-contract-review-recommended"
    )
    assert sarif_finding["partialFingerprints"]["cleanDocsFindingId"] == (
        finding["id"]
    )


def test_unknown_review_contract_is_a_nonblocking_note(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    _add_public_api_review_contract(
        root,
        target_locator="#missing-api-section",
    )
    head = _commit(root, "base")

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=head,
        head=head,
    )

    assert verdict.state == "ready"
    finding = next(
        item
        for item in verdict.findings
        if item.rule == "review-contract-unknown"
    )
    assert finding.level == "note"
    assert verdict.as_dict()["mechanisms"]["review-contract"]["unknown"] == 1


def test_unsupported_public_change_is_unknown(tmp_path: Path) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    (root / "src/Service.java").write_text(
        "public final class Service { public void start() {} }\n"
    )
    head = _commit(root, "add unsupported public service")

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=base,
        head=head,
    )

    assert verdict.state == "unknown"
    assert not verdict.ok
    assert "src/Service.java" in verdict.as_dict()["changed_surface"]["files"]
    assert any(
        finding.rule == "unsupported-public-candidate"
        for finding in verdict.findings
    )
    assert any(
        finding.rule == "unsupported-public-candidate"
        and finding.level == "warning"
        for finding in verdict.findings
    )


def test_static_verdict_classifies_valid_mdx_without_repository_execution(
    tmp_path: Path,
) -> None:
    root = _symbol_repository(tmp_path)
    guide = root / "docs/guide.mdx"
    guide.parent.mkdir()
    guide.write_text("# Guide\n\n<Callout>Old guidance.</Callout>\n")
    base = _commit(root, "base")
    guide.write_text("# Guide\n\n<Callout>Current guidance.</Callout>\n")
    head = _commit(root, "change MDX guidance")

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=base,
        head=head,
    )
    payload = verdict.as_dict()

    assert verdict.state == "ready"
    assert payload["execution"]["repository_commands"] == "skipped"
    assert payload["changed_surface"]["unsupported_documents"] == []
    assert payload["changed_surface"]["artifacts"][0]["adapter"] == "mdx-static"
    assert payload["changed_surface"]["artifacts"][0]["coverage"] == "document-direct"


def test_bound_region_drift_is_not_ready(tmp_path: Path) -> None:
    root = _region_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/actions.py"
    source.write_text(source.read_text().replace("report", "publish"))
    head = _commit(root, "change action")

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=base,
        head=head,
    )

    assert verdict.state == "not_ready"
    assert any(finding.rule == "binding-drift" for finding in verdict.findings)
    assert verdict.as_dict()["mechanisms"]["region"]["drifted"] == 1


def test_affected_command_is_unknown_without_executing_target(
    tmp_path: Path,
) -> None:
    root = _command_repository(tmp_path)
    base = _commit(root, "base")
    marker = root / "command-ran.txt"
    (root / "scripts/count.py").write_text(
        "from pathlib import Path\n"
        "Path('command-ran.txt').write_text('ran')\n"
        'print(\'{"collected": 340}\')\n'
    )
    head = _commit(root, "change declared command")

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=base,
        head=head,
    )

    payload = verdict.as_dict()
    assert verdict.state == "unknown"
    assert payload["execution"]["repository_commands"] == "skipped"
    assert payload["execution"]["skipped_binding_ids"] == ["test-count"]
    assert payload["execution"]["skipped_command_ids"] == ["test-summary"]
    assert any(finding.rule == "execution-skipped" for finding in verdict.findings)
    assert not marker.exists()


def test_unaffected_command_pin_does_not_certify_legacy_prose(
    tmp_path: Path,
) -> None:
    root = _command_repository(tmp_path)
    head = _commit(root, "base")

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=head,
        head=head,
    )

    payload = verdict.as_dict()
    assert verdict.state == "ready"
    assert payload["mechanisms"]["command-pin"]["skipped"] == 1
    assert payload["execution"]["skipped_binding_ids"] == ["test-count"]
    assert payload["execution"]["skipped_command_ids"] == ["test-summary"]
    assert payload["coverage"]["unbound_prose_checked"] is False
    assert "unbound prose is not certified" in payload["non_claims"]


def test_mutation_receipt_must_match_head_and_plan_digest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _symbol_repository(tmp_path)
    head = _commit(root, "base")
    receipt = tmp_path / "receipt.json"
    _mutation_receipt(receipt, "0" * 40)

    exit_code = main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            head,
            "--head",
            head,
            "--mutation-receipt",
            str(receipt),
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "invalid"
    assert "commit does not match" in payload["error"]["detail"]

    _mutation_receipt(receipt, head)
    linked_receipt = tmp_path / "linked-receipt.json"
    linked_receipt.symlink_to(receipt)
    assert main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            head,
            "--head",
            head,
            "--mutation-receipt",
            str(linked_receipt),
        ]
    ) == 2
    assert "must not be a symbolic link" in json.loads(
        capsys.readouterr().out
    )["error"]["detail"]

    verdict = build_pr_verdict(
        root,
        root / ".clean-docs.yml",
        base=head,
        head=head,
        mutation_receipt_paths=(receipt,),
    )
    assert verdict.state == "ready"
    assert verdict.as_dict()["mutation_receipts"][0][
        "semantic_relationship_authorized"
    ] is False

    raw = json.loads(receipt.read_text())
    raw["mutation"]["plan_sha256"] = "0" * 64
    receipt.write_text(json.dumps(raw))
    exit_code = main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            head,
            "--head",
            head,
            "--mutation-receipt",
            str(receipt),
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert "plan digest does not match" in payload["error"]["detail"]


def test_json_and_sarif_share_finding_ids(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _region_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/actions.py"
    source.write_text(source.read_text().replace("report", "publish"))
    head = _commit(root, "change action")

    assert main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            base,
            "--head",
            head,
            "--format",
            "json",
        ]
    ) == 1
    json_payload = json.loads(capsys.readouterr().out)
    assert main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            base,
            "--head",
            head,
            "--format",
            "sarif",
        ]
    ) == 1
    sarif = json.loads(capsys.readouterr().out)

    json_ids = {finding["id"] for finding in json_payload["findings"]}
    sarif_ids = {
        result["partialFingerprints"]["cleanDocsFindingId"]
        for result in sarif["runs"][0]["results"]
    }
    assert json_ids == sarif_ids
    assert sarif["runs"][0]["properties"]["cleanDocsVerdictDigest"] == (
        json_payload["digest"]
    )

    rendered = json.loads(render_verdict_payload_sarif(json_payload))
    assert rendered == sarif

    json_payload["state"] = "ready"
    with pytest.raises(ConfigurationError, match="digest does not match"):
        validate_verdict_payload(json_payload)


def test_verdict_rejects_dirty_or_detached_input_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _symbol_repository(tmp_path)
    base = _commit(root, "base")
    source = root / "src/api.py"
    source.write_text(source.read_text().replace("return value", "return int(value)"))
    head = _commit(root, "refactor")
    (root / "scratch.txt").write_text("dirty\n")

    assert main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            base,
            "--head",
            head,
        ]
    ) == 2
    assert "clean caller worktree" in json.loads(
        capsys.readouterr().out
    )["error"]["detail"]

    (root / "scratch.txt").unlink()
    assert main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            base,
            "--head",
            base,
        ]
    ) == 2
    assert "head must match" in json.loads(
        capsys.readouterr().out
    )["error"]["detail"]


def test_extraction_failure_stays_machine_readable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _region_repository(tmp_path)
    manifest = root / ".clean-docs.yml"
    manifest.write_text(
        """\
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: path
    source: {glob: missing/*.json}
    renderer: markdown-list
"""
    )
    head = _commit(root, "invalid extraction")

    assert main(
        [
            "--root",
            str(root),
            "verdict",
            "--base",
            head,
            "--head",
            head,
        ]
    ) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "invalid"
    assert payload["error"]["class"] == "extraction"
