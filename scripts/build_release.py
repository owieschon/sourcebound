#!/usr/bin/env python3
"""Build and verify one reproducible wheel from the current Git commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

if __package__:
    from scripts.build_sbom import render_sbom
    from scripts.verify_reader_trial import verify_release_reader_trial
else:
    from build_sbom import render_sbom
    from verify_reader_trial import verify_release_reader_trial


ROOT = Path(__file__).resolve().parents[1]


def _canonicalize_wheel(path: Path) -> None:
    """Rewrite a wheel without runtime-dependent ZIP compression bytes."""
    with zipfile.ZipFile(path) as source:
        entries = [(name, source.read(name)) for name in sorted(source.namelist())]
    temporary = path.with_suffix(".canonical.whl")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as output:
        for name, content in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            output.writestr(info, content)
    temporary.replace(path)


def _run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        list(args),
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"{' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def _archive(ref: str, destination: Path) -> None:
    archive = destination / "source.tar"
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "archive", "--format=tar", f"--output={archive}", ref],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"git archive failed: {detail}")
    source = destination / "source"
    source.mkdir()
    with tarfile.open(archive) as handle:
        for member in handle.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise RuntimeError(f"unsafe path in release archive: {member.name}")
        handle.extractall(source)


def _build_once(ref: str, epoch: str, parent: Path, name: str) -> Path:
    workspace = parent / name
    workspace.mkdir()
    _archive(ref, workspace)
    output = workspace / "dist"
    env = dict(os.environ)
    env.update({"LC_ALL": "C", "PYTHONHASHSEED": "0", "SOURCE_DATE_EPOCH": epoch, "TZ": "UTC"})
    _run(
        sys.executable,
        "-m",
        "build",
        "--no-isolation",
        "--wheel",
        "--outdir",
        str(output),
        cwd=workspace / "source",
        env=env,
    )
    wheels = sorted(output.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"release build produced {len(wheels)} wheels; expected 1")
    _canonicalize_wheel(wheels[0])
    return wheels[0]


def _verify_reader_candidate(
    final_ref: str,
    reader_trial: dict[str, object],
    parent: Path,
) -> None:
    if reader_trial.get("required") is not True:
        return
    candidate = str(reader_trial["candidate_commit"])
    _run("git", "merge-base", "--is-ancestor", candidate, final_ref)
    changed = set(_run("git", "diff", "--name-only", candidate, final_ref).splitlines())
    allowed = {"pyproject.toml", ".clean-docs/reader-trial.json"}
    unexpected = sorted(
        path
        for path in changed
        if path not in allowed and not path.startswith(".clean-docs/reader-trials/")
    )
    if unexpected:
        raise RuntimeError(
            "stable release changed product files after the reader trial: "
            + ", ".join(unexpected)
        )
    candidate_project = _run("git", "show", f"{candidate}:pyproject.toml")
    final_project = _run("git", "show", f"{final_ref}:pyproject.toml")
    version_line = re.compile(r'^version = "[^"]+"$', re.MULTILINE)
    if len(version_line.findall(candidate_project)) != 1 or len(version_line.findall(final_project)) != 1:
        raise RuntimeError("pyproject.toml must contain one project version line")
    if version_line.sub('version = "<release>"', candidate_project) != version_line.sub(
        'version = "<release>"', final_project
    ):
        raise RuntimeError("stable release changed pyproject.toml beyond the version")
    candidate_epoch = _run("git", "show", "-s", "--format=%ct", candidate)
    candidate_wheel = _build_once(candidate, candidate_epoch, parent, "reader-candidate")
    actual = hashlib.sha256(candidate_wheel.read_bytes()).hexdigest()
    if actual != reader_trial["candidate_artifact_sha256"]:
        raise RuntimeError("reader trial candidate artifact digest does not match a reproducible build")


def build_release(output: Path) -> dict[str, object]:
    ref = _run("git", "rev-parse", "HEAD")
    epoch = _run("git", "show", "-s", "--format=%ct", ref)
    with tempfile.TemporaryDirectory(prefix="clean-docs-release-") as temporary:
        parent = Path(temporary)
        evidence = parent / "evidence"
        evidence.mkdir()
        _archive(ref, evidence)
        reader_trial = verify_release_reader_trial(evidence / "source")
        _verify_reader_candidate(ref, reader_trial, parent)
        first = _build_once(ref, epoch, parent, "first")
        second = _build_once(ref, epoch, parent, "second")
        first_bytes = first.read_bytes()
        second_bytes = second.read_bytes()
        if first_bytes != second_bytes:
            raise RuntimeError("wheel bytes differ across two builds of the same commit")
        digest = hashlib.sha256(first_bytes).hexdigest()
        first_sbom = render_sbom(first, int(epoch))
        second_sbom = render_sbom(second, int(epoch))
        if first_sbom != second_sbom:
            raise RuntimeError("SBOM bytes differ across two builds of the same commit")
        output.mkdir(parents=True, exist_ok=True)
        wheel = output / first.name
        wheel.write_bytes(first_bytes)
        sbom = output / f"{wheel.stem}.spdx.json"
        sbom.write_text(first_sbom)
        sbom_digest = hashlib.sha256(first_sbom.encode()).hexdigest()
    receipt: dict[str, object] = {
        "schema": "clean-docs.release.v1",
        "ref": ref,
        "source_date_epoch": int(epoch),
        "artifact": {"file": wheel.name, "sha256": digest},
        "sbom": {"file": sbom.name, "sha256": sbom_digest, "format": "SPDX-2.3"},
        "reproducible_builds": 2,
        "independent_reader_trial": reader_trial,
    }
    receipt_path = output / "release.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (output / "SHA256SUMS").write_text(
        f"{digest}  {wheel.name}\n{sbom_digest}  {sbom.name}\n"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        receipt = build_release(args.out.resolve())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
