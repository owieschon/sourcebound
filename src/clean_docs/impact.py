from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import cast

import yaml

from clean_docs import __version__
from clean_docs.changed import ChangedReport, _check_changed_details, _git
from clean_docs.errors import ConfigurationError
from clean_docs.execution import ExecutionPolicy
from clean_docs.inventory import PUBLIC_SURFACE_KINDS, InventoryItem
from clean_docs.manifest import load_manifest
from clean_docs.mdx import MdxParserError, parse_mdx
from clean_docs.models import Manifest, ReviewContract, SymbolBinding
from clean_docs.projections import evaluate_projections
from clean_docs.review_contracts import (
    ReviewContractResult,
    evaluate_review_contracts,
)
from clean_docs.snapshot import RepositorySnapshot


PUBLIC_KINDS = PUBLIC_SURFACE_KINDS | {"ci-job"}
SOURCE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".go",
        ".h",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".scala",
        ".swift",
        ".ts",
        ".tsx",
    }
)
MEDIA_SUFFIXES = frozenset({".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"})
STRUCTURED_SUFFIXES = frozenset({".json", ".toml", ".yaml", ".yml"})
PYTHON_TOOLING_MODULES = frozenset({"conftest.py", "noxfile.py", "setup.py"})
SCRIPT_EXPORT = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:abstract\s+)?"
    r"(?P<kind>function|class|const|interface|type|enum)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)",
    re.M,
)


@dataclass(frozen=True)
class ImpactArtifact:
    path: str
    change: str
    base_blob: str | None
    head_blob: str | None
    adapter: str
    decision: str
    may_expose_public_surface: bool
    coverage: str
    graph_roots: tuple[str, ...]


@dataclass(frozen=True)
class ImpactEvent:
    id: str
    kind: str
    path: str
    item_id: str
    locator: str
    before_digest: str | None
    after_digest: str | None
    coverage: str
    graph_roots: tuple[str, ...]


@dataclass(frozen=True)
class ImpactEdge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class ImpactFinding:
    id: str
    classification: str
    rule: str
    message: str
    paths: tuple[str, ...]
    graph_roots: tuple[str, ...]
    obligations: tuple[str, ...]


@dataclass(frozen=True)
class ImpactPlan:
    producer_version: str
    requested_base: str
    merge_base: str
    head: str
    project: str
    manifest: str
    manifest_digest: str
    input_digest: str
    impact: str
    coverage_complete: bool
    artifacts: tuple[ImpactArtifact, ...]
    events: tuple[ImpactEvent, ...]
    review_contracts: tuple[ReviewContractResult, ...]
    edges: tuple[ImpactEdge, ...]
    required: tuple[ImpactFinding, ...]
    recommended: tuple[ImpactFinding, ...]
    unrelated: tuple[ImpactFinding, ...]
    unknown: tuple[ImpactFinding, ...]

    @property
    def digest(self) -> str:
        return _digest(self._payload())

    @property
    def no_impact(self) -> bool:
        return self.impact == "none"

    @property
    def unsupported_documents(self) -> tuple[str, ...]:
        return tuple(
            artifact.path
            for artifact in self.artifacts
            if artifact.adapter.startswith("mdx-static:failed")
        )

    def _payload(self) -> dict[str, object]:
        roots = sorted(
            {
                root
                for artifact in self.artifacts
                for root in artifact.graph_roots
            }
            | {
                root
                for finding in (
                    self.required
                    + self.recommended
                    + self.unrelated
                    + self.unknown
                )
                for root in finding.graph_roots
            }
        )
        return {
            "schema": "clean-docs.impact-plan.v2",
            "producer": {"name": "clean-docs", "version": self.producer_version},
            "read_only": True,
            "requested_base": self.requested_base,
            "merge_base": self.merge_base,
            "head": self.head,
            "project": self.project,
            "manifest": self.manifest,
            "manifest_digest": self.manifest_digest,
            "input_digest": self.input_digest,
            "impact": self.impact,
            "coverage_complete": self.coverage_complete,
            "no_impact": self.no_impact,
            "unsupported_documents": list(self.unsupported_documents),
            "artifacts": [asdict(item) for item in self.artifacts],
            "events": [asdict(item) for item in self.events],
            "review_contracts": [
                item.as_dict() for item in self.review_contracts
            ],
            "graph": {
                "roots": roots,
                "edges": [asdict(item) for item in self.edges],
            },
            "findings": {
                "required": [asdict(item) for item in self.required],
                "recommended": [asdict(item) for item in self.recommended],
                "unrelated": [asdict(item) for item in self.unrelated],
                "unknown": [asdict(item) for item in self.unknown],
            },
        }

    def as_dict(self) -> dict[str, object]:
        payload = self._payload()
        payload["digest"] = self.digest
        return payload


@dataclass
class _ImpactPreparation:
    changed: ChangedReport
    prefix: str
    project_changed: tuple[str, ...]
    inventory_changes: list[
        tuple[str, InventoryItem | None, InventoryItem | None]
    ]
    public_locator_changes: set[tuple[str, str]]
    required_document_paths: set[str]
    artifact_roots: dict[str, set[str]]
    edges: set[ImpactEdge]
    affected_docs: set[str]


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _identifier(*parts: object) -> str:
    return _digest(list(parts))


def _stable_ast_dump(node: ast.AST) -> str:
    dump = cast(Callable[..., str], ast.dump)
    try:
        return dump(node, include_attributes=False, show_empty=True)
    except TypeError:
        # Python 3.11 and 3.12 include empty fields by default and do not
        # expose the show_empty argument.
        return dump(node, include_attributes=False)


def _python_interface_payload(node: ast.AST) -> dict[str, object]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {
            "kind": type(node).__name__,
            "name": node.name,
            "arguments": _stable_ast_dump(node.args),
            "returns": (
                _stable_ast_dump(node.returns)
                if node.returns is not None
                else None
            ),
            "decorators": [
                _stable_ast_dump(item)
                for item in node.decorator_list
            ],
        }
    if isinstance(node, ast.ClassDef):
        return {
            "kind": type(node).__name__,
            "name": node.name,
            "bases": [
                _stable_ast_dump(item) for item in node.bases
            ],
            "keywords": [
                _stable_ast_dump(item) for item in node.keywords
            ],
            "decorators": [
                _stable_ast_dump(item)
                for item in node.decorator_list
            ],
        }
    raise TypeError(f"unsupported public declaration: {type(node).__name__}")


def _declaration_line(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    return text[line_start:] if line_end == -1 else text[line_start:line_end]


def _balanced_declaration(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    opening_seen = False
    index = start
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if character == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if character == "*" and following == "/":
                block_comment = False
                index += 2
                continue
            index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            index += 1
            continue
        if character == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if character == "/" and following == "*":
            block_comment = True
            index += 2
            continue
        if character in {"'", '"', "`"}:
            quote = character
            index += 1
            continue
        if character == "{":
            opening_seen = True
            depth += 1
        elif character == "}" and opening_seen:
            depth -= 1
            if depth == 0:
                return text[line_start : index + 1]
        index += 1
    return _declaration_line(text, start)


def _script_interface_evidence(text: str, match: re.Match[str]) -> str:
    if match.group("kind") in {"interface", "type", "enum"}:
        return _balanced_declaration(text, match.start())
    return _declaration_line(text, match.start())


def _interface_fingerprints(
    root: Path,
    ref: str,
    project: Path,
    paths: tuple[str, ...],
) -> tuple[dict[str, str], frozenset[str]]:
    fingerprints: dict[str, str] = {}
    failed: set[str] = set()
    snapshot = RepositorySnapshot(root, ref)
    for path in sorted(paths):
        repository_path = (
            path if project == Path(".") else (project / path).as_posix()
        )
        if _blob_id(root, ref, repository_path) is None:
            continue
        try:
            text = snapshot.read_text(Path(repository_path))
        except (OSError, UnicodeDecodeError):
            failed.add(path)
            continue
        candidate = Path(path)
        suffix = candidate.suffix.lower()
        if suffix == ".py":
            try:
                tree = ast.parse(text, filename=path)
            except SyntaxError:
                failed.add(path)
                continue
            is_test = (
                candidate.name.startswith("test_")
                or "/tests/" in f"/{path}"
            )
            if is_test or candidate.name in PYTHON_TOOLING_MODULES:
                continue
            for node in tree.body:
                if not isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ) or node.name.startswith("_"):
                    continue
                item_id = f"api-symbol:{path}:{node.name}"
                fingerprints[item_id] = _digest(
                    _python_interface_payload(node)
                )
        elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
            for match in SCRIPT_EXPORT.finditer(text):
                name = match.group("name")
                item_id = f"api-symbol:{path}:{name}"
                fingerprints[item_id] = _digest(
                    _script_interface_evidence(text, match)
                )
    return fingerprints, frozenset(failed)


def _repo_path(prefix: str, path: str) -> str:
    return f"{prefix}{path}" if prefix else path


def _project_path(prefix: str, path: str) -> str:
    if prefix and path.startswith(prefix):
        return path.removeprefix(prefix)
    return path


def _repository_review_contract(
    contract: ReviewContract,
    project: Path,
) -> ReviewContract:
    if project == Path("."):
        return contract
    return replace(
        contract,
        sources=tuple(
            replace(locator, path=project / locator.path)
            for locator in contract.sources
        ),
        targets=tuple(
            replace(locator, path=project / locator.path)
            for locator in contract.targets
        ),
    )


def _project_review_result(
    result: ReviewContractResult,
    prefix: str,
) -> ReviewContractResult:
    if not prefix:
        return result
    return replace(
        result,
        sources=tuple(
            replace(item, path=_project_path(prefix, item.path))
            for item in result.sources
        ),
        targets=tuple(
            replace(item, path=_project_path(prefix, item.path))
            for item in result.targets
        ),
    )


def _blob_id(root: Path, ref: str, path: str) -> str | None:
    output = _git(root, "ls-tree", ref, "--", path).strip()
    if not output:
        return None
    fields = output.split(None, 3)
    return fields[2] if len(fields) >= 3 else None


def _change_kind(base_blob: str | None, head_blob: str | None) -> str:
    if base_blob is None:
        return "added"
    if head_blob is None:
        return "removed"
    return "modified"


def _event_kind(kind: str, change: str) -> str:
    subject = {
        "api-endpoint": "endpoint",
        "api-symbol": "public-symbol",
        "cli-command": "command",
        "cli-option": "option",
        "ci-job": "ci-job",
        "config-key": "configuration",
        "doc-link": "documentation-link",
        "document": "document",
        "mcp-tool": "mcp-tool",
        "package": "package",
        "package-script": "package-script",
        "runtime-constraint": "supported-runtime",
        "schema": "schema",
        "test-suite": "test-contract",
    }.get(kind, kind)
    return f"{subject}-{change}"


def _projection_inputs(manifest: Manifest) -> dict[str, tuple[str, ...]]:
    if manifest.projections is None:
        return {}
    outputs: dict[str, tuple[str, ...]] = {}
    if manifest.projections.llms_txt is not None:
        llms_projection = manifest.projections.llms_txt
        outputs[llms_projection.output.as_posix()] = tuple(
            path.as_posix() for path in llms_projection.include
        )
    for bundle_projection in manifest.projections.bundles:
        outputs[bundle_projection.output.as_posix()] = tuple(
            path.as_posix() for path in bundle_projection.include
        )
    if manifest.projections.demo is not None:
        demo_projection = manifest.projections.demo
        outputs[demo_projection.output.as_posix()] = (
            demo_projection.evidence.as_posix(),
        )
    return outputs


def _evaluation_contexts(root: Path) -> dict[str, tuple[str, ...]]:
    path = root / ".clean-docs/eval.yml"
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read impact evaluation graph {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid impact evaluation graph {path}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        raise ConfigurationError("impact evaluation graph must contain a tasks list")
    contexts: dict[str, tuple[str, ...]] = {}
    for index, task in enumerate(raw["tasks"]):
        if not isinstance(task, dict) or not isinstance(task.get("id"), str):
            raise ConfigurationError(
                f"impact evaluation graph task {index} needs a string id"
            )
        raw_context = task.get("context", [])
        if not isinstance(raw_context, list) or not all(
            isinstance(item, str) for item in raw_context
        ):
            raise ConfigurationError(
                f"impact evaluation graph task {task['id']} needs a path context"
            )
        contexts[task["id"]] = tuple(sorted(raw_context))
    return contexts


def _adapter_for(
    path: str,
    *,
    event_adapters: tuple[str, ...],
    projection_outputs: set[str],
    manifest_path: str,
) -> str:
    candidate = Path(path)
    if path in projection_outputs:
        return "projection"
    if path == manifest_path:
        return "manifest"
    if path == ".clean-docs/eval.yml":
        return "evaluation"
    if candidate.parts[:2] == (".github", "workflows"):
        return "github-actions-static"
    if event_adapters:
        return "+".join(event_adapters)
    if candidate.name.startswith("test_") or candidate.name.endswith(
        (".test.ts", ".spec.ts", ".test.js", ".spec.js")
    ):
        return "test-files"
    if candidate.suffix == ".md":
        return "markdown"
    if candidate.suffix == ".mdx":
        return "mdx-static"
    if candidate.suffix == ".py":
        return "python-ast"
    if candidate.suffix in {".ts", ".tsx"}:
        return "typescript-static"
    if candidate.suffix in {".js", ".jsx"}:
        return "javascript-static"
    if candidate.suffix in STRUCTURED_SUFFIXES:
        return "structured-static"
    if candidate.suffix in MEDIA_SUFFIXES:
        return "documentation-media"
    if candidate.name in {
        ".editorconfig",
        ".gitignore",
        "LICENSE",
        "LICENSE.txt",
        "uv.lock",
    } or candidate.name.endswith(".lock"):
        return "repository-metadata"
    return "unsupported"


def _may_expose_public_surface(
    path: str, adapter: str, events: tuple[ImpactEvent, ...]
) -> bool:
    if any(event.item_id.split(":", 1)[0] in PUBLIC_KINDS for event in events):
        return True
    candidate = Path(path)
    public_source_path = bool(
        {"src", "lib", "app", "api", "cmd", "packages", "services"}
        & set(candidate.parts[:-1])
    )
    control_surface = (
        candidate.name in {
            "Dockerfile",
            "Makefile",
            "Taskfile.yml",
            "compose.yaml",
            "compose.yml",
            "docker-compose.yaml",
            "docker-compose.yml",
        }
        or candidate.parts[:2] == (".github", "workflows")
    )
    if control_surface:
        return True
    if adapter != "unsupported":
        return False
    return candidate.suffix.lower() in SOURCE_SUFFIXES and (
        public_source_path or len(candidate.parts) == 1
    )


def _adapter_failed(root: Path, ref: str, path: str, adapter: str) -> bool:
    try:
        text = RepositorySnapshot(root, ref).read_text(Path(path))
        if adapter == "python-ast":
            ast.parse(text, filename=path)
        elif adapter == "mdx-static":
            parse_mdx(text)
    except (SyntaxError, UnicodeDecodeError, MdxParserError):
        return True
    return False


def _workflow_jobs(
    root: Path, ref: str, path: str, *, exists: bool
) -> dict[str, str]:
    if not exists:
        return {}
    try:
        raw = yaml.safe_load(RepositorySnapshot(root, ref).read_text(Path(path)))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid workflow {path} at {ref}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("jobs"), dict):
        raise ConfigurationError(f"workflow {path} at {ref} needs a jobs mapping")
    return {
        str(identifier): _digest(job)
        for identifier, job in sorted(raw["jobs"].items())
    }


def _workflow_events(
    root: Path,
    *,
    base: str,
    head: str,
    repository_path: str,
    base_exists: bool,
    head_exists: bool,
    graph_roots: tuple[str, ...],
) -> tuple[ImpactEvent, ...]:
    base_jobs = _workflow_jobs(root, base, repository_path, exists=base_exists)
    head_jobs = _workflow_jobs(root, head, repository_path, exists=head_exists)
    events = []
    for identifier in sorted(set(base_jobs) | set(head_jobs)):
        before = base_jobs.get(identifier)
        after = head_jobs.get(identifier)
        if before == after:
            continue
        change = (
            "added" if before is None else "removed" if after is None else "changed"
        )
        item_id = f"ci-job:{repository_path}:jobs.{identifier}"
        events.append(
            ImpactEvent(
                id=_identifier(item_id, change, before, after),
                kind=f"ci-job-{change}",
                path=repository_path,
                item_id=item_id,
                locator=f"jobs.{identifier}",
                before_digest=before,
                after_digest=after,
                coverage="adapter",
                graph_roots=graph_roots,
            )
        )
    return tuple(events)


def _finding(
    classification: str,
    rule: str,
    message: str,
    *,
    paths: tuple[str, ...],
    roots: tuple[str, ...] = (),
    obligations: tuple[str, ...] = (),
) -> ImpactFinding:
    normalized_paths = tuple(sorted(set(paths)))
    normalized_roots = tuple(sorted(set(roots)))
    normalized_obligations = tuple(sorted(set(obligations)))
    return ImpactFinding(
        id=_identifier(
            classification,
            rule,
            message,
            normalized_paths,
            normalized_roots,
            normalized_obligations,
        ),
        classification=classification,
        rule=rule,
        message=message,
        paths=normalized_paths,
        graph_roots=normalized_roots,
        obligations=normalized_obligations,
    )


def _prepare_impact_plan(
    root: Path,
    manifest_path: Path,
    *,
    merge_base: str,
    head_sha: str,
    use_cache: bool,
    project: Path,
    head_snapshot_root: Path,
    execution_policy: ExecutionPolicy,
) -> _ImpactPreparation:
    changed, base_inventory, head_inventory = _check_changed_details(
        root,
        manifest_path,
        base=merge_base,
        head=head_sha,
        use_cache=use_cache,
        project=project,
        head_snapshot_root=head_snapshot_root,
        execution_policy=execution_policy,
    )
    prefix = "" if project == Path(".") else project.as_posix().rstrip("/") + "/"
    project_changed = tuple(
        _project_path(prefix, path) for path in changed.changed_files
    )
    base_items = {item.id: item for item in base_inventory}
    head_items = {item.id: item for item in head_inventory}
    interface_paths = tuple(
        path
        for path in project_changed
        if Path(path).suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}
    )
    base_interfaces, base_interface_failures = _interface_fingerprints(
        root, changed.base, project, interface_paths
    )
    head_interfaces, head_interface_failures = _interface_fingerprints(
        root, changed.head, project, interface_paths
    )
    inventory_changes = []
    for item_id in sorted(set(base_items) | set(head_items)):
        before_item = base_items.get(item_id)
        after_item = head_items.get(item_id)
        inventory_item = after_item or before_item
        assert inventory_item is not None
        if (
            inventory_item.kind == "api-symbol"
            and inventory_item.source in interface_paths
        ):
            if inventory_item.source in (
                base_interface_failures | head_interface_failures
            ):
                continue
            before_interface = base_interfaces.get(item_id)
            after_interface = head_interfaces.get(item_id)
            if before_interface == after_interface:
                continue
            if before_item is not None and before_interface is not None:
                before_item = replace(before_item, digest=before_interface)
            if after_item is not None and after_interface is not None:
                after_item = replace(after_item, digest=after_interface)
            inventory_changes.append((item_id, before_item, after_item))
            continue
        if (
            before_item is not None
            and after_item is not None
            and before_item.digest == after_item.digest
            and before_item.coverage == after_item.coverage
        ):
            continue
        inventory_changes.append((item_id, before_item, after_item))
    public_locator_changes = {
        (item.source, item.locator)
        for _item_id, before_item, after_item in inventory_changes
        for item in (after_item or before_item,)
        if item is not None and item.kind in PUBLIC_KINDS
    }
    required_document_paths = {
        _project_path(prefix, item.doc)
        for item in changed.required
        if item.doc
    }
    artifact_roots: dict[str, set[str]] = {
        path: set() for path in project_changed
    }
    edges: set[ImpactEdge] = set()
    affected_docs: set[str] = {
        item.source
        for item in head_inventory
        if item.kind == "document" and item.source in project_changed
    }
    for path in affected_docs:
        artifact_roots[path].add(f"document:{path}")
    return _ImpactPreparation(
        changed,
        prefix,
        project_changed,
        inventory_changes,
        public_locator_changes,
        required_document_paths,
        artifact_roots,
        edges,
        affected_docs,
    )


def build_impact_plan(
    root: Path,
    manifest_path: Path,
    *,
    base: str,
    head: str,
    use_cache: bool = True,
    project: Path = Path("."),
    execution_policy: ExecutionPolicy = ExecutionPolicy.TRUSTED,
) -> ImpactPlan:
    root = root.resolve()
    if not base or not head:
        raise ConfigurationError("impact planning requires --base and --head")
    if project.is_absolute() or ".." in project.parts:
        raise ConfigurationError("impact-plan project must stay inside the repository")
    project = (
        Path(project.as_posix().strip("/"))
        if project.as_posix() != "."
        else Path(".")
    )
    project_root = (root / project).resolve()
    try:
        manifest_relative = manifest_path.resolve().relative_to(project_root)
    except ValueError as exc:
        raise ConfigurationError(
            "impact-plan manifest must be inside the selected project"
        ) from exc

    requested_base = RepositorySnapshot(root, base).label
    head_sha = RepositorySnapshot(root, head).label
    merge_base = _git(root, "merge-base", requested_base, head_sha).strip()
    if not merge_base:
        raise ConfigurationError("impact planning could not resolve a merge base")
    with RepositorySnapshot(root, head_sha).materialized_root(
        paths=(() if project == Path(".") else (project,))
    ) as snapshot:
        preparation = _prepare_impact_plan(
            root,
            manifest_path,
            merge_base=merge_base,
            head_sha=head_sha,
            use_cache=use_cache,
            project=project,
            head_snapshot_root=snapshot,
            execution_policy=execution_policy,
        )
        changed = preparation.changed
        prefix = preparation.prefix
        project_changed = preparation.project_changed
        inventory_changes = preparation.inventory_changes
        public_locator_changes = preparation.public_locator_changes
        required_document_paths = preparation.required_document_paths
        artifact_roots = preparation.artifact_roots
        edges = preparation.edges
        affected_docs = preparation.affected_docs
        head_project = snapshot / project
        head_manifest_path = head_project / manifest_relative
        manifest = load_manifest(head_manifest_path)
        manifest_bytes = head_manifest_path.read_bytes()
        manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
        review_contract_results = tuple(
            _project_review_result(result, prefix)
            for result in evaluate_review_contracts(
                root,
                tuple(
                    _repository_review_contract(contract, project)
                    for contract in manifest.review_contracts
                ),
                base=changed.base,
                head=changed.head,
            )
        )
        for result in review_contract_results:
            contract_root = f"review-contract:{result.contract_id}"
            for source_evidence in result.sources:
                repository_path = _repo_path(prefix, source_evidence.path)
                edges.add(
                    ImpactEdge(
                        f"artifact:{repository_path}",
                        contract_root,
                        "affects",
                    )
                )
                if (
                    source_evidence.state in {"added", "changed", "removed"}
                    and source_evidence.path in artifact_roots
                ):
                    artifact_roots[source_evidence.path].add(contract_root)
            for target_evidence in result.targets:
                edges.add(
                    ImpactEdge(
                        contract_root,
                        f"artifact:{_repo_path(prefix, target_evidence.path)}",
                        "requests-review",
                    )
                )
        binding_docs = {
            binding.id: binding.doc.as_posix() for binding in manifest.bindings
        }
        bindings_by_id = {binding.id: binding for binding in manifest.bindings}
        claim_docs = {
            f"source-claim:{claim.id}": claim.doc.as_posix()
            for claim in manifest.source_claim_checks
        }
        for dependency, paths in changed.dependencies.items():
            root_id = (
                dependency
                if dependency.startswith("source-claim:")
                else f"binding:{dependency}"
            )
            doc = claim_docs.get(dependency) or binding_docs.get(dependency)
            for path in paths:
                artifact_roots.setdefault(path, set()).add(root_id)
                edges.add(ImpactEdge(f"artifact:{path}", root_id, "affects"))
            if doc is not None:
                edges.add(ImpactEdge(root_id, f"document:{doc}", "serves"))
                binding = bindings_by_id.get(dependency)
                public_symbol_changed = (
                    isinstance(binding, SymbolBinding)
                    and (
                        binding.source.path.as_posix(),
                        binding.source.symbol or binding.source.path.as_posix(),
                    )
                    in public_locator_changes
                )
                if (
                    doc in required_document_paths
                    or doc in project_changed
                    or public_symbol_changed
                ):
                    affected_docs.add(doc)

        projection_inputs = _projection_inputs(manifest)
        projection_outputs = set(projection_inputs)
        affected_docs.difference_update(projection_outputs)
        manifest_changed = manifest_relative.as_posix() in project_changed
        affected_projections: set[str] = set()
        for output, inputs in projection_inputs.items():
            projection_triggering = sorted(set(inputs) & affected_docs)
            if projection_triggering or manifest_changed:
                affected_projections.add(output)
                for source in projection_triggering:
                    edges.add(
                        ImpactEdge(
                            f"document:{source}",
                            f"projection:{output}",
                            "projects-to",
                        )
                    )
                    if source in artifact_roots:
                        artifact_roots[source].add(f"projection:{output}")
                for path, root_set in artifact_roots.items():
                    if any(
                        root.startswith(("binding:", "source-claim:"))
                        and ImpactEdge(
                            root, f"document:{source}", "serves"
                        )
                        in edges
                        for source in projection_triggering
                        for root in root_set
                    ):
                        root_set.add(f"projection:{output}")
            if output in artifact_roots:
                artifact_roots[output].add(f"projection:{output}")

        projection_states = {
            result.doc: result.changed
            for result in (
                evaluate_projections(head_project, manifest)
                if manifest.projections is not None and affected_projections
                else []
            )
        }
        evaluation_contexts = _evaluation_contexts(head_project)
        evaluation_file_changed = ".clean-docs/eval.yml" in project_changed
        affected_evaluations: dict[str, tuple[str, ...]] = {}
        graph_documents = affected_docs | affected_projections
        for identifier, contexts in evaluation_contexts.items():
            evaluation_triggering = tuple(sorted(set(contexts) & graph_documents))
            if evaluation_triggering or evaluation_file_changed:
                affected_evaluations[identifier] = evaluation_triggering
                for context in evaluation_triggering:
                    source = (
                        f"projection:{context}"
                        if context in projection_outputs
                        else f"document:{context}"
                    )
                    edges.add(
                        ImpactEdge(
                            source,
                            f"evaluation:{identifier}",
                            "verified-by",
                        )
                    )
                    for path, root_set in artifact_roots.items():
                        if source in root_set or (
                            source.startswith("document:")
                            and source.removeprefix("document:") == path
                        ):
                            root_set.add(f"evaluation:{identifier}")
        if evaluation_file_changed:
            artifact_roots[".clean-docs/eval.yml"].update(
                f"evaluation:{identifier}" for identifier in affected_evaluations
            )

    events_by_path: dict[str, list[ImpactEvent]] = {
        path: [] for path in project_changed
    }
    event_adapters: dict[str, set[str]] = {
        path: set() for path in project_changed
    }
    for item_id, before, after in inventory_changes:
        inventory_item = after or before
        assert inventory_item is not None
        if inventory_item.source not in events_by_path:
            continue
        if inventory_item.kind not in PUBLIC_KINDS:
            continue
        change = (
            "added"
            if before is None
            else "removed"
            if after is None
            else "changed"
        )
        event_roots = tuple(sorted(artifact_roots[inventory_item.source]))
        event = ImpactEvent(
            id=_identifier(item_id, change, before.digest if before else None, after.digest if after else None),
            kind=_event_kind(inventory_item.kind, change),
            path=_repo_path(prefix, inventory_item.source),
            item_id=item_id,
            locator=inventory_item.locator,
            before_digest=before.digest if before else None,
            after_digest=after.digest if after else None,
            coverage=inventory_item.coverage,
            graph_roots=event_roots,
        )
        events_by_path[inventory_item.source].append(event)
        event_adapters[inventory_item.source].add(inventory_item.adapter)
    failed_adapters: set[str] = set()
    for path in project_changed:
        if Path(path).parts[:2] != (".github", "workflows"):
            continue
        repository_path = _repo_path(prefix, path)
        base_blob = _blob_id(root, changed.base, repository_path)
        head_blob = _blob_id(root, changed.head, repository_path)
        try:
            workflow_events = _workflow_events(
                root,
                base=changed.base,
                head=changed.head,
                repository_path=repository_path,
                base_exists=base_blob is not None,
                head_exists=head_blob is not None,
                graph_roots=tuple(sorted(artifact_roots[path])),
            )
        except ConfigurationError:
            failed_adapters.add(path)
            workflow_events = ()
        events_by_path[path].extend(workflow_events)
        event_adapters[path].add("github-actions-static")

    manifest_repo_path = _repo_path(prefix, manifest_relative.as_posix())
    artifacts: list[ImpactArtifact] = []
    for repository_path in changed.changed_files:
        path = _project_path(prefix, repository_path)
        base_blob = _blob_id(root, changed.base, repository_path)
        head_blob = _blob_id(root, changed.head, repository_path)
        path_events = tuple(sorted(events_by_path[path], key=lambda item: item.id))
        adapter = _adapter_for(
            path,
            event_adapters=tuple(sorted(event_adapters[path])),
            projection_outputs=projection_outputs,
            manifest_path=manifest_relative.as_posix(),
        )
        adapter_ref = changed.head if head_blob is not None else changed.base
        adapter_failed = path in failed_adapters or _adapter_failed(
            root, adapter_ref, repository_path, adapter
        )
        if adapter_failed:
            adapter = f"{adapter}:failed"
        may_expose = adapter_failed or _may_expose_public_surface(
            path, adapter, path_events
        )
        artifact_graph_roots = tuple(sorted(artifact_roots[path]))
        event_coverages = {event.coverage for event in path_events}
        has_public_event = any(
            event.item_id.split(":", 1)[0] in PUBLIC_KINDS
            for event in path_events
        )
        if path in projection_outputs:
            coverage = "generated"
            decision = "projection output is not a change-impact root"
        elif may_expose and (
            adapter == "unsupported"
            or adapter.endswith(":failed")
            or "standard-gap" in event_coverages
            or not has_public_event
        ):
            coverage = "unknown"
            decision = "public impact is unsupported or lacks an accepted relationship"
        elif artifact_graph_roots:
            coverage = "graph-covered"
            decision = "traversed accepted documentation relationships"
        elif adapter == "unsupported":
            coverage = "unrelated-covered"
            decision = "unsupported artifact is outside recognized public source paths"
        elif path.endswith((".md", ".mdx")):
            coverage = "document-direct"
            decision = "documentation changed directly"
        else:
            coverage = "adapter-covered"
            decision = "adapter found no public contract delta"
        artifacts.append(
            ImpactArtifact(
                path=repository_path,
                change=_change_kind(base_blob, head_blob),
                base_blob=base_blob,
                head_blob=head_blob,
                adapter=adapter,
                decision=decision,
                may_expose_public_surface=may_expose,
                coverage=coverage,
                graph_roots=tuple(
                    _repo_path(prefix, root)
                    if root.startswith("artifact:")
                    else root
                    for root in artifact_graph_roots
                ),
            )
        )

    required: list[ImpactFinding] = []
    recommended: list[ImpactFinding] = []
    unrelated: list[ImpactFinding] = []
    unknown: list[ImpactFinding] = []

    for result in review_contract_results:
        if result.state not in {"review-recommended", "unknown"}:
            continue
        contract_root = f"review-contract:{result.contract_id}"
        message = (
            f"review contract {result.contract_id} observed a source change; "
            "its declared targets require review"
            if result.state == "review-recommended"
            else f"review contract {result.contract_id} could not resolve "
            "every declared locator"
        )
        recommended.append(
            _finding(
                "recommended",
                "review-contract",
                message,
                paths=tuple(
                    _repo_path(prefix, item.path)
                    for item in result.sources + result.targets
                ),
                roots=(contract_root,),
                obligations=("review-declared-targets",),
            )
        )

    for changed_finding in changed.required:
        finding_roots = tuple(
            sorted(
                set(
                    artifact_roots.get(
                        _project_path(prefix, changed_finding.source), set()
                    )
                )
                | set(
                    artifact_roots.get(
                        _project_path(prefix, changed_finding.doc), set()
                    )
                )
            )
        )
        required.append(
            _finding(
                "required",
                changed_finding.rule,
                changed_finding.message,
                paths=tuple(
                    path
                    for path in (changed_finding.doc, changed_finding.source)
                    if path
                ),
                roots=finding_roots,
                obligations=("repair-declared-contract",),
            )
        )
    for changed_finding in changed.gaps:
        finding_roots = tuple(
            sorted(
                artifact_roots.get(
                    _project_path(prefix, changed_finding.source), set()
                )
            )
        )
        unknown.append(
            _finding(
                "unknown",
                changed_finding.rule,
                changed_finding.message,
                paths=tuple(
                    path
                    for path in (changed_finding.doc, changed_finding.source)
                    if path
                ),
                roots=finding_roots,
                obligations=("declare-binding-or-reasoned-ignore",),
            )
        )
    for changed_finding in changed.ignored:
        finding_roots = tuple(
            sorted(
                artifact_roots.get(
                    _project_path(prefix, changed_finding.source), set()
                )
            )
        )
        unrelated.append(
            _finding(
                "unrelated",
                changed_finding.rule,
                changed_finding.message,
                paths=tuple(
                    path
                    for path in (changed_finding.doc, changed_finding.source)
                    if path
                ),
                roots=finding_roots,
                obligations=(),
            )
        )

    public_event_paths: set[str] = set()
    for event in sorted(
        (event for values in events_by_path.values() for event in values),
        key=lambda item: item.id,
    ):
        item_kind = event.item_id.split(":", 1)[0]
        if item_kind not in PUBLIC_KINDS:
            continue
        public_event_paths.add(event.path)
        if event.coverage == "ignored":
            unrelated.append(
                _finding(
                    "unrelated",
                    "ignored-public-contract",
                    f"{event.kind} is covered by a reasoned ignore",
                    paths=(event.path,),
                    roots=event.graph_roots,
                )
            )
            continue
        if event.coverage == "standard-gap":
            unknown.append(
                _finding(
                    "unknown",
                    "unsupported-public-contract",
                    f"{event.kind} has no accepted documentation relationship",
                    paths=(event.path,),
                    roots=event.graph_roots,
                    obligations=("declare-binding-or-reasoned-ignore",),
                )
            )
            continue
        obligations = (
            ("review-reference", "review-migration")
            if event.kind.endswith(("changed", "removed"))
            else ("review-reference",)
        )
        target = required if event.coverage == "bound" else recommended
        classification = "required" if event.coverage == "bound" else "recommended"
        target.append(
            _finding(
                classification,
                "public-contract-change",
                f"{event.kind} reaches {event.coverage} coverage",
                paths=(event.path,),
                roots=event.graph_roots,
                obligations=obligations,
            )
        )

    for output in sorted(affected_projections):
        root_id = f"projection:{output}"
        pending_document_repair = bool(
            set(projection_inputs[output]) & required_document_paths
        )
        if projection_states.get(output) or pending_document_repair:
            state = (
                "is stale after an affected source changed"
                if projection_states.get(output)
                else "must refresh after the planned document repair"
            )
            required.append(
                _finding(
                    "required",
                    "projection-refresh",
                    f"projection {output} {state}",
                    paths=(_repo_path(prefix, output),),
                    roots=(root_id,),
                    obligations=("refresh-projection",),
                )
            )
    for identifier, contexts in sorted(affected_evaluations.items()):
        recommended.append(
            _finding(
                "recommended",
                "evaluation-replay",
                f"evaluation {identifier} consumes affected documentation",
                paths=tuple(_repo_path(prefix, path) for path in contexts)
                or (_repo_path(prefix, ".clean-docs/eval.yml"),),
                roots=(f"evaluation:{identifier}",),
                obligations=("replay-evaluation",),
            )
        )
    if manifest_relative.as_posix() in project_changed:
        recommended.append(
            _finding(
                "recommended",
                "contract-change-review",
                "the documentation control manifest changed",
                paths=(manifest_repo_path,),
                roots=tuple(
                    sorted(artifact_roots[manifest_relative.as_posix()])
                ),
                obligations=("review-contract-scope",),
            )
        )

    classified_paths = {
        path
        for finding in required + recommended + unrelated + unknown
        for path in finding.paths
    }
    for artifact in artifacts:
        if artifact.path in classified_paths or artifact.path in public_event_paths:
            continue
        if artifact.coverage == "unknown":
            unsupported_document = artifact.adapter.startswith("mdx-static:failed")
            unknown.append(
                _finding(
                    "unknown",
                    (
                        "unsupported-document-format"
                        if unsupported_document
                        else "unsupported-public-candidate"
                    ),
                    (
                        f"{artifact.path} is an unsupported MDX document"
                        if unsupported_document
                        else f"{artifact.path} may expose a public surface, "
                        "but no adapter can classify it"
                    ),
                    paths=(artifact.path,),
                    roots=artifact.graph_roots,
                    obligations=(
                        ("add-mdx-adapter-or-review-manually",)
                        if unsupported_document
                        else ("add-adapter-or-declare-scope",)
                    ),
                )
            )
        elif artifact.coverage == "generated":
            unrelated.append(
                _finding(
                    "unrelated",
                    "generated-output",
                    f"{artifact.path} is a projection output, not a recursive impact root",
                    paths=(artifact.path,),
                    roots=artifact.graph_roots,
                )
            )
        elif artifact.coverage == "document-direct":
            unrelated.append(
                _finding(
                    "unrelated",
                    "direct-document-change",
                    f"{artifact.path} already contains the documentation change",
                    paths=(artifact.path,),
                    roots=artifact.graph_roots,
                )
            )
        else:
            unrelated.append(
                _finding(
                    "unrelated",
                    "no-public-contract-delta",
                    f"{artifact.path} has no public documentation obligation in the affected graph",
                    paths=(artifact.path,),
                    roots=artifact.graph_roots,
                )
            )

    def _normalized(items: list[ImpactFinding]) -> tuple[ImpactFinding, ...]:
        return tuple(sorted({item.id: item for item in items}.values(), key=lambda item: item.id))

    normalized_required = _normalized(required)
    normalized_recommended = _normalized(recommended)
    normalized_unrelated = _normalized(unrelated)
    normalized_unknown = _normalized(unknown)
    coverage_complete = not normalized_unknown
    impact = (
        "unknown"
        if normalized_unknown
        else "required"
        if normalized_required
        else "recommended"
        if normalized_recommended
        else "none"
    )
    normalized_artifacts = tuple(sorted(artifacts, key=lambda item: item.path))
    normalized_events = tuple(
        sorted(
            (event for values in events_by_path.values() for event in values),
            key=lambda item: item.id,
        )
    )
    input_digest = _digest(
        {
            "requested_base": requested_base,
            "merge_base": changed.base,
            "head": changed.head,
            "project": project.as_posix(),
            "manifest": manifest_repo_path,
            "manifest_digest": manifest_digest,
            "review_contracts": [
                result.as_dict() for result in review_contract_results
            ],
            "artifacts": [
                {
                    "path": artifact.path,
                    "base_blob": artifact.base_blob,
                    "head_blob": artifact.head_blob,
                }
                for artifact in normalized_artifacts
            ],
        }
    )
    return ImpactPlan(
        producer_version=__version__,
        requested_base=requested_base,
        merge_base=changed.base,
        head=changed.head,
        project=project.as_posix(),
        manifest=manifest_repo_path,
        manifest_digest=manifest_digest,
        input_digest=input_digest,
        impact=impact,
        coverage_complete=coverage_complete,
        artifacts=normalized_artifacts,
        events=normalized_events,
        review_contracts=review_contract_results,
        edges=tuple(
            sorted(edges, key=lambda item: (item.source, item.target, item.kind))
        ),
        required=normalized_required,
        recommended=normalized_recommended,
        unrelated=normalized_unrelated,
        unknown=normalized_unknown,
    )


def render_impact_plan(plan: ImpactPlan) -> str:
    lines = [
        f"impact: {plan.impact}",
        f"plan: sha256:{plan.digest}",
        f"diff: {plan.merge_base}..{plan.head}",
        f"coverage: {'complete' if plan.coverage_complete else 'unknown'}",
    ]
    for artifact in plan.artifacts:
        lines.append(
            f"[{artifact.coverage}] {artifact.path}: "
            f"{artifact.adapter}; {artifact.decision}"
        )
    for classification, findings in (
        ("required", plan.required),
        ("recommended", plan.recommended),
        ("unrelated", plan.unrelated),
        ("unknown", plan.unknown),
    ):
        for finding in findings:
            lines.append(f"[{classification}] {finding.rule}: {finding.message}")
            if finding.obligations:
                lines.append(f"obligations: {', '.join(finding.obligations)}")
    return "\n".join(lines) + "\n"
