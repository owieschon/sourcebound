from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[2]
FIXTURE = Path("examples/complementary-toolchain")
VALE_VERSION = "3.15.1"
VALE_SHA256 = "968c6d8bf2052bc97aa24274234cc466dbcc249b55ace33dd382c2cdfa93b08c"
VALE_URL = "https://github.com/errata-ai/vale/releases/download/v3.15.1/vale_3.15.1_MacOS_arm64.tar.gz"
TRACKED_INPUTS = (
    "tests/contracts/run_toolchain_fixture.py",
    "examples/complementary-toolchain/.doc-detective.json",
    "examples/complementary-toolchain/doc-detective.spec.json",
    "examples/complementary-toolchain/src/actions.py",
    "examples/complementary-toolchain/README.md",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(argv: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=False, env=env, cwd=cwd)


def _checked(argv: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = _run(argv, env=env, cwd=cwd)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {argv}\n{result.stdout}\n{result.stderr}")
    return result


def _tree_inputs(tree: str) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for path in TRACKED_INPUTS:
        blob = _checked(["git", "-C", str(ROOT), "show", f"{tree}:{path}"]).stdout.encode()
        actual = (ROOT / path).read_bytes()
        if blob != actual:
            raise RuntimeError(f"working bytes differ from staged tree: {path}")
        inputs[path] = _sha256(blob)
    return inputs


def _private(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError(f"path escapes private root: {resolved}") from error
    return str(resolved)


def _record(result: subprocess.CompletedProcess[str], argv: list[str]) -> dict[str, Any]:
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "stdout_sha256": _sha256(result.stdout.encode()),
        "stderr_sha256": _sha256(result.stderr.encode()),
    }


def _python_in(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _sandbox_profile(private_root: Path) -> tuple[str, list[Path]]:
    python_root = Path(sys.executable).resolve().parents[3]
    runtime_roots = [
        Path("/System"),
        Path("/usr"),
        Path("/dev"),
        python_root,
    ]
    readable = [private_root, *(root for root in runtime_roots if root.exists())]
    clauses = [
        "(version 1)",
        "(deny default)",
        "(allow process*)",
        '(allow file-read* (literal "/"))',
        '(allow file-read-metadata (subpath "/Library"))',
        '(allow file-read-metadata (subpath "/private"))',
    ]
    clauses.extend(f'(allow file-read* (subpath "{path}"))' for path in readable)
    clauses.append(f'(allow file-write* (subpath "{private_root}"))')
    clauses.append(
        '(allow file-write* (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr"))'
    )
    clauses.extend(["(allow sysctl-read)", "(deny network*)"])
    return "\n".join(clauses) + "\n", readable


def _sandboxed(profile: Path, argv: list[str]) -> list[str]:
    return ["sandbox-exec", "-f", str(profile), *argv]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--wheel",
        type=Path,
        help="run Sourcebound from this wheel instead of the source checkout",
    )
    parser.add_argument(
        "--wheelhouse",
        type=Path,
        help="offline dependency wheelhouse required with --wheel",
    )
    args = parser.parse_args()

    inputs = _tree_inputs(args.tree)
    with tempfile.TemporaryDirectory(prefix="sourcebound-toolchain-") as temp:
        private_root = Path(temp).resolve()
        home = private_root / "home"
        fixture_copy = private_root / "fixture"
        archive = private_root / "vale.tar.gz"
        vale_dir = private_root / "vale"
        profile = private_root / "deny-network.sb"
        for directory in (home, vale_dir):
            directory.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / FIXTURE, fixture_copy)

        environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(home),
            "TMPDIR": str(private_root),
            "CI": "1",
        }
        sourcebound_runtime: dict[str, object]
        if args.wheel is None:
            environment["PYTHONPATH"] = str(ROOT / "src")
            sourcebound_prefix = [sys.executable, "-m", "sourcebound"]
            sourcebound_runtime = {"installation": "source-tree"}
        else:
            if args.wheelhouse is None:
                raise RuntimeError("--wheel requires --wheelhouse for its runtime dependencies")
            wheel = args.wheel.resolve()
            wheelhouse = args.wheelhouse.resolve()
            if not wheel.is_file():
                raise RuntimeError(f"Sourcebound wheel does not exist: {wheel}")
            dependency_wheels = sorted(
                path
                for path in wheelhouse.glob("*.whl")
                if path.name.lower().startswith("pyyaml-")
            )
            if len(dependency_wheels) != 1:
                raise RuntimeError(
                    "--wheelhouse must contain exactly one PyYAML wheel for offline installation"
                )
            venv = private_root / "sourcebound-runtime"
            _checked(
                [sys.executable, "-m", "venv", str(venv)],
                env=environment,
            )
            venv_config = (venv / "pyvenv.cfg").read_text()
            if "include-system-site-packages = false" not in venv_config:
                raise RuntimeError("wheel runtime must not inherit system site-packages")
            runtime_python = _python_in(venv)
            _checked(
                [
                    str(runtime_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    str(dependency_wheels[0]),
                ],
                env=environment,
            )
            _checked(
                [
                    str(runtime_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    str(wheel),
                ],
                env=environment,
            )
            module_path = Path(
                _checked(
                    [
                        str(runtime_python),
                        "-I",
                        "-c",
                        "import sourcebound; print(sourcebound.__file__)",
                    ],
                    env=environment,
                ).stdout.strip()
            ).resolve()
            site_packages = Path(
                _checked(
                    [
                        str(runtime_python),
                        "-I",
                        "-c",
                        "import site; print(site.getsitepackages()[0])",
                    ],
                    env=environment,
                ).stdout.strip()
            ).resolve()
            if site_packages not in module_path.parents:
                raise RuntimeError("wheel runtime did not import Sourcebound from its own site-packages")
            dist_info = next(site_packages.glob("sourcebound-*.dist-info"), None)
            if dist_info is None:
                raise RuntimeError("wheel runtime has no Sourcebound distribution metadata")
            direct_url = dist_info / "direct_url.json"
            if not direct_url.is_file():
                raise RuntimeError("wheel runtime has no direct wheel provenance")
            direct_url_data = json.loads(direct_url.read_text())
            wheel_sha256 = _sha256(wheel.read_bytes())
            archive_hash = direct_url_data.get("archive_info", {}).get("hash")
            if archive_hash != f"sha256={wheel_sha256}":
                raise RuntimeError("wheel runtime provenance does not match the supplied wheel")
            sourcebound_prefix = [str(runtime_python), "-I", "-m", "sourcebound"]
            sourcebound_runtime = {
                "installation": "wheel",
                "wheel_sha256": wheel_sha256,
                "system_site_packages": False,
                "module_path": _private(module_path, private_root),
                "site_packages": _private(site_packages, private_root),
                "distribution_path": _private(dist_info, private_root),
                "direct_url_sha256": _sha256(direct_url.read_bytes()),
                "direct_url_archive_hash": archive_hash,
                "dependency_wheel_sha256": _sha256(dependency_wheels[0].read_bytes()),
            }

        _checked(["curl", "-fsSL", VALE_URL, "-o", str(archive)], env=environment)
        archive_bytes = archive.read_bytes()
        if _sha256(archive_bytes) != VALE_SHA256:
            raise RuntimeError("Vale archive checksum mismatch")
        with tarfile.open(archive) as extracted:
            extracted.extractall(vale_dir, filter="data")
        vale_binary = next(path for path in vale_dir.rglob("vale") if path.is_file())

        doc_config = json.loads((fixture_copy / ".doc-detective.json").read_text())
        if doc_config != {"telemetry": {"send": False}, "autoUpdate": False}:
            raise RuntimeError("Doc Detective example must explicitly disable telemetry and updates")

        if shutil.which("sandbox-exec") is None:
            raise RuntimeError("toolchain fixture requires sandbox-exec")
        profile_text, allowed_read_roots = _sandbox_profile(private_root)
        profile.write_text(profile_text)
        private_probe = private_root / "containment-positive.txt"
        private_probe_argv = _sandboxed(
            profile,
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "from pathlib import Path; "
                    f"path=Path({str(private_probe)!r}); "
                    "path.write_text('private-root-ok\\n'); "
                    "assert path.read_text() == 'private-root-ok\\n'"
                ),
            ],
        )
        private_probe_result = _run(private_probe_argv, env=environment)
        if private_probe_result.returncode:
            raise RuntimeError(
                "contained profile cannot read and write its private root: "
                f"{private_probe_result.stdout}\n{private_probe_result.stderr}"
            )
        egress_argv = _sandboxed(
            profile,
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "from pathlib import Path; import socket; "
                    f"Path({str(private_root / 'egress-reached')!r}).write_text('reached\\n'); "
                    "socket.create_connection(('1.1.1.1', 443), timeout=2)"
                ),
            ],
        )
        egress = _run(egress_argv, env=environment)
        if egress.returncode == 0 or not (private_root / "egress-reached").is_file():
            raise RuntimeError("egress probe did not reach and reject the network operation")
        host_read_argv = _sandboxed(
            profile,
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(private_root / 'host-read-reached')!r}).write_text('reached\\n'); "
                    f"Path({str(ROOT / 'tests/contracts/run_toolchain_fixture.py')!r}).read_text()"
                ),
            ],
        )
        host_read = _run(host_read_argv, env=environment)
        if host_read.returncode == 0 or not (private_root / "host-read-reached").is_file():
            raise RuntimeError("host-read probe did not reach and reject the host file operation")

        sourcebound_base_argv = [
            *sourcebound_prefix,
            "--root",
            str(fixture_copy),
            "check",
        ]
        sourcebound_base = _run(sourcebound_base_argv, env=environment)
        if sourcebound_base.returncode:
            raise RuntimeError(sourcebound_base.stderr)
        vale_base_argv = _sandboxed(profile, [str(vale_binary), "--config", ".vale.ini", "docs/guide.md"])
        vale_base = _run(vale_base_argv, env=environment, cwd=fixture_copy)
        if vale_base.returncode:
            raise RuntimeError(
                f"Vale failed ({vale_base.returncode}):\n"
                f"{vale_base.stdout}\n{vale_base.stderr}"
            )

        source = fixture_copy / "src" / "actions.py"
        source.write_text(source.read_text().replace(
            '    "inspect": {"name": "inspect", "audience": "maintainers"},\n',
            '    "inspect": {"name": "inspect", "audience": "maintainers"},\n'
            '    "publish": {"name": "publish", "audience": "reviewers"},\n',
        ))
        sourcebound_mutation = _run(sourcebound_base_argv, env=environment)
        if sourcebound_mutation.returncode != 1:
            raise RuntimeError("source mutation did not produce declared drift")
        vale_mutation = _run(vale_base_argv, env=environment, cwd=fixture_copy)
        if vale_mutation.returncode:
            raise RuntimeError("unowned mutation changed the editorial result")

        paths = {
            name: _private(value, private_root)
            for name, value in {
                "private_root": private_root,
                "home": home,
                "tmpdir": private_root,
                "vale_binary": vale_binary,
            }.items()
        }
        receipt = {
            "schema": "sourcebound.toolchain-fixture.v1",
            "staged_tree": args.tree,
            "input_sha256": inputs,
            "private_paths": paths,
            "vale": {"version": VALE_VERSION, "archive_sha256": _sha256(archive_bytes), "binary_sha256": _sha256(vale_binary.read_bytes())},
            "doc_detective": {
                "config_sha256": _sha256(
                    (fixture_copy / ".doc-detective.json").read_bytes()
                ),
                "telemetry_send": False,
                "auto_update": False,
                "execution": "configuration-only",
            },
            "sourcebound_runtime": sourcebound_runtime,
            "containment": {
                "profile_sha256": _sha256(profile.read_bytes()),
                "allowed_read_roots": [str(path) for path in allowed_read_roots],
                "private_probe": _record(private_probe_result, private_probe_argv),
                "egress_reached": (private_root / "egress-reached").is_file(),
                "egress_probe": _record(egress, egress_argv),
                "host_read_reached": (private_root / "host-read-reached").is_file(),
                "host_read_probe": _record(host_read, host_read_argv),
            },
            "runs": {
                "sourcebound_baseline": _record(sourcebound_base, sourcebound_base_argv),
                "sourcebound_mutation": _record(sourcebound_mutation, sourcebound_base_argv),
                "vale_baseline": _record(vale_base, vale_base_argv),
                "vale_mutation": _record(vale_mutation, vale_base_argv),
            },
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
