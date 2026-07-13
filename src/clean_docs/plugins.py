"""Run versioned extension commands against disposable repository snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError, ExtractionError
from clean_docs.execution import resolve_argv
from clean_docs.inventory import InventoryItem, InventoryReport, scan_inventory
from clean_docs.manifest import load_manifest
from clean_docs.models import (
    PLUGIN_API_VERSION,
    EvidenceValue,
    PluginSpec,
    Provenance,
    RegionBinding,
)
from clean_docs.policy import PolicyFinding
from clean_docs.snapshot import RepositorySnapshot


MAX_PLUGIN_OUTPUT_BYTES = 1_000_000
COPY_IGNORES = (".git", ".venv", "node_modules", "__pycache__")


@dataclass(frozen=True)
class PluginResponse:
    plugin: str
    operation: str
    result: dict[str, Any]


def _isolated_copy(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        symlinks=True,
        ignore=shutil.ignore_patterns(*COPY_IGNORES),
    )
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise ExtractionError(
                f"plugin snapshot contains a symbolic link: {path.relative_to(destination)}"
            )


def _run_plugin(
    snapshot: RepositorySnapshot,
    plugin: PluginSpec,
    operation: str,
    payload: dict[str, Any],
) -> PluginResponse:
    if operation not in plugin.interfaces:
        raise ConfigurationError(
            f"plugin {plugin.id} does not implement the {operation} interface"
        )
    request = json.dumps(
        {
            "schema": "clean-docs.plugin-request.v1",
            "api_version": PLUGIN_API_VERSION,
            "operation": operation,
            "snapshot": snapshot.label,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with snapshot.materialized_root() as source, tempfile.TemporaryDirectory(
        prefix="clean-docs-plugin-"
    ) as temporary:
        sandbox = Path(temporary)
        worktree = sandbox / "repository"
        _isolated_copy(source, worktree)
        environment = {
            "HOME": str(sandbox / "home"),
            "TMPDIR": str(sandbox / "tmp"),
            "PATH": os.environ.get("PATH", ""),
            "NO_COLOR": "1",
        }
        Path(environment["HOME"]).mkdir()
        Path(environment["TMPDIR"]).mkdir()
        try:
            proc = subprocess.run(
                resolve_argv(plugin.argv),
                cwd=worktree,
                input=request,
                text=True,
                capture_output=True,
                timeout=plugin.timeout_seconds,
                check=False,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExtractionError(f"plugin {plugin.id} failed to run: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "no output"
        raise ExtractionError(f"plugin {plugin.id} exited {proc.returncode}: {detail[:500]}")
    output_size = len(proc.stdout.encode()) + len(proc.stderr.encode())
    if output_size > MAX_PLUGIN_OUTPUT_BYTES:
        raise ExtractionError(
            f"plugin {plugin.id} output exceeds {MAX_PLUGIN_OUTPUT_BYTES} bytes"
        )
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"plugin {plugin.id} returned invalid JSON: {exc}") from exc
    if (
        not isinstance(raw, dict)
        or set(raw) != {"schema", "api_version", "result"}
        or raw.get("schema") != "clean-docs.plugin-response.v1"
        or raw.get("api_version") != PLUGIN_API_VERSION
        or not isinstance(raw.get("result"), dict)
    ):
        raise ExtractionError(
            f"plugin {plugin.id} must return clean-docs.plugin-response.v1 at API version 1"
        )
    return PluginResponse(plugin.id, operation, raw["result"])


def _digest(value: Any) -> str:
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode()).hexdigest()


def extract_plugin(
    snapshot: RepositorySnapshot, binding: RegionBinding, plugin: PluginSpec
) -> EvidenceValue:
    response = _run_plugin(
        snapshot,
        plugin,
        "extractor",
        {
            "binding": binding.id,
            "source": binding.source.path.as_posix(),
            "renderer": binding.renderer,
            "columns": list(binding.columns),
        },
    )
    if set(response.result) != {"kind", "value"}:
        raise ExtractionError(f"plugin {plugin.id} extractor result must contain kind and value")
    kind = response.result["kind"]
    if kind not in {"list", "mapping", "scalar", "table", "text"}:
        raise ExtractionError(f"plugin {plugin.id} returned unsupported evidence kind: {kind}")
    value = response.result["value"]
    return EvidenceValue(
        kind,
        value,
        Provenance(
            snapshot.label,
            binding.source.path.as_posix(),
            binding.id,
            f"plugin:{plugin.id}@{plugin.api_version}",
            _digest(value),
        ),
    )


def render_plugin(
    snapshot: RepositorySnapshot,
    binding: RegionBinding,
    plugin: PluginSpec,
    evidence: EvidenceValue,
) -> str:
    response = _run_plugin(
        snapshot,
        plugin,
        "renderer",
        {
            "binding": binding.id,
            "kind": evidence.kind,
            "value": evidence.value,
        },
    )
    if set(response.result) != {"content"} or not isinstance(
        response.result["content"], str
    ):
        raise ExtractionError(f"plugin {plugin.id} renderer result must contain text content")
    return response.result["content"]


def check_plugin_policies(
    snapshot: RepositorySnapshot,
    plugins: tuple[PluginSpec, ...],
    documents: dict[str, str],
) -> list[PolicyFinding]:
    findings: list[PolicyFinding] = []
    for plugin in plugins:
        if "policy" not in plugin.interfaces:
            continue
        response = _run_plugin(
            snapshot,
            plugin,
            "policy",
            {"documents": documents},
        )
        raw_findings = response.result.get("findings")
        if set(response.result) != {"findings"} or not isinstance(raw_findings, list):
            raise ExtractionError(f"plugin {plugin.id} policy result must contain a findings list")
        for index, raw in enumerate(raw_findings):
            if not isinstance(raw, dict) or set(raw) != {"doc", "line", "rule", "detail"}:
                raise ExtractionError(
                    f"plugin {plugin.id} policy finding {index} must contain doc, line, rule, and detail"
                )
            if (
                not isinstance(raw["doc"], str)
                or not isinstance(raw["line"], int)
                or raw["line"] < 1
                or not isinstance(raw["rule"], str)
                or not isinstance(raw["detail"], str)
            ):
                raise ExtractionError(f"plugin {plugin.id} policy finding {index} is invalid")
            findings.append(
                PolicyFinding(raw["doc"], raw["line"], raw["rule"], raw["detail"])
            )
    return findings


def discover_plugin_items(
    snapshot: RepositorySnapshot, plugins: tuple[PluginSpec, ...]
) -> tuple[InventoryItem, ...]:
    items: list[InventoryItem] = []
    identifiers: set[str] = set()
    for plugin in plugins:
        if "discoverer" not in plugin.interfaces:
            continue
        response = _run_plugin(snapshot, plugin, "discoverer", {})
        raw_items = response.result.get("items")
        if set(response.result) != {"items"} or not isinstance(raw_items, list):
            raise ExtractionError(f"plugin {plugin.id} discoverer result must contain an items list")
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict) or set(raw) != {
                "kind", "name", "source", "locator", "evidence"
            }:
                raise ExtractionError(
                    f"plugin {plugin.id} item {index} must contain kind, name, source, locator, and evidence"
                )
            if not all(
                isinstance(raw[key], str) and raw[key]
                for key in ("kind", "name", "source", "locator")
            ):
                raise ExtractionError(f"plugin {plugin.id} item {index} has invalid string fields")
            source = Path(raw["source"])
            if source.is_absolute() or ".." in source.parts:
                raise ExtractionError(f"plugin {plugin.id} item {index} source escapes the repository")
            identifier = f"{raw['kind']}:{raw['source']}:{raw['locator']}"
            if identifier in identifiers:
                raise ExtractionError(
                    f"plugin {plugin.id} item {index} duplicates inventory id {identifier}"
                )
            identifiers.add(identifier)
            items.append(
                InventoryItem(
                    identifier,
                    raw["kind"],
                    raw["name"],
                    raw["source"],
                    raw["locator"],
                    f"plugin:{plugin.id}",
                    _digest(raw["evidence"]),
                    "standard-gap",
                )
            )
    return tuple(sorted(items, key=lambda item: item.id))


def merge_plugin_inventory(
    base: tuple[InventoryItem, ...], additions: tuple[InventoryItem, ...]
) -> tuple[InventoryItem, ...]:
    merged = {item.id: item for item in base}
    for item in additions:
        if item.id in merged:
            raise ExtractionError(f"plugin inventory id collides with core evidence: {item.id}")
        merged[item.id] = item
    return tuple(merged[key] for key in sorted(merged))


def scan_extended_inventory(root: Path) -> InventoryReport:
    base = scan_inventory(root)
    manifest_path = root / ".clean-docs.yml"
    if not manifest_path.is_file():
        return base
    manifest = load_manifest(manifest_path)
    additions = discover_plugin_items(RepositorySnapshot(root), manifest.plugins)
    return InventoryReport(base.languages, merge_plugin_inventory(base.items, additions))
