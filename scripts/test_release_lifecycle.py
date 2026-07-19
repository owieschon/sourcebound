#!/usr/bin/env python3
"""Exercise install, upgrade, executable rollback, and uninstall with release wheels."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path

from build_release import ROOT, _build_once, _run


def _wheel_version(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise RuntimeError("release wheel must contain one dist-info/METADATA file")
        metadata = Parser().parsestr(archive.read(names[0]).decode("utf-8"))
    version = metadata.get("Version")
    if not version:
        raise RuntimeError("release wheel metadata has no Version")
    return version


def _command(*args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        list(args),
        cwd=ROOT,
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


def verify_lifecycle(candidate: Path) -> None:
    candidate = candidate.resolve()
    candidate_version = _wheel_version(candidate)
    prior_ref = "v0.5.0^{}"
    prior_epoch = _run("git", "show", "-s", "--format=%ct", prior_ref)
    with tempfile.TemporaryDirectory(prefix="clean-docs-lifecycle-") as temporary:
        workspace = Path(temporary)
        prior = _build_once(prior_ref, prior_epoch, workspace, "prior")
        environment = dict(os.environ)
        environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        venv = workspace / "venv"
        _command(sys.executable, "-m", "venv", "--system-site-packages", str(venv))
        executable = venv / "bin" / "clean-docs"
        pip = venv / "bin" / "pip"

        _command(str(pip), "install", str(prior), env=environment)
        prior_version = _command(str(executable), "--version", env=environment)
        if prior_version != "0.5.0":
            raise RuntimeError(
                f"prior release install reported {prior_version!r}, expected '0.5.0'"
            )

        _command(str(pip), "install", "--upgrade", str(candidate), env=environment)
        upgraded_version = _command(str(executable), "--version", env=environment)
        if upgraded_version != candidate_version:
            raise RuntimeError(
                f"candidate upgrade reported {upgraded_version!r}, "
                f"expected {candidate_version!r}"
            )
        fixture = workspace / "mdx-fixture"
        fixture.mkdir()
        _command("git", "init", "-q", str(fixture))
        (fixture / "README.md").write_text("# Fixture\n", encoding="utf-8")
        (fixture / "guide.mdx").write_text(
            "# MDX guide\n\n<Callout>Static content.</Callout>\n",
            encoding="utf-8",
        )
        _command("git", "-C", str(fixture), "add", ".")
        mdx_audit = json.loads(
            _command(
                str(executable),
                "--root",
                str(fixture),
                "audit",
                "--format",
                "json",
                env=environment,
            )
        )
        if (
            "guide.mdx" not in mdx_audit["documents"]
            or mdx_audit["unsupported_documents"]
        ):
            raise RuntimeError("installed wheel did not activate its bundled MDX parser")

        _command(str(pip), "install", "--force-reinstall", str(prior), env=environment)
        rolled_back_version = _command(str(executable), "--version", env=environment)
        if rolled_back_version != "0.5.0":
            raise RuntimeError(
                f"executable rollback reported {rolled_back_version!r}, "
                "expected '0.5.0'"
            )

        _command(str(pip), "install", "--upgrade", str(candidate), env=environment)
        _command(str(pip), "uninstall", "--yes", "clean-docs", env=environment)
        if executable.exists():
            raise RuntimeError("uninstall left the clean-docs executable installed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify_lifecycle(args.wheel)
    except (OSError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(f"lifecycle: {exc}", file=sys.stderr)
        return 1
    print("lifecycle: install, upgrade, rollback, and uninstall passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
