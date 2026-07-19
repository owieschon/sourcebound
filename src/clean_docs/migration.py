"""Migrate prior manifests with an exact backup and rollback path."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.regions import atomic_write


@dataclass(frozen=True)
class MigrationPlan:
    source_version: int
    target_version: int
    original_sha256: str
    migrated_sha256: str
    original: str
    migrated: str
    diff: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema"] = "sourcebound.manifest-migration.v1"
        payload["backup"] = ".sourcebound.yml.v0.bak"
        return payload


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError("manifest migration source must be a mapping")
    return value


def build_migration_plan(path: Path) -> MigrationPlan:
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read manifest {path}: {exc}") from exc
    try:
        raw = _mapping(yaml.safe_load(original))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc
    source_version = raw.get("version")
    if source_version not in {0, 1}:
        raise ConfigurationError("manifest migration requires source version 0 or 1")
    migrated_data = dict(raw)
    target_version = source_version + 1
    migrated_data["version"] = target_version
    if source_version == 1:
        execution = migrated_data.get("execution")
        if isinstance(execution, dict):
            allowed = execution.get("allowed_commands")
            if isinstance(allowed, dict):
                for command in allowed.values():
                    if isinstance(command, dict):
                        command.pop("network", None)
    migrated = yaml.safe_dump(migrated_data, sort_keys=False, allow_unicode=True)
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            migrated.splitlines(keepends=True),
            fromfile=path.name,
            tofile=f"{path.name} (version {target_version})",
        )
    )
    return MigrationPlan(
        source_version,
        target_version,
        hashlib.sha256(original.encode()).hexdigest(),
        hashlib.sha256(migrated.encode()).hexdigest(),
        original,
        migrated,
        diff,
    )


def backup_path(path: Path, source_version: int = 0) -> Path:
    return path.with_name(path.name + f".v{source_version}.bak")


def apply_migration(path: Path, plan: MigrationPlan) -> Path:
    backup = backup_path(path, plan.source_version)
    if backup.exists():
        raise ConfigurationError(f"migration backup already exists: {backup}")
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read manifest {path}: {exc}") from exc
    if hashlib.sha256(current.encode()).hexdigest() != plan.original_sha256:
        raise ConfigurationError("manifest changed after migration planning")
    atomic_write(backup, plan.original)
    try:
        atomic_write(path, plan.migrated)
    except OSError:
        atomic_write(path, plan.original)
        raise
    return backup


def rollback_migration(path: Path) -> None:
    backups = sorted(path.parent.glob(path.name + ".v*.bak"))
    if len(backups) != 1:
        raise ConfigurationError(
            f"manifest rollback requires one backup, found {len(backups)}"
        )
    backup = backups[0]
    try:
        original = backup.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read migration backup {backup}: {exc}") from exc
    atomic_write(path, original)
    try:
        backup.unlink()
    except OSError as exc:
        raise ConfigurationError(f"cannot remove migration backup {backup}: {exc}") from exc
