from __future__ import annotations

from pathlib import Path

import yaml

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised on Python 3.10 in CI
    import tomli as tomllib


ROOT = Path(__file__).parents[1]


def test_release_toolchain_and_ci_install_are_pinned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["build-system"]["requires"] == [
        "setuptools==75.8.0",
        "wheel==0.45.1",
    ]
    assert {"build==1.2.2.post1", "setuptools==75.8.0", "wheel==0.45.1"} <= set(
        project["project"]["optional-dependencies"]["dev"]
    )

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["release-artifact"]["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    assert "python scripts/build_release.py --out dist" in commands
    assert "/tmp/clean-docs-release/bin/clean-docs --help" in commands
    assert "/tmp/clean-docs-release/bin/clean-docs --root . audit" in commands
    upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
    assert upload["with"]["if-no-files-found"] == "error"
