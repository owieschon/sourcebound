from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT = Path(__file__).parents[1]
FIXTURE = PROJECT / "tests/fixtures/vendor/httpx-version"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    source = PROJECT / "src"
    environment["PYTHONPATH"] = str(source) + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def test_vendored_httpx_version_fixture_detects_bound_source_drift(tmp_path: Path) -> None:
    root = tmp_path / "httpx-version"
    shutil.copytree(FIXTURE, root)

    baseline = _run(root, "check")
    assert baseline.returncode == 0, baseline.stderr
    assert (root / "LICENSE").is_file()
    assert "26d48e0634e6ee9cdc0533996db289ce4b430177" in (root / "UPSTREAM.md").read_text()

    source = root / "httpx_version.py"
    source.write_text(source.read_text().replace('"0.28.1"', '"0.28.2"'))

    drift = _run(root, "check")
    assert drift.returncode == 1
    assert "upstream-version" in drift.stdout
