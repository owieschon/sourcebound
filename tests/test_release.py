from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from clean_docs.release import (
    build_release_report,
    render_release_markdown,
    validate_release_narrative,
)


PROJECT = Path(__file__).parents[1]


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


def test_release_reports_added_and_removed_cli_evidence_with_provenance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source = root / "cli.py"
    source.write_text(
        "parser.add_parser('serve')\nparser.add_argument('--legacy')\n"
    )
    before = _commit(root, "before")
    source.write_text("parser.add_parser('serve')\nparser.add_parser('ship')\n")
    after = _commit(root, "after")

    report = build_release_report(root, before, after)

    assert report.from_ref == before
    assert report.to_ref == after
    assert {(delta.change, delta.kind, delta.name) for delta in report.deltas} == {
        ("added", "cli-command", "ship"),
        ("removed", "cli-option", "--legacy"),
    }
    assert all(delta.source == "cli.py" for delta in report.deltas)
    payload = report.as_dict()
    assert payload["schema"] == "sourcebound.release-delta.v1"
    assert payload["counts"] == {"added": 1, "removed": 1, "changed": 0}
    rendered = render_release_markdown(report)
    assert "[cli.py](cli.py)" in rendered
    assert "evidence sha256" in rendered
    assert "because" not in rendered.lower()
    json.dumps(payload)
    command = _run(
        root,
        "release",
        "--from",
        before,
        "--to",
        after,
        "--format",
        "json",
    )
    assert command.returncode == 0, command.stderr
    assert json.loads(command.stdout) == payload


def test_release_reads_each_ref_without_active_worktree_influence(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source = root / "cli.py"
    source.write_text("parser.add_parser('old')\n")
    before = _commit(root, "before")
    source.write_text("parser.add_parser('new')\n")
    after = _commit(root, "after")
    source.write_text("parser.add_parser('worktree-only')\n")

    first = build_release_report(root, before, after)
    source.write_text("this is not valid Python\n")
    second = build_release_report(root, before, after)

    assert first == second
    assert {delta.name for delta in first.deltas} == {"old", "new"}


def test_release_narrative_cannot_omit_or_contradict_typed_facts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source = root / "cli.py"
    source.write_text("parser.add_parser('old')\n")
    before = _commit(root, "before")
    source.write_text("parser.add_parser('new')\n")
    after = _commit(root, "after")
    report = build_release_report(root, before, after)
    delta = report.deltas[0]
    response = json.dumps(
        {
            "schema": "sourcebound.release-narrative.v1",
            "drafts": [
                {
                    "delta_id": delta.id,
                    "change": delta.change,
                    "kind": delta.kind,
                    "name": "contradictory-name",
                    "citation": f"{delta.source}#{delta.locator}",
                    "text": "A command changed.",
                }
            ],
        }
    )
    response_path = root / "release-response.json"
    response_path.write_text(response)

    narrative = validate_release_narrative(report, response)

    assert not narrative.ok
    assert narrative.drafts == ()
    assert any("contradicts deterministic fields: name" in item for item in narrative.findings)
    assert any("omitted" in item for item in narrative.findings)
    assembled = render_release_markdown(report, narrative)
    assert assembled.startswith(render_release_markdown(report))
    command = _run(
        root,
        "release",
        "--from",
        before,
        "--to",
        after,
        "--recorded-model-response",
        response_path.name,
        "--format",
        "json",
    )
    assert command.returncode == 1
    command_payload = json.loads(command.stdout)
    assert command_payload["deltas"] == report.as_dict()["deltas"]
    assert not command_payload["narrative"]["ok"]


def test_release_narrative_accepts_exact_cited_facts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source = root / "cli.py"
    source.write_text("parser.add_parser('old')\n")
    before = _commit(root, "before")
    source.write_text("parser.add_parser('new')\n")
    after = _commit(root, "after")
    report = build_release_report(root, before, after)
    drafts = [
        {
            "delta_id": delta.id,
            "change": delta.change,
            "kind": delta.kind,
            "name": delta.name,
            "citation": f"{delta.source}#{delta.locator}",
            "text": f"The {delta.name} command was {delta.change}.",
        }
        for delta in report.deltas
    ]

    narrative = validate_release_narrative(
        report,
        json.dumps({"schema": "sourcebound.release-narrative.v1", "drafts": drafts}),
    )

    assert narrative.ok
    rendered = render_release_markdown(report, narrative)
    assert all(f"`{draft.citation}`" in rendered for draft in narrative.drafts)
