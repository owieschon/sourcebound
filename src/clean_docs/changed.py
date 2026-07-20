from __future__ import annotations

import hashlib
import json
import subprocess
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path

from clean_docs.engine import evaluate
from clean_docs.errors import ConfigurationError, ExtractionError
from clean_docs.execution import ExecutionPolicy
from clean_docs.claims import scan_source_claims
from clean_docs.inventory import (
    PUBLIC_SURFACE_KINDS,
    InventoryItem,
    scan_inventory,
)
from clean_docs.manifest import load_manifest
from clean_docs.models import Binding, ClaimBinding, RegionBinding
from clean_docs.regions import atomic_write
from clean_docs.plugins import discover_plugin_items, merge_plugin_inventory
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
            "schema": "sourcebound.changed.v1",
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
        if (
            isinstance(binding, RegionBinding)
            and binding.extractor in {"repository-inventory", "repository-overview"}
        ):
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
    return path.resolve() / "sourcebound-cache"


def _inventory(
    root: Path,
    ref: str,
    project: Path,
    *,
    use_cache: bool,
    materialized_root: Path | None = None,
    execution_policy: ExecutionPolicy = ExecutionPolicy.TRUSTED,
) -> tuple[tuple[InventoryItem, ...], bool]:
    key_payload = json.dumps(
        {
            "extractor": "repository-inventory@1",
            "parameters": {"project": project.as_posix()},
            "source": ref,
            "execution_policy": execution_policy.value,
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
    repository_snapshot = RepositorySnapshot(root, ref)
    snapshot_context = (
        nullcontext(materialized_root)
        if materialized_root is not None
        else repository_snapshot.materialized_root(
            paths=(() if project == Path(".") else (project,))
        )
    )
    with snapshot_context as snapshot:
        project_root = snapshot / project
        if not project_root.is_dir():
            raise ConfigurationError(f"project does not exist at {ref}: {project}")
        items = list(scan_inventory(project_root).items)
        manifest_path = project_root / ".sourcebound.yml"
        plugins = (
            load_manifest(manifest_path).plugins
            if manifest_path.is_file()
            and execution_policy is ExecutionPolicy.TRUSTED
            else ()
        )
    items = list(
        merge_plugin_inventory(
            tuple(items), discover_plugin_items(repository_snapshot, plugins)
        )
    )
    if use_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(cache_path, json.dumps({
            "schema": "sourcebound.inventory-cache.v1",
            "key": key,
            "items": [asdict(item) for item in items],
        }, sort_keys=True, separators=(",", ":")) + "\n")
    return tuple(items), False


def _check_changed_details(
    root: Path,
    manifest_path: Path,
    *,
    base: str,
    head: str,
    use_cache: bool = True,
    project: Path = Path("."),
    head_snapshot_root: Path | None = None,
    execution_policy: ExecutionPolicy = ExecutionPolicy.TRUSTED,
) -> tuple[ChangedReport, tuple[InventoryItem, ...], tuple[InventoryItem, ...]]:
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
        line for line in _git(
            root, "diff", "--name-only", base_sha, head_sha
        ).splitlines()
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
        root,
        base_sha,
        project,
        use_cache=use_cache,
        execution_policy=execution_policy,
    )
    snapshot_context = (
        nullcontext(head_snapshot_root)
        if head_snapshot_root is not None
        else RepositorySnapshot(root, head_sha).materialized_root()
    )
    with snapshot_context as snapshot:
        head_inventory, head_hit = _inventory(
            root,
            head_sha,
            project,
            use_cache=use_cache,
            materialized_root=snapshot,
            execution_policy=execution_policy,
        )
        base_items = {item.id: item for item in base_inventory}
        head_items = {item.id: item for item in head_inventory}
        required: list[ChangedFinding] = []
        dependencies: dict[str, tuple[str, ...]] = {}
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
                head_project,
                head_manifest,
                binding_id=binding.id,
                execution_policy=execution_policy,
                inventory_items=head_inventory,
            ):
                if not result.changed:
                    continue
                rule = (
                    "execution-skipped"
                    if result.state == "skipped-untrusted-execution"
                    else "binding-drift"
                )
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
                    (
                        f"binding {result.binding_id} is unknown because "
                        "static-only mode skipped repository-declared execution"
                        if result.state == "skipped-untrusted-execution"
                        else f"binding {result.binding_id} changed behind {doc}"
                    ),
                    (
                        "run the binding in a separately configured trusted environment"
                        if result.state == "skipped-untrusted-execution"
                        else f"sourcebound{root_arg} drive --binding {result.binding_id}"
                    ),
                ))
        affected_claim_checks = []
        for claim_check in loaded.source_claim_checks:
            paths = tuple(
                sorted(
                    set(project_changed_files)
                    & {
                        claim_check.doc.as_posix(),
                        claim_check.source.as_posix(),
                        manifest_relative.as_posix(),
                    }
                )
            )
            if not paths:
                continue
            dependencies[f"source-claim:{claim_check.id}"] = paths
            affected_claim_checks.append(claim_check)
        if affected_claim_checks:
            claim_report = scan_source_claims(
                head_project,
                tuple(affected_claim_checks),
                discover=False,
            )
            for claim_result in claim_report.results:
                if claim_result.status != "drift":
                    continue
                rule = "source-claim-drift"
                doc = prefix + claim_result.doc
                source = prefix + claim_result.source
                required.append(
                    ChangedFinding(
                        _finding_id(rule, doc, source, claim_result.locator),
                        rule,
                        doc,
                        source,
                        claim_result.locator,
                        claim_result.detail,
                        "update the documented value or accepted relationship, "
                        "then run sourcebound claims",
                    )
                )
            for missing_claim in claim_report.missing:
                rule = "source-claim-contract-missing"
                doc = prefix + missing_claim.doc
                source = prefix + missing_claim.source
                required.append(
                    ChangedFinding(
                        _finding_id(rule, doc, source, missing_claim.locator),
                        rule,
                        doc,
                        source,
                        missing_claim.locator,
                        f"accepted source claim {missing_claim.id} cannot be verified: "
                        f"{missing_claim.detail}",
                        "restore the documented claim and source locator or remove "
                        "the obsolete relationship from .sourcebound.yml",
                    )
                )

    gaps: list[ChangedFinding] = []
    ignored: list[ChangedFinding] = []
    for identifier in sorted(set(head_items) - set(base_items)):
        inventory_item = head_items[identifier]
        if inventory_item.kind not in PUBLIC_SURFACE_KINDS:
            continue
        rule = "new-public-surface"
        source = prefix + inventory_item.source
        finding = ChangedFinding(
            _finding_id(rule, "", source, inventory_item.locator),
            rule,
            "",
            source,
            inventory_item.locator,
            f"new {inventory_item.kind} {inventory_item.name!r} has coverage "
            f"state {inventory_item.coverage}",
            "add a source binding or a specific .sourcebound-ignore.yml record",
        )
        if inventory_item.coverage == "ignored":
            ignored.append(finding)
        elif inventory_item.coverage not in {"bound", "cataloged"}:
            gaps.append(finding)
    report = ChangedReport(
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
    return report, base_inventory, head_inventory


def check_changed(
    root: Path,
    manifest_path: Path,
    *,
    base: str,
    head: str,
    use_cache: bool = True,
    project: Path = Path("."),
    execution_policy: ExecutionPolicy = ExecutionPolicy.TRUSTED,
) -> ChangedReport:
    report, _, _ = _check_changed_details(
        root,
        manifest_path,
        base=base,
        head=head,
        use_cache=use_cache,
        project=project,
        execution_policy=execution_policy,
    )
    return report


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
                    "name": "sourcebound",
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
