from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


MANIFEST = """\
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: python-literal
    source:
      path: src/actions.py
      symbol: ACTIONS
    renderer: markdown-table
    columns: [name, tier, external]
"""

SOURCE_TWO = """\
from dataclasses import dataclass

ACTIONS = {
    "recommend": Action(name="recommend", tier=1, external=False),
    "draft": Action(name="draft", tier=2, external=True),
}
"""

SOURCE_THREE = SOURCE_TWO.replace(
    "}\n",
    '    "call": Action(name="call", tier=3, external=True),\n}\n',
)

README = """\
# Fixture

Author-owned introduction.

<!-- clean-docs:begin actions -->
| name | tier | external |
| --- | --- | --- |
| recommend | 1 | false |
| draft | 2 | true |
<!-- clean-docs:end actions -->

Author-owned ending.
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    src = Path(__file__).parents[1] / "src"
    env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / ".clean-docs.yml").write_text(MANIFEST)
    (root / "src/actions.py").write_text(SOURCE_TWO)
    (root / "README.md").write_text(README)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(root), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "-qm", "baseline",
        ],
        check=True,
    )
    return root


def test_detects_repairs_and_preserves_author_prose(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _run(root, "check").returncode == 0
    (root / "src/actions.py").write_text(SOURCE_THREE)

    check = _run(root, "check", "--format", "json")
    assert check.returncode == 1
    report = json.loads(check.stdout)
    assert report["results"][0]["status"] == "drift"
    assert "| call | 3 | true |" in report["results"][0]["diff"]
    assert (root / "README.md").read_text() == README

    preview = _run(root, "derive")
    assert preview.returncode == 0
    assert "| call | 3 | true |" in preview.stdout
    assert (root / "README.md").read_text() == README

    write = _run(root, "derive", "--write")
    assert write.returncode == 0
    updated = (root / "README.md").read_text()
    assert updated.startswith("# Fixture\n\nAuthor-owned introduction.\n")
    assert updated.endswith("\nAuthor-owned ending.\n")
    assert "| call | 3 | true |" in updated
    assert _run(root, "check").returncode == 0


def test_ci_evidence_fails_on_drift_and_passes_after_regeneration(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "src/actions.py").write_text(SOURCE_THREE)

    audit = _run(root, "audit", "--format", "json")
    check = _run(root, "check", "--format", "json")
    (root / "clean-docs-audit.json").write_text(audit.stdout)
    (root / "clean-docs-check.json").write_text(check.stdout)

    assert audit.returncode == 0
    assert check.returncode == 1
    assert json.loads((root / "clean-docs-audit.json").read_text())["ok"] is True
    assert json.loads((root / "clean-docs-check.json").read_text())["ok"] is False

    assert _run(root, "derive", "--write").returncode == 0
    repaired = _run(root, "check", "--format", "json")
    assert repaired.returncode == 0
    assert json.loads(repaired.stdout)["ok"] is True


def test_reads_source_from_immutable_ref_without_mutation(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    baseline = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
    ).stdout.strip()
    (root / "src/actions.py").write_text(SOURCE_THREE)
    before = (root / "src/actions.py").read_text()

    check = _run(root, "check", "--ref", baseline, "--format", "json")
    assert check.returncode == 0
    report = json.loads(check.stdout)
    assert report["results"][0]["provenance"]["ref"] == baseline
    assert (root / "src/actions.py").read_text() == before


def test_drive_repairs_drift_and_returns_passing_state(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "src/actions.py").write_text(SOURCE_THREE)

    driven = _run(root, "drive", "--format", "json")
    assert driven.returncode == 0, driven.stderr
    report = json.loads(driven.stdout.split("\ndrive:", 1)[0])
    assert report["ok"] is True
    assert report["results"][0]["status"] == "repaired"
    assert "| call | 3 | true |" in (root / "README.md").read_text()
    assert _run(root, "check").returncode == 0


def test_drive_does_not_write_a_policy_failure(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    original = README.replace("Author-owned introduction.", "A powerful introduction.")
    (root / "README.md").write_text(original)
    (root / "src/actions.py").write_text(SOURCE_THREE)

    driven = _run(root, "drive")
    assert driven.returncode == 1
    assert "prohibited-booster" in driven.stderr
    assert (root / "README.md").read_text() == original


def test_json_pointer_binding_repairs_realistic_corpus_table(tmp_path: Path) -> None:
    root = tmp_path / "json-repo"
    (root / "experiment").mkdir(parents=True)
    (root / ".clean-docs.yml").write_text(MANIFEST.replace(
        "extractor: python-literal\n    source:\n      path: src/actions.py\n      symbol: ACTIONS",
        "extractor: json\n    source:\n      path: experiment/corpus.json\n      pointer: /cases",
    ).replace("columns: [name, tier, external]", "columns: [name, tier, external]"))
    (root / "experiment/corpus.json").write_text(json.dumps({"cases": [
        {"name": "clean-baseline", "tier": 0, "external": False},
        {"name": "stale-evidence", "tier": 3, "external": True},
    ]}))
    (root / "README.md").write_text(README.replace(
        "| recommend | 1 | false |\n| draft | 2 | true |",
        "Not generated yet.",
    ))

    driven = _run(root, "drive", "--format", "json")

    assert driven.returncode == 0, driven.stderr
    assert "| stale-evidence | 3 | true |" in (root / "README.md").read_text()
    assert _run(root, "check").returncode == 0
