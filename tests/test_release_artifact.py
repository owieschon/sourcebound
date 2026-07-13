from __future__ import annotations

from pathlib import Path

import yaml

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised on Python 3.10 in CI
    import tomli as tomllib


ROOT = Path(__file__).parents[1]
UPLOAD_ARTIFACT = (
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
)


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
    assert "python scripts/test_release_lifecycle.py --wheel dist/*.whl" in commands
    upload = next(step for step in steps if step.get("uses") == UPLOAD_ARTIFACT)
    assert upload["with"]["if-no-files-found"] == "error"
    assert "dist/*.spdx.json" in upload["with"]["path"]


def test_release_workflow_attests_wheel_and_sbom() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    assert workflow["permissions"] == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }
    steps = workflow["jobs"]["release"]["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    assert "python scripts/test_release_lifecycle.py --wheel dist/*.whl" in commands
    attestations = [step for step in steps if str(step.get("uses", "")).startswith("actions/attest@")]
    assert len(attestations) == 2
    assert attestations[0]["with"] == {"subject-path": "dist/*.whl"}
    assert attestations[1]["with"] == {
        "subject-path": "dist/*.whl",
        "sbom-path": "dist/*.spdx.json",
    }
    upload = next(step for step in steps if step.get("uses") == UPLOAD_ARTIFACT)
    assert upload["with"]["if-no-files-found"] == "error"
