from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from clean_docs.audit import AUDIT_BASELINE_PATH, PROCESS_NAME, audit, write_audit_baseline
from clean_docs.emit import render_llms_txt
from clean_docs.engine import evaluate
from clean_docs.errors import ConfigurationError, PolicyError
from clean_docs.extractors.inventory import INCLUDED_KINDS, extract_repository_overview
from clean_docs.inventory import InventoryItem, scan_inventory
from clean_docs.manifest import load_manifest
from clean_docs.models import (
    LlmsTxtProjection,
    Manifest,
    ProjectionConfig,
    RegionBinding,
    Source,
)
from clean_docs.phrasing import GroundedDraft, ModelRecord, PhrasingProvider, build_model_record
from clean_docs.projections import evaluate_projections
from clean_docs.regions import atomic_write, replace_region
from clean_docs.renderers import render
from clean_docs.snapshot import RepositorySnapshot
from clean_docs.write_gate import redact_secrets


REFERENCE_REGION = "repository-surface"
REFERENCE_SECTION = re.compile(
    r"^## (?:Commands|CLI|Repository surface)\s*\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL
)


@dataclass(frozen=True)
class PlannedWrite:
    path: str
    content: str
    reason: str
    diff: str


@dataclass(frozen=True)
class PlannedMove:
    source: str
    path: str
    reason: str


@dataclass(frozen=True)
class BootstrapPlan:
    facts: tuple[InventoryItem, ...]
    writes: tuple[PlannedWrite, ...]
    moves: tuple[PlannedMove, ...]
    gaps: tuple[str, ...]
    model: ModelRecord | None
    digest: str
    accept_hygiene_baseline: bool = False

    def as_dict(self) -> dict[str, object]:
        facts = []
        for item in self.facts:
            facts.append({
                field: redact_secrets(value)[0] if isinstance(value, str) else value
                for field, value in asdict(item).items()
            })
        return {
            "schema": "clean-docs.content-plan.v1",
            "ok": not self.gaps,
            "digest": self.digest,
            "facts": facts,
            "operations": [
                {
                    "action": "write",
                    "path": write.path,
                    "content": None,
                    "reason": write.reason,
                    "diff": redact_secrets(write.diff)[0],
                }
                for write in self.writes
            ] + [
                {"action": "move", **asdict(move)} for move in self.moves
            ] + ([{
                "action": "write",
                "path": AUDIT_BASELINE_PATH.as_posix(),
                "content": None,
                "reason": "record exact existing documentation debt after bootstrap",
                "diff": None,
            }] if self.accept_hygiene_baseline else []),
            "gaps": list(self.gaps),
            "model": self.model.as_dict() if self.model else None,
        }


def _readme_path(root: Path) -> str:
    names = [path.name for path in root.iterdir() if path.is_file()]
    if "README.md" in names:
        return "README.md"
    candidates = sorted(
        name for name in names if name.lower() == "readme.md"
    )
    return candidates[0] if candidates else "README.md"


def _manifest_text(document: str = "README.md") -> str:
    return f"""\
version: 1
bindings:
  - id: repository-surface
    type: region
    doc: {document}
    region: repository-surface
    extractor: repository-overview
    source: {{path: .}}
    renderer: markdown-fragment
projections:
  llms_txt:
    output: llms.txt
    title: Repository documentation
    summary: Source-bound repository documentation.
"""


def _binding(document: str = "README.md") -> RegionBinding:
    return RegionBinding(
        id="repository-surface",
        doc=Path(document),
        region=REFERENCE_REGION,
        extractor="repository-overview",
        source=Source(Path(".")),
        renderer="markdown-fragment",
        columns=(),
    )


def _reference_document(
    root: Path, document: str, drafts: tuple[GroundedDraft, ...] = ()
) -> str:
    readme = root / document
    current = readme.read_text(encoding="utf-8") if readme.exists() else "# Repository\n"
    binding = _binding(document)
    evidence = extract_repository_overview(RepositorySnapshot(root), binding)
    generated = render(evidence, binding)
    highlights = ""
    if drafts:
        highlights = "### Grounded highlights\n\n" + "\n".join(
            f"- {draft.text}" for draft in drafts
        ) + "\n\n"
    section = (
        "## Repository surface\n\n"
        "This summary is generated from statically detected package, CLI, API, schema, and test surfaces. Run `clean-docs inventory` for the full catalog.\n\n"
        f"{highlights}"
        f"<!-- clean-docs:begin {REFERENCE_REGION} -->\n"
        f"{generated}\n"
        f"<!-- clean-docs:end {REFERENCE_REGION} -->\n"
    )
    if f"<!-- clean-docs:begin {REFERENCE_REGION} -->" in current:
        return replace_region(current, REFERENCE_REGION, generated)
    if REFERENCE_SECTION.search(current):
        return REFERENCE_SECTION.sub(section + "\n", current, count=1).rstrip() + "\n"
    return current.rstrip() + "\n\n" + section


def _diff(path: str, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=path,
        tofile=f"{path} (clean-docs init)",
    ))


def _planned_write(root: Path, path: str, content: str, reason: str) -> PlannedWrite | None:
    target = root / path
    before = target.read_text(encoding="utf-8") if target.exists() else ""
    if before == content:
        return None
    return PlannedWrite(path, content, reason, _diff(path, before, content))


def _archive_moves(root: Path) -> list[PlannedMove]:
    documents = sorted(
        path for path in root.rglob("*.md")
        if path.is_file()
        and path.name != "README.md"
        and "docs/archive" not in path.relative_to(root).as_posix()
        and not set(path.relative_to(root).parts) & {".git", ".venv", "node_modules"}
    )
    moves: dict[str, PlannedMove] = {}
    for path in documents:
        relative = path.relative_to(root).as_posix()
        if PROCESS_NAME.search(path.stem):
            destination = f"docs/archive/clean-docs-init/{relative.removeprefix('docs/')}"
            moves[relative] = PlannedMove(relative, destination, "process-only document")
    by_digest: dict[str, list[Path]] = {}
    for path in documents:
        normalized = "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()).strip()
        if normalized:
            by_digest.setdefault(hashlib.sha256(normalized.encode()).hexdigest(), []).append(path)
    for group in by_digest.values():
        for path in sorted(group)[1:]:
            relative = path.relative_to(root).as_posix()
            destination = f"docs/archive/clean-docs-init/{relative.removeprefix('docs/')}"
            moves.setdefault(relative, PlannedMove(relative, destination, "duplicate document"))
    return sorted(moves.values(), key=lambda item: item.source)


def build_bootstrap_plan(
    root: Path,
    provider: PhrasingProvider | None = None,
    *,
    accept_hygiene_baseline: bool = False,
) -> BootstrapPlan:
    root = root.resolve()
    if not root.is_dir():
        raise ConfigurationError(f"repository root does not exist or is not a directory: {root}")
    readme_path = _readme_path(root)
    existing_manifest = root / ".clean-docs.yml"
    manifest_text = _manifest_text(readme_path)
    if existing_manifest.exists() and existing_manifest.read_text(encoding="utf-8") != manifest_text:
        raise ConfigurationError(
            "init cannot replace an existing manifest; remove it or run inventory and add bindings"
        )
    report = scan_inventory(root)
    facts = tuple(item for item in report.items if item.kind in INCLUDED_KINDS)
    model = build_model_record(root, facts, provider) if provider else None
    readme = _reference_document(root, readme_path, model.drafts if model else ())
    manifest = Manifest(
        path=root / ".clean-docs.yml",
        version=1,
        bindings=(_binding(readme_path),),
        projections=ProjectionConfig(
            llms_txt=LlmsTxtProjection(
                Path("llms.txt"),
                "Repository documentation",
                "Source-bound repository documentation.",
            )
        ),
    )
    assert manifest.projections is not None
    llms_config = manifest.projections.llms_txt
    assert llms_config is not None
    llms = render_llms_txt(
        manifest,
        title=llms_config.title,
        summary=llms_config.summary,
        documents={readme_path: readme.encode("utf-8")},
        output_path=root / llms_config.output,
    )
    writes = [
        item for item in (
            _planned_write(root, readme_path, readme, "bind detected repository surfaces"),
            _planned_write(root, ".clean-docs.yml", manifest_text, "declare the generated binding"),
            _planned_write(root, "llms.txt", llms, "index the source-bound documentation"),
        ) if item is not None
    ]
    supported = {"Python", "TypeScript", "JavaScript"}
    gaps = tuple(
        f"language adapter missing: {language}"
        for language in report.languages
        if language not in supported
    )
    if any(redact_secrets(item.content)[1] for item in writes):
        gaps += ("secret detected in generated documentation",)
    moves = [] if accept_hygiene_baseline else _archive_moves(root)
    payload = json.dumps({
        "facts": [item.id + ":" + item.digest for item in facts],
        "writes": [(item.path, hashlib.sha256(item.content.encode()).hexdigest()) for item in writes],
        "moves": [(item.source, item.path) for item in moves],
        "gaps": gaps,
        "model": model.as_dict() if model else None,
        "accept_hygiene_baseline": accept_hygiene_baseline,
    }, sort_keys=True, separators=(",", ":"))
    return BootstrapPlan(
        facts,
        tuple(writes),
        tuple(moves),
        gaps,
        model,
        hashlib.sha256(payload.encode()).hexdigest(),
        accept_hygiene_baseline,
    )


def apply_bootstrap_plan(root: Path, plan: BootstrapPlan) -> None:
    root = root.resolve()
    if plan.gaps:
        raise ConfigurationError("cannot initialize unsupported surfaces: " + "; ".join(plan.gaps))
    originals = {
        write.path: (root / write.path).read_bytes() if (root / write.path).exists() else None
        for write in plan.writes
    }
    baseline_key = AUDIT_BASELINE_PATH.as_posix()
    if plan.accept_hygiene_baseline and baseline_key not in originals:
        baseline_path = root / AUDIT_BASELINE_PATH
        originals[baseline_key] = (
            baseline_path.read_bytes() if baseline_path.exists() else None
        )
    completed_moves: list[PlannedMove] = []
    try:
        for move in plan.moves:
            source = root / move.source
            destination = root / move.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise ConfigurationError(f"archive destination already exists: {move.path}")
            os.replace(source, destination)
            completed_moves.append(move)
        for write in plan.writes:
            atomic_write(root / write.path, write.content)
        results = evaluate(root, root / ".clean-docs.yml")
        if any(result.changed for result in results):
            raise ConfigurationError("init wrote a baseline that does not pass binding checks")
        if plan.accept_hygiene_baseline:
            write_audit_baseline(root)
        report = audit(root)
        if not report.ok:
            details = "; ".join(
                f"{finding.path}:{finding.line} {finding.rule}" for finding in report.findings[:5]
            )
            if report.stale_baseline:
                details = (details + "; " if details else "") + "; ".join(
                    f"{finding.path}:{finding.line} stale-baseline"
                    for finding in report.stale_baseline[:5]
                )
            raise PolicyError(f"init baseline has policy findings: {details}")
        manifest = load_manifest(root / ".clean-docs.yml")
        if any(result.changed for result in evaluate_projections(root, manifest)):
            raise ConfigurationError("init wrote a baseline with stale projections")
    except Exception:
        for path, content in originals.items():
            target = root / path
            if content is None:
                target.unlink(missing_ok=True)
            else:
                atomic_write(target, content.decode("utf-8"))
        if plan.accept_hygiene_baseline:
            try:
                (root / AUDIT_BASELINE_PATH).parent.rmdir()
            except OSError:
                pass
        for move in reversed(completed_moves):
            source = root / move.source
            destination = root / move.path
            if destination.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, source)
            parent = destination.parent
            while parent != root:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        raise
