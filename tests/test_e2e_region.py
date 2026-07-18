from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


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

<!-- clean-docs:purpose -->
Author-owned introduction.
<!-- clean-docs:end purpose -->

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
    assert updated.startswith(
        "# Fixture\n\n<!-- clean-docs:purpose -->\n"
        "Author-owned introduction.\n<!-- clean-docs:end purpose -->\n"
    )
    assert updated.endswith("\nAuthor-owned ending.\n")
    assert "| call | 3 | true |" in updated
    assert _run(root, "check").returncode == 0


def test_tenth_action_drift_is_detected_and_repaired(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    def action_source(count: int) -> str:
        rows = "\n".join(
            f'    "action-{index:02d}": Action('
            f'name="action-{index:02d}", tier={index}, external=False),'
            for index in range(1, count + 1)
        )
        return f"ACTIONS = {{\n{rows}\n}}\n"

    (root / "src/actions.py").write_text(action_source(9))
    baseline_drive = _run(root, "drive")
    assert baseline_drive.returncode == 0, baseline_drive.stderr
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(root), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.test", "commit", "-qm", "nine-actions",
        ],
        check=True,
    )
    before = (root / "README.md").read_text()
    (root / "src/actions.py").write_text(action_source(10))

    checked = _run(root, "check", "--format", "json")

    assert checked.returncode == 1
    assert "action-10" in json.loads(checked.stdout)["results"][0]["diff"]
    assert (root / "README.md").read_text() == before
    repaired = _run(root, "derive", "--write")
    assert repaired.returncode == 0, repaired.stderr
    after = (root / "README.md").read_text()
    begin = "<!-- clean-docs:begin actions -->"
    end = "<!-- clean-docs:end actions -->"
    assert after.split(begin, 1)[0] == before.split(begin, 1)[0]
    assert after.split(end, 1)[1] == before.split(end, 1)[1]
    assert "| action-10 | 10 | false |" in after
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
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-clean-docs.yml").read_text())
    upload = next(
        step
        for step in workflow["jobs"]["clean-docs"]["steps"]
        if step.get("uses")
        == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert upload["if"] == "always()"
    assert upload["with"]["if-no-files-found"] == "error"


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
    original = README.replace(
        "# Fixture\n",
        "# Fixture\n\n"
        "<!-- clean-docs:policy register-v2 -->\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates the booster rule" -->\n'
        '<!-- clean-docs:allow readme-routing reason="Fixture isolates the booster rule" -->\n',
    ).replace("Author-owned introduction.", "A powerful introduction.")
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


def test_two_region_repair_preserves_every_unbound_byte(tmp_path: Path) -> None:
    root = tmp_path / "two-region-repo"
    root.mkdir()
    (root / "first.txt").write_text("new first\n")
    (root / "second.txt").write_text("new second\n")
    original = (
        "# Fixture\n\n<!-- clean-docs:purpose -->\n"
        "Author introduction.\n<!-- clean-docs:end purpose -->\n\n"
        "<!-- clean-docs:begin first -->\nold first\n<!-- clean-docs:end first -->\n\n"
        "Author bridge.\n\n"
        "<!-- clean-docs:begin second -->\nold second\n<!-- clean-docs:end second -->\n\n"
        "Author ending.\n"
    )
    (root / "README.md").write_text(original)
    (root / ".clean-docs.yml").write_text("""\
version: 1
bindings:
  - id: first
    type: region
    doc: README.md
    region: first
    extractor: file
    source: {path: first.txt}
    renderer: scalar
  - id: second
    type: region
    doc: README.md
    region: second
    extractor: file
    source: {path: second.txt}
    renderer: scalar
""")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    derived = _run(root, "derive", "--write")

    assert derived.returncode == 0, derived.stderr
    updated = (root / "README.md").read_text()
    body = re.compile(
        r"(<!-- clean-docs:begin [^ ]+ -->\n).*?(<!-- clean-docs:end [^ ]+ -->)",
        re.DOTALL,
    )
    assert body.sub(r"\1<generated>\n\2", updated) == body.sub(
        r"\1<generated>\n\2", original
    )
    assert "\nnew first\n" in updated
    assert "\nnew second\n" in updated
