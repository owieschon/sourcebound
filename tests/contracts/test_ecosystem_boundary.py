from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "examples" / "complementary-toolchain"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def test_source_integrity_mutation_has_one_owner(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture)

    baseline = _run(fixture, "check")
    assert baseline.returncode == 0, baseline.stderr

    source = fixture / "src" / "actions.py"
    source.write_text(source.read_text().replace(
        '    "inspect": {"name": "inspect", "audience": "maintainers"},\n',
        '    "inspect": {"name": "inspect", "audience": "maintainers"},\n'
        '    "publish": {"name": "publish", "audience": "reviewers"},\n',
    ))
    drift = _run(fixture, "check")
    assert drift.returncode == 1
    assert "actions" in (drift.stdout + drift.stderr)
