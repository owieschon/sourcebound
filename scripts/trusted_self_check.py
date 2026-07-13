#!/usr/bin/env python3
"""Check a candidate tree with both pinned and candidate clean-docs code."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


TRUST_KEYS = {"schema_version", "channel", "commit", "package_version", "required_checks"}
CHECKS = {
    "standard": ("standard", "check"),
    "bindings": ("check",),
}


@dataclass(frozen=True)
class CheckResult:
    authority: str
    check: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def _command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _command(["git", "-C", str(root), *args], cwd=root)


def _load_trust(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read trust record {path}: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != TRUST_KEYS:
        raise RuntimeError(f"trust record must contain exactly: {', '.join(sorted(TRUST_KEYS))}")
    if raw["schema_version"] != 1 or raw["channel"] not in {"bootstrap", "release"}:
        raise RuntimeError("trust record has an unsupported schema or channel")
    if not isinstance(raw["commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", raw["commit"]):
        raise RuntimeError("trust record commit must be a full lowercase SHA-1")
    if not isinstance(raw["package_version"], str) or not raw["package_version"]:
        raise RuntimeError("trust record package_version must be non-empty")
    checks = raw["required_checks"]
    if checks != ["standard", "bindings"]:
        raise RuntimeError("trust record must require standard and bindings checks")
    return raw


def _validate_commit(root: Path, trust: dict[str, Any]) -> None:
    commit = trust["commit"]
    resolved = _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
    if resolved.returncode != 0 or resolved.stdout.strip() != commit:
        raise RuntimeError(f"trusted verifier commit is unavailable: {commit}")
    ancestor = _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    if ancestor.returncode != 0:
        raise RuntimeError(f"trusted verifier is not an ancestor of HEAD: {commit}")
    project = _git(root, "show", f"{commit}:pyproject.toml")
    expected = f'version = "{trust["package_version"]}"'
    if project.returncode != 0 or expected not in project.stdout:
        raise RuntimeError("trusted commit does not match the recorded package version")


def _extract_trusted_source(root: Path, commit: str, destination: Path) -> Path:
    archive = destination / "trusted.tar"
    archived = _git(
        root,
        "archive",
        "--format=tar",
        f"--output={archive}",
        commit,
        "src/clean_docs",
    )
    if archived.returncode != 0:
        raise RuntimeError(f"cannot archive trusted verifier: {archived.stderr.strip()}")
    with tarfile.open(archive) as handle:
        for member in handle.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"unsafe path in trusted archive: {member.name}")
        handle.extractall(destination)
    return destination / "src"


def _trusted_command(source: Path, root: Path, args: tuple[str, ...]) -> list[str]:
    launcher = (
        "import sys;"
        f"sys.path.insert(0, {str(source)!r});"
        "from clean_docs.cli import main;"
        "raise SystemExit(main())"
    )
    return [sys.executable, "-I", "-c", launcher, "--root", str(root), *args]


def _candidate_command(root: Path, args: tuple[str, ...]) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    return [sys.executable, "-m", "clean_docs", "--root", str(root), *args], env


def _trusted_manifest(root: Path, destination: Path) -> Path:
    """Write the manifest subset understood by the pinned verifier."""
    manifest = root / ".clean-docs.yml"
    try:
        raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"cannot prepare trusted manifest view: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("cannot prepare trusted manifest view: root must be a mapping")
    required = {"version", "bindings"}
    if not required <= set(raw):
        raise RuntimeError("cannot prepare trusted manifest view: version or bindings missing")
    legacy = {
        key: raw[key]
        for key in ("version", "bindings", "execution")
        if key in raw
    }
    output = destination / "trusted-manifest.yml"
    output.write_text(yaml.safe_dump(legacy, sort_keys=False), encoding="utf-8")
    return output


def verify(root: Path, trust_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    trust_file = trust_path or root / ".clean-docs-trust.json"
    trust = _load_trust(trust_file)
    _validate_commit(root, trust)
    results: list[CheckResult] = []
    with tempfile.TemporaryDirectory(prefix="clean-docs-trusted-") as temporary:
        temp_root = Path(temporary)
        source = _extract_trusted_source(root, trust["commit"], temp_root)
        trusted_manifest = _trusted_manifest(root, temp_root)
        for check in trust["required_checks"]:
            args = CHECKS[check]
            trusted_args = (
                ("--manifest", str(trusted_manifest), *args)
                if check == "bindings"
                else args
            )
            trusted = _command(_trusted_command(source, root, trusted_args), cwd=root)
            results.append(CheckResult(
                authority="trusted",
                check=check,
                exit_code=trusted.returncode,
                stdout=trusted.stdout,
                stderr=trusted.stderr,
            ))
            candidate_args, candidate_env = _candidate_command(root, args)
            candidate = subprocess.run(
                candidate_args,
                cwd=root,
                env=candidate_env,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            results.append(CheckResult(
                authority="candidate",
                check=check,
                exit_code=candidate.returncode,
                stdout=candidate.stdout,
                stderr=candidate.stderr,
            ))
    return {
        "ok": all(result.ok for result in results),
        "trust": trust,
        "results": [{**asdict(result), "ok": result.ok} for result in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--trust", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.root, args.trust)
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
