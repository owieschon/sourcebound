#!/usr/bin/env python3
"""Verify one published Sourcebound release across GitHub, PyPI, pipx, and uv."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SCHEMA = "sourcebound.publication-verification.v1"
PYPI_PROJECT = "sourcebound"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    process = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"{' '.join(args)} failed: {detail}")
    return process.stdout.strip()


def _request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "sourcebound-release-verifier/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} returned a non-object response")
    return payload


def _request_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "sourcebound-release-verifier/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _wait_for_pypi(version: str, wheel_name: str, *, attempts: int, delay: float) -> dict[str, Any]:
    version_url = f"https://pypi.org/pypi/{PYPI_PROJECT}/{version}/json"
    simple_url = f"https://pypi.org/simple/{PYPI_PROJECT}/"
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            payload = _request_json(version_url)
            if wheel_name in _request_text(simple_url):
                return payload
        except (OSError, UnicodeError, ValueError, urllib.error.HTTPError) as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(delay)
    detail = f": {last_error}" if last_error is not None else ""
    raise RuntimeError(f"PyPI did not expose {wheel_name} after {attempts} attempts{detail}")


def _pypi_wheel(payload: dict[str, Any], wheel_name: str) -> tuple[str, str]:
    urls = payload.get("urls")
    if not isinstance(urls, list):
        raise RuntimeError("PyPI release response omitted urls")
    matches = [
        item
        for item in urls
        if isinstance(item, dict)
        and item.get("filename") == wheel_name
        and item.get("packagetype") == "bdist_wheel"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"PyPI exposed {len(matches)} matching wheels; expected 1")
    item = matches[0]
    url = item.get("url")
    digests = item.get("digests")
    digest = digests.get("sha256") if isinstance(digests, dict) else None
    if not isinstance(url, str) or not url.startswith("https://files.pythonhosted.org/"):
        raise RuntimeError("PyPI wheel URL is missing or outside files.pythonhosted.org")
    if not isinstance(digest, str) or len(digest) != 64:
        raise RuntimeError("PyPI wheel response omitted a SHA-256 digest")
    return url, digest


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "sourcebound-release-verifier/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def _checksum_digest(path: Path, wheel_name: str) -> str:
    matches = []
    for line in path.read_text().splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[1] == wheel_name:
            matches.append(parts[0])
    if len(matches) != 1 or len(matches[0]) != 64:
        raise RuntimeError(f"SHA256SUMS must contain exactly one digest for {wheel_name}")
    return matches[0]


def _installed_binary(directory: Path) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    binary = directory / f"sourcebound{suffix}"
    if not binary.is_file():
        raise RuntimeError(f"installer did not create {binary}")
    return binary


def _smoke_installers(
    version: str,
    root: Path,
    temporary: Path,
    *,
    attempts: int = 24,
    delay: float = 5.0,
) -> dict[str, str]:
    specification = f"{PYPI_PROJECT}=={version}"
    if importlib.util.find_spec("pipx") is None:
        raise RuntimeError("pipx module not found; install the workflow's pinned pipx version")

    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable not found")

    last_error: RuntimeError | None = None
    for attempt in range(attempts):
        pipx_home = temporary / "pipx-home"
        pipx_bin = temporary / "pipx-bin"
        uv_bin = temporary / "uv-bin"
        for path in (pipx_home, pipx_bin, temporary / "pipx-shared", temporary / "uv-cache", temporary / "uv-tools", uv_bin):
            shutil.rmtree(path, ignore_errors=True)
        pipx_env = dict(os.environ)
        pipx_env.update(
            {
                "PIPX_BIN_DIR": str(pipx_bin),
                "PIPX_DEFAULT_PYTHON": sys.executable,
                "PIPX_HOME": str(pipx_home),
                "PIPX_SHARED_LIBS": str(temporary / "pipx-shared"),
            }
        )
        uv_env = dict(os.environ)
        uv_env.update(
            {
                "UV_CACHE_DIR": str(temporary / "uv-cache"),
                "UV_TOOL_BIN_DIR": str(uv_bin),
                "UV_TOOL_DIR": str(temporary / "uv-tools"),
            }
        )
        try:
            _run(
                [
                    sys.executable,
                    "-m",
                    "pipx",
                    "install",
                    specification,
                    "--pip-args=--no-cache-dir",
                ],
                env=pipx_env,
            )
            pipx_sourcebound = _installed_binary(pipx_bin)
            pipx_version = _run([str(pipx_sourcebound), "--version"], env=pipx_env)
            _run([str(pipx_sourcebound), "--root", str(root), "doctor"], env=pipx_env)

            _run([uv, "tool", "install", specification], env=uv_env)
            uv_sourcebound = _installed_binary(uv_bin)
            uv_version = _run([str(uv_sourcebound), "--version"], env=uv_env)
            _run([str(uv_sourcebound), "--root", str(root), "doctor"], env=uv_env)
            if pipx_version != version or uv_version != version:
                raise RuntimeError(
                    f"installer versions do not match {version}: pipx={pipx_version}, uv={uv_version}"
                )
            return {"pipx": pipx_version, "uv": uv_version}
        except RuntimeError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay)
    raise RuntimeError(f"installers did not expose {specification} after {attempts} attempts: {last_error}")


def verify_published_release(
    *,
    repo: str,
    tag: str,
    version: str,
    dist: Path,
    root: Path,
    attempts: int = 24,
    delay: float = 5.0,
) -> dict[str, Any]:
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one local wheel, found {len(wheels)}")
    local_wheel = wheels[0]
    local_digest = _sha256(local_wheel)
    checksum_digest = _checksum_digest(dist / "SHA256SUMS", local_wheel.name)
    if local_digest != checksum_digest:
        raise RuntimeError("local wheel does not match SHA256SUMS")

    with tempfile.TemporaryDirectory(prefix="sourcebound-publication-") as temporary_name:
        temporary = Path(temporary_name)
        github = temporary / "github"
        github.mkdir()
        _run(
            [
                "gh",
                "release",
                "download",
                tag,
                "--repo",
                repo,
                "--pattern",
                local_wheel.name,
                "--pattern",
                "SHA256SUMS",
                "--dir",
                str(github),
            ]
        )
        github_wheel = github / local_wheel.name
        github_digest = _sha256(github_wheel)
        github_checksum = _checksum_digest(github / "SHA256SUMS", local_wheel.name)
        _run(["gh", "attestation", "verify", str(github_wheel), "--repo", repo])

        pypi_payload = _wait_for_pypi(
            version,
            local_wheel.name,
            attempts=attempts,
            delay=delay,
        )
        pypi_url, pypi_declared_digest = _pypi_wheel(pypi_payload, local_wheel.name)
        pypi_wheel = temporary / local_wheel.name
        _download(pypi_url, pypi_wheel)
        pypi_digest = _sha256(pypi_wheel)

        observed = {
            "local": local_digest,
            "checksum": checksum_digest,
            "github": github_digest,
            "github_checksum": github_checksum,
            "pypi": pypi_digest,
            "pypi_declared": pypi_declared_digest,
        }
        if set(observed.values()) != {local_digest}:
            raise RuntimeError(f"published wheel digests differ: {observed}")
        installers = _smoke_installers(
            version,
            root,
            temporary,
            attempts=attempts,
            delay=delay,
        )

    return {
        "schema": SCHEMA,
        "ok": True,
        "repo": repo,
        "tag": tag,
        "version": version,
        "wheel": {"file": local_wheel.name, "sha256": local_digest},
        "digests": observed,
        "attestation": "verified",
        "installers": installers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=24)
    parser.add_argument("--delay", type=float, default=5.0)
    args = parser.parse_args()
    try:
        receipt = verify_published_release(
            repo=args.repo,
            tag=args.tag,
            version=args.version,
            dist=args.dist.resolve(),
            root=args.root.resolve(),
            attempts=args.attempts,
            delay=args.delay,
        )
        exit_code = 0
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        receipt = {
            "schema": SCHEMA,
            "ok": False,
            "repo": args.repo,
            "tag": args.tag,
            "version": args.version,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        exit_code = 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
