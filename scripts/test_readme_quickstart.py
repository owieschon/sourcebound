#!/usr/bin/env python3
"""Run the README quickstart against one wheel outside the source checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import site
import subprocess
import sys
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "sourcebound.quickstart-verification.v1"


def _wheel_version(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise RuntimeError("candidate wheel must contain one metadata file")
        metadata = Parser().parsestr(archive.read(names[0]).decode("utf-8"))
    version = metadata.get("Version")
    if not version:
        raise RuntimeError("candidate wheel metadata has no version")
    return version


def _quickstart_script() -> str:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("## Install in the repository you want to protect")
    try:
        end = readme.index("\n## ", start + 3)
    except ValueError:
        end = len(readme)
    section = readme[start:end]
    blocks = re.findall(r"```bash\n(.*?)\n```", section, flags=re.DOTALL)
    if len(blocks) != 2:
        raise RuntimeError(
            f"README quickstart must contain two bash blocks, found {len(blocks)}"
        )
    return "\n\n".join(blocks)


def _run_quickstart(candidate: Path, wheelhouse: Path) -> dict[str, object]:
    candidate = candidate.resolve()
    wheelhouse = wheelhouse.resolve()
    if not candidate.is_file():
        raise RuntimeError(f"candidate wheel does not exist: {candidate}")
    if not wheelhouse.is_dir() or not any(
        path.name.lower().startswith("pyyaml-") for path in wheelhouse.glob("*.whl")
    ):
        raise RuntimeError("wheelhouse must contain one PyYAML wheel")
    if not any(path.name.lower().startswith("pip-") for path in wheelhouse.glob("*.whl")):
        raise RuntimeError("wheelhouse must contain one pip wheel for the isolated pipx runtime")
    version = _wheel_version(candidate)
    candidate_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="sourcebound-readme-quickstart-") as raw:
        workspace = Path(raw)
        repository = workspace / "moonbase-status"
        repository.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
        (repository / "README.md").write_text(
            "# Moonbase status\n\n"
            "Moonbase maintainers use this page to keep the public status API and its "
            "documentation in the same orbit.\n",
            encoding="utf-8",
        )
        (repository / "status.py").write_text(
            "def report() -> str:\n    return 'nominal'\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(repository), "add", "."], check=True)

        bin_dir = workspace / "bin"
        bin_dir.mkdir()
        pipx_home = workspace / "pipx-home"
        user_scripts = Path(site.getuserbase()) / "bin"
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "GH_TOKEN", "GITHUB_TOKEN"}
        }
        environment.update(
            {
                "PATH": os.pathsep.join(
                    (bin_dir.as_posix(), user_scripts.as_posix(), environment["PATH"])
                ),
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_FIND_LINKS": f"{candidate.parent} {wheelhouse}",
                "PIP_NO_INDEX": "1",
                "PIPX_BIN_DIR": bin_dir.as_posix(),
                "PIPX_DEFAULT_PYTHON": sys.executable,
                "PIPX_HOME": pipx_home.as_posix(),
                "PIPX_SHARED_LIBS": (workspace / "pipx-shared").as_posix(),
            }
        )
        process = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", _quickstart_script()],
            cwd=repository,
            env=environment,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"README quickstart failed: {detail}")
        executable = bin_dir / "sourcebound"
        python = pipx_home / "venvs/sourcebound/bin/python"
        reported = subprocess.run(
            [str(executable), "--version"],
            cwd=repository,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        module_path = Path(
            subprocess.run(
                [
                    str(python),
                    "-c",
                    "import sourcebound; print(sourcebound.__file__)",
                ],
                cwd=repository,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
        ).resolve()
        if reported != version:
            raise RuntimeError(
                f"quickstart reported {reported!r}, expected wheel version {version!r}"
            )
        if ROOT == module_path or ROOT in module_path.parents:
            raise RuntimeError("quickstart imported Sourcebound from the source checkout")
        if '"ok": true' not in process.stdout:
            raise RuntimeError("README quickstart emitted no successful verification receipt")
        return {
            "schema": SCHEMA,
            "status": "passed",
            "candidate": {
                "file": candidate.name,
                "version": version,
                "sha256": candidate_sha256,
            },
            "environment": {
                "platform": sys.platform,
                "python": sys.version.split()[0],
                "source_checkout_shadowed": False,
                "pythonpath_set": False,
                "package_module": module_path.as_posix(),
            },
            "observed": {
                "installer": "pipx",
                "readme_bash_blocks": 2,
                "verification_receipt": True,
                "network_package_index_used": False,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = _run_quickstart(args.wheel, args.wheelhouse)
        args.out.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(f"README quickstart: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
