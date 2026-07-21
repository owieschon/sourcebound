from __future__ import annotations

import argparse
import base64
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
DOC_VERSION = "4.36.0"
DOC_INTEGRITY = "sha512-i+Ffu32WBMRnvzxhNwxTy6zpJODO2YLlDaqRNgXcbFaQGhFqATBOjZqkhvOMQvlzzikCfKhlWXWSyAg/HP2gzw=="
DOC_URL = "https://registry.npmjs.org/doc-detective/-/doc-detective-4.36.0.tgz"
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


def _sri_sha512(data: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    inputs = _tree_inputs(args.tree)
    with tempfile.TemporaryDirectory(prefix="sourcebound-toolchain-") as temp:
        private_root = Path(temp).resolve()
        home = private_root / "home"
        cache = private_root / "npm-cache"
        prefix = private_root / "npm-prefix"
        fixture_copy = private_root / "fixture"
        archive = private_root / "vale.tar.gz"
        vale_dir = private_root / "vale"
        package_tarball = private_root / "doc-detective.tgz"
        profile = private_root / "deny-network.sb"
        for directory in (home, cache, prefix, vale_dir):
            directory.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / FIXTURE, fixture_copy)

        environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(home),
            "TMPDIR": str(private_root),
            "npm_config_cache": str(cache),
            "npm_config_prefix": str(prefix),
            "npm_config_package_lock": "true",
            "npm_config_update_notifier": "false",
            "CI": "1",
            "DOC_DETECTIVE_AUTOINSTALL": "0",
            "DOC_DETECTIVE_SKIP_AUTO_UPDATE": "1",
            "DOC_DETECTIVE_CACHE_DIR": str(private_root / "doc-detective-cache"),
            "PYTHONPATH": str(ROOT / "src"),
        }

        _checked(["curl", "-fsSL", VALE_URL, "-o", str(archive)], env=environment)
        archive_bytes = archive.read_bytes()
        if _sha256(archive_bytes) != VALE_SHA256:
            raise RuntimeError("Vale archive checksum mismatch")
        with tarfile.open(archive) as extracted:
            extracted.extractall(vale_dir, filter="data")
        vale_binary = next(path for path in vale_dir.rglob("vale") if path.is_file())

        _checked(["curl", "-fsSL", DOC_URL, "-o", str(package_tarball)], env=environment)
        if _sri_sha512(package_tarball.read_bytes()) != DOC_INTEGRITY:
            raise RuntimeError("Doc Detective tarball integrity mismatch")
        _checked([
            "npm", "install", "--prefix", str(prefix), "--ignore-scripts", "--package-lock=true", str(package_tarball),
        ], env=environment)
        lock = prefix / "package-lock.json"
        binary = prefix / "node_modules" / ".bin" / "doc-detective"
        if not lock.is_file() or not binary.is_file():
            raise RuntimeError("private installation did not produce lock and binary")

        profile.write_text("(version 1) (deny network*) (allow default)\n")
        egress_argv = ["sandbox-exec", "-f", str(profile), "python3", "-c", "import socket; socket.create_connection(('1.1.1.1', 443), timeout=2)"]
        egress = _run(egress_argv, env=environment)
        if egress.returncode == 0:
            raise RuntimeError("deny-network profile allowed egress")

        sourcebound_base = _run([sys.executable, "-m", "clean_docs", "--root", str(fixture_copy), "check"], env=environment)
        if sourcebound_base.returncode:
            raise RuntimeError(sourcebound_base.stderr)
        vale_base_argv = ["sandbox-exec", "-f", str(profile), str(vale_binary), "--config", ".vale.ini", "docs/guide.md"]
        vale_base = _run(vale_base_argv, env=environment, cwd=fixture_copy)
        if vale_base.returncode:
            raise RuntimeError(vale_base.stderr)
        doc_base_argv = ["sandbox-exec", "-f", str(profile), str(binary), "--no-auto-update", "--config", ".doc-detective.json", "--input", "doc-detective.spec.json"]
        doc_base = _run(doc_base_argv, env=environment, cwd=fixture_copy)
        if doc_base.returncode:
            raise RuntimeError(doc_base.stderr)

        source = fixture_copy / "src" / "actions.py"
        source.write_text(source.read_text().replace(
            '    "inspect": {"name": "inspect", "audience": "maintainers"},\n',
            '    "inspect": {"name": "inspect", "audience": "maintainers"},\n'
            '    "publish": {"name": "publish", "audience": "reviewers"},\n',
        ))
        sourcebound_mutation = _run([sys.executable, "-m", "clean_docs", "--root", str(fixture_copy), "check"], env=environment)
        if sourcebound_mutation.returncode != 1:
            raise RuntimeError("source mutation did not produce declared drift")
        vale_mutation = _run(vale_base_argv, env=environment, cwd=fixture_copy)
        doc_mutation = _run(doc_base_argv, env=environment, cwd=fixture_copy)
        if vale_mutation.returncode or doc_mutation.returncode:
            raise RuntimeError("unowned mutation changed editorial or procedure result")

        paths = {
            name: _private(value, private_root)
            for name, value in {
                "private_root": private_root,
                "home": home,
                "tmpdir": private_root,
                "npm_cache": cache,
                "npm_prefix": prefix,
                "package_lock": lock,
                "doc_binary": binary,
                "vale_binary": vale_binary,
            }.items()
        }
        receipt = {
            "schema": "sourcebound.toolchain-fixture.v1",
            "staged_tree": args.tree,
            "input_sha256": inputs,
            "private_paths": paths,
            "vale": {"version": VALE_VERSION, "archive_sha256": _sha256(archive_bytes), "binary_sha256": _sha256(vale_binary.read_bytes())},
            "doc_detective": {"version": DOC_VERSION, "tarball_integrity": _sri_sha512(package_tarball.read_bytes()), "binary_sha256": _sha256(binary.read_bytes()), "package_lock_sha256": _sha256(lock.read_bytes()), "telemetry_send": False},
            "network": {"profile_sha256": _sha256(profile.read_bytes()), "egress_probe": _record(egress, egress_argv)},
            "runs": {
                "sourcebound_baseline": _record(sourcebound_base, [sys.executable, "-m", "clean_docs", "--root", str(fixture_copy), "check"]),
                "sourcebound_mutation": _record(sourcebound_mutation, [sys.executable, "-m", "clean_docs", "--root", str(fixture_copy), "check"]),
                "vale_baseline": _record(vale_base, vale_base_argv),
                "vale_mutation": _record(vale_mutation, vale_base_argv),
                "doc_detective_baseline": _record(doc_base, doc_base_argv),
                "doc_detective_mutation": _record(doc_mutation, doc_base_argv),
            },
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
