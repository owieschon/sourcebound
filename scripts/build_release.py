#!/usr/bin/env python3
"""Build and verify one reproducible wheel from the current Git commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        list(args),
        cwd=cwd,
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
    return wheels[0]


def build_release(output: Path) -> dict[str, object]:
    ref = _run("git", "rev-parse", "HEAD")
    epoch = _run("git", "show", "-s", "--format=%ct", ref)
    with tempfile.TemporaryDirectory(prefix="clean-docs-release-") as temporary:
        parent = Path(temporary)
        first = _build_once(ref, epoch, parent, "first")
        second = _build_once(ref, epoch, parent, "second")
        first_bytes = first.read_bytes()
        second_bytes = second.read_bytes()
        if first_bytes != second_bytes:
            raise RuntimeError("wheel bytes differ across two builds of the same commit")
        digest = hashlib.sha256(first_bytes).hexdigest()
        output.mkdir(parents=True, exist_ok=True)
        wheel = output / first.name
        wheel.write_bytes(first_bytes)
    receipt: dict[str, object] = {
        "schema": "clean-docs.release.v1",
        "ref": ref,
        "source_date_epoch": int(epoch),
        "artifact": {"file": wheel.name, "sha256": digest},
        "reproducible_builds": 2,
    }
    receipt_path = output / "release.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (output / "SHA256SUMS").write_text(f"{digest}  {wheel.name}\n")
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
