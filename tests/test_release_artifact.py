from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

import scripts.build_release as release_builder

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised on Python 3.10 in CI
    import tomli as tomllib


ROOT = Path(__file__).parents[1]
UPLOAD_ARTIFACT = (
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
)


def test_published_wheel_checksum_command_accepts_matching_artifact(tmp_path: Path) -> None:
    wheel = tmp_path / "clean_docs-1.0.0rc14-py3-none-any.whl"
    wheel.write_bytes(b"release candidate")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(f"{digest}  {wheel.name}\n")

    install = (ROOT / "docs/INSTALL.md").read_text()
    section = install.split("## Verify release artifacts", maxsplit=1)[1]
    match = re.search(r"```bash\npython3 - <<'PY'\n(.*?)\nPY\n", section, re.DOTALL)
    assert match is not None

    result = subprocess.run(
        [sys.executable, "-c", match.group(1)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{wheel.name}: {digest}"


def test_wheel_canonicalization_removes_zip_runtime_variation(tmp_path: Path) -> None:
    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
    with zipfile.ZipFile(first, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("b.txt", "second")
        archive.writestr("a.txt", "first")
    with zipfile.ZipFile(second, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("a.txt", "first")
        archive.writestr("b.txt", "second")

    release_builder._canonicalize_wheel(first)
    release_builder._canonicalize_wheel(second)

    assert first.read_bytes() == second.read_bytes()


def test_release_toolchain_and_ci_install_are_pinned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["build-system"]["requires"] == [
        "setuptools==75.8.0",
        "wheel==0.45.1",
    ]
    assert {"build==1.2.2.post1", "setuptools==75.8.0", "wheel==0.45.1"} <= set(
        project["project"]["optional-dependencies"]["dev"]
    )
    package = (ROOT / "src/clean_docs/__init__.py").read_text()
    assert '__version__ = "' not in package
    assert 'version("clean-docs")' in package

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["release-artifact"]["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    assert "python scripts/build_release.py --out dist" in commands
    assert "/tmp/clean-docs-release/bin/clean-docs --help" in commands
    assert "/tmp/clean-docs-release/bin/clean-docs --root . audit" in commands
    assert "python scripts/test_release_lifecycle.py --wheel dist/*.whl" in commands
    assert "verify_release_reader_trial" in (ROOT / "scripts/build_release.py").read_text()
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
        "sbom-path": "${{ steps.release-files.outputs.sbom }}",
    }
    resolver = next(step for step in steps if step.get("id") == "release-files")
    assert "expected one SBOM" in resolver["run"]
    upload = next(step for step in steps if step.get("uses") == UPLOAD_ARTIFACT)
    assert upload["with"]["if-no-files-found"] == "error"
    publisher = next(step for step in steps if step.get("name") == "Publish release assets")
    assert "python scripts/publish_release.py" in publisher["run"]
    assert "--source-digest \"$GITHUB_SHA\"" in publisher["run"]
    assert "gh release create" not in publisher["run"]
    publication_upload = next(
        step for step in steps if step.get("name") == "Upload publication receipt"
    )
    assert publication_upload["with"]["path"] == "release-publication.json"
    assert publication_upload["with"]["if-no-files-found"] == "error"


def test_stable_release_accepts_only_reader_candidate_version_and_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "fixture"\nversion = "1.0.0rc9"\n')
    (tmp_path / "product.py").write_text("VALUE = 1\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "candidate",
        ],
        check=True,
    )
    candidate = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    project.write_text('[project]\nname = "fixture"\nversion = "1.0.0"\n')
    receipts = tmp_path / ".clean-docs/reader-trials"
    receipts.mkdir(parents=True)
    (receipts / "result.txt").write_text("passed\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "finalize",
        ],
        check=True,
    )
    final = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"candidate wheel")
    monkeypatch.setattr(release_builder, "ROOT", tmp_path)
    monkeypatch.setattr(
        release_builder,
        "_build_once",
        lambda *args, **kwargs: wheel,
    )
    trial: dict[str, object] = {
        "required": True,
        "candidate_commit": candidate,
        "candidate_artifact_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "receipt_path": ".clean-docs/reader-trial.json",
        "evidence_root": ".clean-docs/reader-trials",
    }

    release_builder._verify_reader_candidate(final, trial, tmp_path / "build")

    (tmp_path / "product.py").write_text("VALUE = 2\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "untried product change",
        ],
        check=True,
    )
    changed = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    with pytest.raises(RuntimeError, match="changed product files"):
        release_builder._verify_reader_candidate(changed, trial, tmp_path / "build")
