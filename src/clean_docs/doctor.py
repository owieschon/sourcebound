from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clean_docs import __version__
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


@dataclass(frozen=True)
class DiagnosticBundle:
    ref: str | None
    checks: tuple[DoctorCheck, ...]
    bindings: int | None
    commands: int | None
    plugins: tuple[str, ...]
    deprecations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "clean-docs.diagnostic.v2",
            "ok": self.ok,
            "version": __version__,
            "runtime": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "system": platform.system(),
                "machine": platform.machine(),
            },
            "repository": {
                "ref": self.ref,
                "bindings": self.bindings,
                "commands": self.commands,
                "plugins": list(self.plugins),
            },
            "checks": [
                {"name": check.name, "ok": check.ok, "detail": check.detail}
                for check in self.checks
            ],
            "included_data": [
                "runtime versions",
                "repository ref",
                "manifest counts and plugin ids",
                "doctor check results",
            ],
            "excluded_data": [
                "environment variables",
                "credentials",
                "document contents",
                "source contents",
                "command arguments",
            ],
            "deprecations": list(self.deprecations),
            "execution": {
                "declared_processes_run": 0,
                "network_isolation": "not-provided",
                "network_observation": "not-instrumented",
            },
        }


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
            report.ok,
            f"{len(report.documents)} active documents; {len(report.findings)} new findings; "
            f"{sum(count for _rule, count in report.advisory_totals)} advisory candidates; "
            f"{len(report.baselined_findings)} baselined; {len(report.stale_baseline)} stale; "
            f"{len(report.unsupported_documents)} unsupported",
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


def build_diagnostic_bundle(root: Path, manifest_path: Path) -> DiagnosticBundle:
    root = root.resolve()
    checks = diagnose(root, manifest_path)
    ref = None
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        ref = proc.stdout.strip()
    try:
        manifest = load_manifest(manifest_path)
        bindings = len(manifest.bindings)
        commands = len(manifest.commands)
        plugins = tuple(item.id for item in manifest.plugins)
        deprecations = manifest.deprecations
    except ConfigurationError:
        bindings = None
        commands = None
        plugins = ()
        deprecations = ()
    return DiagnosticBundle(ref, checks, bindings, commands, plugins, deprecations)
