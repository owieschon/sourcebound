from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path

from clean_docs.engine import evaluate
from clean_docs.errors import ConfigurationError, ExtractionError
from clean_docs.inventory import InventoryItem, scan_inventory
from clean_docs.manifest import load_manifest
from clean_docs.models import Binding, ClaimBinding, RegionBinding
from clean_docs.regions import atomic_write
from clean_docs.snapshot import RepositorySnapshot


CHANGED_CHECK_BUDGET_SECONDS = 5.0


@dataclass(frozen=True)
class ChangedFinding:
    id: str
    rule: str
    doc: str
    source: str
    locator: str
    message: str
    repair: str


@dataclass(frozen=True)
class ChangedReport:
    base: str
    head: str
    project: str
    changed_files: tuple[str, ...]
    required: tuple[ChangedFinding, ...]
    gaps: tuple[ChangedFinding, ...]
    ignored: tuple[ChangedFinding, ...]
    dependencies: dict[str, tuple[str, ...]]
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def ok(self) -> bool:
        return not self.required and not self.gaps

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "clean-docs.changed.v1",
            "ok": self.ok,
            "base": self.base,
            "head": self.head,
            "project": self.project,
            "changed_files": list(self.changed_files),
            "required": [asdict(item) for item in self.required],
            "gaps": [asdict(item) for item in self.gaps],
            "ignored": [asdict(item) for item in self.ignored],
            "dependencies": {
                binding: list(paths) for binding, paths in sorted(self.dependencies.items())
            },
        }


def _finding_id(rule: str, doc: str, source: str, locator: str) -> str:
    value = json.dumps([rule, doc, source, locator], separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


def _affected_paths(
    binding: Binding,
    changed: tuple[str, ...],
    manifest_path: str,
) -> tuple[str, ...]:
    matched = {path for path in changed if path in {binding.doc.as_posix(), manifest_path}}
    if isinstance(binding, ClaimBinding):
        matched.update(changed)
    else:
        source = binding.source
        if isinstance(binding, RegionBinding) and binding.extractor == "repository-inventory":
            matched.update(changed)
        elif source.glob:
            matched.update(path for path in changed if fnmatch(path, source.glob))
        elif source.path.as_posix() in changed:
            matched.add(source.path.as_posix())
    return tuple(sorted(matched))


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown git error"
        raise ExtractionError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout


def _cache_root(root: Path) -> Path:
    git_dir = _git(root, "rev-parse", "--git-dir").strip()
    path = Path(git_dir)
    if not path.is_absolute():
        path = root / path
    return path.resolve() / "clean-docs-cache"


def _inventory(
    root: Path, ref: str, project: Path, *, use_cache: bool
) -> tuple[tuple[InventoryItem, ...], bool]:
    key_payload = json.dumps(
        {
            "extractor": "repository-inventory@1",
            "parameters": {"project": project.as_posix()},
            "source": ref,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    key = hashlib.sha256(key_payload.encode()).hexdigest()
    cache_path = _cache_root(root) / f"inventory-{key}.json"
    if use_cache and cache_path.is_file():
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            if (
                isinstance(raw, dict)
                and raw.get("key") == key
                and isinstance(raw.get("items"), list)
            ):
                return tuple(InventoryItem(**item) for item in raw["items"]), True
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    with RepositorySnapshot(root, ref).materialized_root() as snapshot:
        project_root = snapshot / project
        if not project_root.is_dir():
            raise ConfigurationError(f"project does not exist at {ref}: {project}")
        items = scan_inventory(project_root).items
    if use_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(cache_path, json.dumps({
            "schema": "clean-docs.inventory-cache.v1",
            "key": key,
            "items": [asdict(item) for item in items],
        }, sort_keys=True, separators=(",", ":")) + "\n")
    return items, False


def check_changed(
    root: Path,
    manifest_path: Path,
    *,
    base: str,
    head: str,
    use_cache: bool = True,
    project: Path = Path("."),
) -> ChangedReport:
    root = root.resolve()
    if not base or not head:
        raise ConfigurationError("check --changed requires --base and --head")
    if project.is_absolute() or ".." in project.parts:
        raise ConfigurationError("check --changed project must stay inside the repository")
    project = Path(project.as_posix().strip("/")) if project.as_posix() != "." else Path(".")
    project_root = (root / project).resolve()
    try:
        manifest_relative = manifest_path.resolve().relative_to(project_root)
    except ValueError as exc:
        raise ConfigurationError("changed-check manifest must be inside the selected project") from exc
    base_sha = RepositorySnapshot(root, base).label
    head_sha = RepositorySnapshot(root, head).label
    all_changed_files = tuple(sorted(
        line for line in _git(root, "diff", "--name-only", base_sha, head_sha).splitlines()
        if line
    ))
    prefix = "" if project == Path(".") else project.as_posix().rstrip("/") + "/"
    changed_files = tuple(
        path for path in all_changed_files if not prefix or path.startswith(prefix)
    )
    project_changed_files = tuple(
        path.removeprefix(prefix) if prefix else path for path in changed_files
    )
    base_inventory, base_hit = _inventory(
        root, base_sha, project, use_cache=use_cache
    )
    head_inventory, head_hit = _inventory(
        root, head_sha, project, use_cache=use_cache
    )
    base_items = {item.id: item for item in base_inventory}
    head_items = {item.id: item for item in head_inventory}

    required: list[ChangedFinding] = []
    dependencies: dict[str, tuple[str, ...]] = {}
    with RepositorySnapshot(root, head_sha).materialized_root() as snapshot:
        head_project = snapshot / project
        head_manifest = head_project / manifest_relative
        loaded = load_manifest(head_manifest)
        for binding in loaded.bindings:
            paths = _affected_paths(
                binding, project_changed_files, manifest_relative.as_posix()
            )
            if not paths:
                continue
            dependencies[binding.id] = paths
            for result in evaluate(
                head_project, head_manifest, binding_id=binding.id
            ):
                if not result.changed:
                    continue
                rule = "binding-drift"
                doc = prefix + result.doc
                source = prefix + result.provenance.path
                root_arg = (
                    "" if project == Path(".") else f" --root {project.as_posix()}"
                )
                required.append(ChangedFinding(
                    _finding_id(rule, doc, source, result.provenance.locator),
                    rule,
                    doc,
                    source,
                    result.provenance.locator,
                    f"binding {result.binding_id} changed behind {doc}",
                    f"clean-docs{root_arg} drive --binding {result.binding_id}",
                ))

    gaps: list[ChangedFinding] = []
    ignored: list[ChangedFinding] = []
    for identifier in sorted(set(head_items) - set(base_items)):
        item = head_items[identifier]
        rule = "new-public-surface"
        source = prefix + item.source
        finding = ChangedFinding(
            _finding_id(rule, "", source, item.locator),
            rule,
            "",
            source,
            item.locator,
            f"new {item.kind} {item.name!r} has coverage state {item.coverage}",
            "add a source binding or a specific .clean-docs-ignore.yml record",
        )
        if item.coverage == "ignored":
            ignored.append(finding)
        elif item.coverage != "bound":
            gaps.append(finding)
    return ChangedReport(
        base_sha,
        head_sha,
        project.as_posix(),
        changed_files,
        tuple(sorted(required, key=lambda item: item.id)),
        tuple(sorted(gaps, key=lambda item: item.id)),
        tuple(sorted(ignored, key=lambda item: item.id)),
        dependencies,
        int(base_hit) + int(head_hit),
        int(not base_hit) + int(not head_hit),
    )


def render_sarif(report: ChangedReport) -> str:
    findings = [
        (finding, "error") for finding in report.required
    ] + [
        (finding, "warning") for finding in report.gaps
    ]
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "clean-docs",
                    "rules": [
                        {"id": rule, "shortDescription": {"text": rule.replace("-", " ")}}
                        for rule in sorted({finding.rule for finding, _level in findings})
                    ],
                }
            },
            "results": [
                {
                    "ruleId": finding.rule,
                    "level": level,
                    "message": {"text": f"{finding.message}. Repair: {finding.repair}"},
                    "partialFingerprints": {"cleanDocsFindingId": finding.id},
                    "locations": [{
                        "physicalLocation": {
                            "artifactLocation": {"uri": finding.doc or finding.source},
                        }
                    }],
                }
                for finding, level in findings
            ],
        }],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
