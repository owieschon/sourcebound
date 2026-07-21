from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from clean_docs.corpus import findings_as_json, scan_corpus
from clean_docs.write_gate import evaluate_write


ROOT = Path(__file__).parents[1]


def _policy_corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    archive = root / "docs" / "archive"
    archive.mkdir(parents=True)
    (root / "STATUS.md").write_text("# Status\n")
    (root / "REFERENCE.md").write_text(
        "# Reference\n\n"
        "The next executor can pick up this branch from the worktree.\n\n"
        "The decision record uses IF/THEN, and its round trip must remain byte-identical.\n\n"
        "The value was recorded in (Program 9).\n"
    )
    paragraph = "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda.\n"
    (root / "ALPHA.md").write_text(f"# Alpha\n\n{paragraph}")
    (root / "BETA.md").write_text(f"# Beta\n\n{paragraph}")
    (root / "LONG.md").write_text(
        "# Long\n\n" + "\n".join(f"line {index}" for index in range(121))
    )
    (root / "SECTION.md").write_text(
        "# Section\n\n## Oversized\n"
        + "\n".join(f"detail {index}" for index in range(41))
    )
    (archive / "STATUS.md").write_text(
        "# Archived status\n\nnext executor pick up this branch worktree (Program 4)\n"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


def test_corpus_policy_matches_frozen_version_zero_golden(tmp_path: Path) -> None:
    root = _policy_corpus(tmp_path)
    expected = json.loads(
        (ROOT / "tests/fixtures/v0-policy/corpus-findings.json").read_text()
    )

    packaged = findings_as_json(scan_corpus(root))
    wrapper = subprocess.run(
        [sys.executable, str(ROOT / "doc-hygiene.py"), str(root), "--json"],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )

    assert packaged == expected
    assert json.loads(wrapper.stdout) == expected
    assert wrapper.returncode == 1


def test_prior_false_positive_repairs_are_preserved(tmp_path: Path) -> None:
    findings = scan_corpus(_policy_corpus(tmp_path))
    details = "\n".join(finding.detail for finding in findings)

    assert "docs/archive" not in "\n".join(finding.doc for finding in findings)
    assert "IF/THEN" not in details
    assert "byte-identical" not in details
    migrations = json.loads(
        (ROOT / "src/clean_docs/standards/v0-migrations.json").read_text()
    )
    assert {item["rule"] for item in migrations["differences"]} >= {
        "archive-surface",
        "audience-if-then",
        "provenance-byte-identical",
    }


def test_pre_write_wrapper_matches_frozen_version_zero_script(tmp_path: Path) -> None:
    payloads = [
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "README.md",
                "content": "We could potentially utilize this layer.\n",
            },
        },
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "module.py",
                "content": "try:\n    run()\nexcept:\n    pass\n",
            },
        },
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "values.json",
                "content": '{"token": "Bearer abcdefghijklmnop1234"}',
            },
        },
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "README.md",
                "content": "A clean sentence.\n",
            },
        },
    ]
    environment = {**os.environ, "HOME": str(tmp_path), "PYTHONPATH": str(ROOT / "src")}
    original = ROOT / "tests/fixtures/v0-policy/quality-gate.py.orig"
    wrapper = ROOT / "quality-gate.py"
    for payload in payloads:
        baseline = subprocess.run(
            [sys.executable, str(original)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        packaged = subprocess.run(
            [sys.executable, str(wrapper)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        assert (packaged.returncode, packaged.stdout, packaged.stderr) == (
            baseline.returncode,
            baseline.stdout,
            baseline.stderr,
        )

    result = evaluate_write(payloads[0])
    assert [finding.rule for finding in result.findings] == [
        "utilize-verb",
        "hedge-stack",
    ]
