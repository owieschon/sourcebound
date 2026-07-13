from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from clean_docs.engine import evaluate
from clean_docs.manifest import load_manifest
from clean_docs.migration import (
    apply_migration,
    backup_path,
    build_migration_plan,
    rollback_migration,
)


FIXTURES = Path(__file__).parent / "fixtures/migrations"
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


def test_v0_to_v1_migration_matches_golden_and_preserves_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    manifest = root / ".clean-docs.yml"
    source = root / "source.txt"
    readme = root / "README.md"
    source.write_text("Grounded fact\n")
    readme.write_text(
        "# Fixture\n\n<!-- clean-docs:begin fact -->\nGrounded fact\n"
        "<!-- clean-docs:end fact -->\n"
    )
    shutil.copy2(FIXTURES / "manifest-v1.yml", manifest)
    expected = evaluate(root, manifest)
    original = (FIXTURES / "manifest-v0.yml").read_text()
    manifest.write_text(original)

    plan = build_migration_plan(manifest)

    assert plan.migrated == (FIXTURES / "manifest-v1.yml").read_text()
    backup = apply_migration(manifest, plan)
    assert backup == backup_path(manifest)
    assert backup.read_text() == original
    assert load_manifest(manifest).version == 1
    assert evaluate(root, manifest) == expected

    rollback_migration(manifest)
    assert manifest.read_text() == original
    assert not backup.exists()

    applied = _run(root, "migrate", "--write")
    assert applied.returncode == 0, applied.stderr
    assert load_manifest(manifest).version == 1
    rolled_back = _run(root, "migrate", "--rollback")
    assert rolled_back.returncode == 0, rolled_back.stderr
    assert manifest.read_text() == original
