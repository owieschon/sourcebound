from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clean_docs.audit import audit
from clean_docs.errors import CleanDocsError, ConfigurationError
from clean_docs.execution import resolve_argv
from clean_docs.manifest import load_manifest
from clean_docs.standard import load_default_pack


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


def _git_repository(root: Path) -> DoctorCheck:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return DoctorCheck(
        "git-repository",
        proc.returncode == 0 and proc.stdout.strip() == "true",
        proc.stderr.strip() or proc.stdout.strip() or "git did not identify a worktree",
    )


def diagnose(root: Path, manifest_path: Path) -> tuple[DoctorCheck, ...]:
    root = root.resolve()
    checks = [_git_repository(root)]
    try:
        pack = load_default_pack()
        checks.append(DoctorCheck(
            "default-policy-pack",
            True,
            f"{pack['profile']} pack version {pack['pack_version']}",
        ))
    except CleanDocsError as exc:
        checks.append(DoctorCheck("default-policy-pack", False, str(exc)))
    try:
        report = audit(root)
        checks.append(DoctorCheck(
            "documentation-audit",
            not report.findings,
            f"{len(report.documents)} active documents; {len(report.findings)} findings",
        ))
    except CleanDocsError as exc:
        checks.append(DoctorCheck("documentation-audit", False, str(exc)))
    try:
        manifest = load_manifest(manifest_path)
        checks.append(DoctorCheck(
            "manifest",
            True,
            f"version {manifest.version}; {len(manifest.bindings)} bindings",
        ))
        for command in manifest.commands:
            executable = resolve_argv(command.argv)[0]
            available = shutil.which(executable) is not None or (
                (root / executable).is_file() and "/" in executable
            )
            checks.append(DoctorCheck(
                f"command:{command.id}",
                available,
                executable if available else f"executable not found: {executable}",
            ))
    except ConfigurationError as exc:
        checks.append(DoctorCheck("manifest", False, str(exc)))
    return tuple(checks)
