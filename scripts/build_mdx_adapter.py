#!/usr/bin/env python3
"""Rebuild and verify the pinned first-party MDX parser bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/mdx-parser"
BUNDLE = ROOT / "src/clean_docs/adapters/mdx_parser.mjs"
DEPENDENCIES = ROOT / "src/clean_docs/adapters/mdx_dependencies.json"


def _package_name(path: str) -> str:
    return path.rsplit("node_modules/", 1)[1]


def _dependency_manifest() -> str:
    lock_path = TOOL / "package-lock.json"
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes)
    if lock.get("lockfileVersion") != 3 or not isinstance(lock.get("packages"), dict):
        raise RuntimeError("MDX parser package-lock.json must use lockfile version 3")
    packages = []
    for path, package in sorted(lock["packages"].items()):
        if not path or package.get("dev") is True:
            continue
        version = package.get("version")
        integrity = package.get("integrity")
        if not isinstance(version, str) or not isinstance(integrity, str):
            raise RuntimeError(f"MDX parser dependency {path} lacks a version or integrity")
        license_name = package.get("license", "NOASSERTION")
        packages.append(
            {
                "integrity": integrity,
                "license": (
                    license_name
                    if isinstance(license_name, str)
                    else "NOASSERTION"
                ),
                "name": _package_name(path),
                "version": version,
            }
        )
    payload = {
        "schema": "sourcebound.mdx-dependencies.v1",
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "packages": packages,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _build_bundle(destination: Path) -> None:
    install = subprocess.run(
        ["npm", "ci", "--ignore-scripts"],
        cwd=TOOL,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if install.returncode != 0:
        raise RuntimeError(install.stderr.strip() or "npm ci failed")
    esbuild = TOOL / "node_modules/.bin/esbuild"
    process = subprocess.run(
        [
            str(esbuild),
            str(TOOL / "src/parser.mjs"),
            "--bundle",
            "--platform=node",
            "--format=esm",
            "--target=node20",
            f"--outfile={destination}",
            "--legal-comments=eof",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "esbuild failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        dependencies = _dependency_manifest()
        with tempfile.TemporaryDirectory(prefix="sourcebound-mdx-build-") as temporary:
            generated_bundle = Path(temporary) / "mdx_parser.mjs"
            _build_bundle(generated_bundle)
            bundle_bytes = generated_bundle.read_bytes()
        if args.write:
            BUNDLE.write_bytes(bundle_bytes)
            DEPENDENCIES.write_text(dependencies, encoding="utf-8")
        else:
            if not BUNDLE.is_file() or BUNDLE.read_bytes() != bundle_bytes:
                raise RuntimeError(
                    "bundled MDX parser is stale; run "
                    "python scripts/build_mdx_adapter.py --write"
                )
            if (
                not DEPENDENCIES.is_file()
                or DEPENDENCIES.read_text(encoding="utf-8") != dependencies
            ):
                raise RuntimeError(
                    "MDX dependency manifest is stale; run "
                    "python scripts/build_mdx_adapter.py --write"
                )
    except (OSError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"mdx-adapter: {exc}")
        return 1
    print(
        json.dumps(
            {
                "bundle_sha256": hashlib.sha256(BUNDLE.read_bytes()).hexdigest(),
                "dependencies_sha256": hashlib.sha256(
                    DEPENDENCIES.read_bytes()
                ).hexdigest(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
