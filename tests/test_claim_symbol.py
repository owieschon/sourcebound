from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
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
    (root / "scripts").mkdir()
    (root / "README.md").write_text("# Fixture\n\n## Testing\n\nTwo tests.\n\n## Architecture\n\nSee `sweep`.\n")
    (root / "src/service.py").write_text("def sweep():\n    return True\n")
    (root / "scripts/count.py").write_text('import json\nprint(json.dumps({"collected": 2}))\n')
    (root / ".clean-docs.yml").write_text(f"""\
version: 1
execution:
  commands: deny
  allowed_commands:
    test-summary:
      argv: [{json.dumps(sys.executable)}, scripts/count.py]
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
      expected: 2
  - id: sweep-symbol
    type: symbol
    doc: README.md
    anchor: architecture
    source:
      path: src/service.py
      symbol: sweep
""")
    return root


def test_claim_drift_is_read_only_and_reports_values(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _run(root, "check").returncode == 0
    before = (root / "README.md").read_text()
    (root / "scripts/count.py").write_text('import json\nprint(json.dumps({"collected": 3}))\n')

    checked = _run(root, "check", "--format", "json")

    assert checked.returncode == 1
    result = json.loads(checked.stdout)["results"][0]
    assert result["status"] == "drift"
    assert "expected 2, observed 3" in result["diff"]
    assert (root / "README.md").read_text() == before


def test_symbol_rename_is_documentation_drift(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "src/service.py").write_text("def renamed():\n    return True\n")

    checked = _run(root, "check", "--format", "json")

    assert checked.returncode == 1
    result = json.loads(checked.stdout)["results"][1]
    assert result["status"] == "drift"
    assert "sweep" in result["diff"]
    assert "architecture" in result["diff"]


def test_drive_does_not_claim_to_repair_assertion_drift(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "scripts/count.py").write_text('import json\nprint(json.dumps({"collected": 3}))\n')

    driven = _run(root, "drive", "--format", "json")

    assert driven.returncode == 1
    report = json.loads(driven.stdout.split("\ndrive:", 1)[0])
    assert report["ok"] is False
    assert report["results"][0]["status"] == "drift"
