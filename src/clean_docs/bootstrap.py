from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from clean_docs.applicability import classify_document
from clean_docs.audit import AUDIT_BASELINE_PATH, audit, write_audit_baseline
from clean_docs.claims import SourceClaimResult, scan_source_claims
from clean_docs.corpus import list_documents
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
from clean_docs.policy import REGISTER_PROFILE, ensure_purpose_contract
from clean_docs.projections import evaluate_projections
from clean_docs.regions import atomic_write, replace_region
from clean_docs.renderers import render
from clean_docs.snapshot import RepositorySnapshot
from clean_docs.write_gate import redact_secrets


REFERENCE_REGION = "repository-surface"
GENERATED_REFERENCE = ".sourcebound/repository-surface.md"
PLAN_FACT_LIMIT = 100
PLAN_DIFF_LIMIT = 4000
PLAN_CANDIDATE_LIMIT = 12
REFERENCE_SECTION = re.compile(
    r"^## Repository surface\s*\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL
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
class BindingCandidate:
    """One bounded, advisory source-to-prose relationship discovered at init."""

    id: str
    relationship: str
    kind: str
    document: str
    anchor: str
    source: str
    locator: str
    ownership_evidence: tuple[str, ...]
    advisory_reason: str
    manifest_entry: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "ownership_evidence": list(self.ownership_evidence),
            "next_step": (
                "Review this relationship, then add manifest_entry under "
                "source_claim_checks in .sourcebound.yml or reject it."
            ),
        }


@dataclass(frozen=True)
class DirectProtectionSummary:
    directly_protected: int
    cataloged_only_after_init: int
    candidate_population: int
    candidate_shown: int
    candidate_truncated: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class BootstrapPlan:
    facts: tuple[InventoryItem, ...]
    writes: tuple[PlannedWrite, ...]
    moves: tuple[PlannedMove, ...]
    gaps: tuple[str, ...]
    model: ModelRecord | None
    digest: str
    canonical_documents: tuple[str, ...] = ()
    accept_hygiene_baseline: bool = False
    direct_protection: DirectProtectionSummary | None = None
    binding_candidates: tuple[BindingCandidate, ...] = ()

    def as_dict(self) -> dict[str, object]:
        facts = []
        for item in self.facts:
            facts.append({
                field: redact_secrets(value)[0] if isinstance(value, str) else value
                for field, value in asdict(item).items()
            })
        serialized_facts = facts[:PLAN_FACT_LIMIT]
        return {
            "schema": "sourcebound.content-plan.v1",
            "ok": not self.gaps,
            "digest": self.digest,
            "fact_count": len(facts),
            "facts": serialized_facts,
            "facts_omitted": len(facts) - len(serialized_facts),
            "canonical_documents": list(self.canonical_documents),
            "direct_protection": (
                None
                if self.direct_protection is None
                else self.direct_protection.as_dict()
            ),
            "binding_candidates": [
                candidate.as_dict() for candidate in self.binding_candidates
            ],
            "operations": [
                {
                    "action": "write",
                    "path": write.path,
                    "content": None,
                    "reason": write.reason,
                    "diff": redact_secrets(write.diff[:PLAN_DIFF_LIMIT])[0],
                    "diff_truncated": len(write.diff) > PLAN_DIFF_LIMIT,
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


def _manifest_text(
    document: str = "README.md", canonical_documents: tuple[str, ...] = ()
) -> str:
    declared = tuple(path for path in canonical_documents if path != document)
    include = ""
    if declared:
        include = "    include:\n" + "".join(
            f"      - {json.dumps(path)}\n" for path in declared
        )
    return f"""\
version: 2
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
    summary: Bound facts and explicitly declared canonical repository context.
{include}
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
    existing = readme.exists()
    title = "# Repository surface\n" if document == GENERATED_REFERENCE else "# Repository\n"
    current = readme.read_text(encoding="utf-8") if existing else title
    current, _redaction_rules = redact_secrets(current)
    registered = REGISTER_PROFILE in current
    if registered:
        current = ensure_purpose_contract(current, fallback=False)
    if not existing and document != GENERATED_REFERENCE:
        lines = current.splitlines()
        heading = next((index for index, line in enumerate(lines) if line.startswith("# ")), 0)
        purpose = [
            REGISTER_PROFILE,
            "<!-- sourcebound:purpose -->",
            "Use this repository guide when you need to run or change this project. Without a "
            "source-bound overview, entry points and public surfaces can drift from the "
            "implementation; after reading, you can locate the detected surfaces and verify "
            "their current sources.",
            "<!-- sourcebound:end purpose -->",
        ]
        lines[heading + 1:heading + 1] = ["", *purpose]
        current = "\n".join(lines).rstrip() + "\n"
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
        "This summary is a static catalog of detected package, CLI, API, schema, and test "
        "surfaces. It does not validate existing prose claims. Direct manifest bindings are "
        "the accuracy boundary; run `sourcebound inventory` for coverage state and the full "
        "catalog.\n\n"
        f"{highlights}"
        f"<!-- sourcebound:begin {REFERENCE_REGION} -->\n"
        f"{generated}\n"
        f"<!-- sourcebound:end {REFERENCE_REGION} -->\n"
    )
    if f"<!-- sourcebound:begin {REFERENCE_REGION} -->" in current:
        return replace_region(current, REFERENCE_REGION, generated)
    if REFERENCE_SECTION.search(current):
        return REFERENCE_SECTION.sub(section + "\n", current, count=1).rstrip() + "\n"
    return current.rstrip() + "\n\n" + section


def _diff(path: str, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=path,
        tofile=f"{path} (sourcebound init)",
    ))


def _planned_write(root: Path, path: str, content: str, reason: str) -> PlannedWrite | None:
    target = root / path
    before = target.read_text(encoding="utf-8") if target.exists() else ""
    if before == content:
        return None
    return PlannedWrite(path, content, reason, _diff(path, before, content))


def _archive_moves(root: Path) -> list[PlannedMove]:
    # Filename and text-overlap heuristics cannot prove that a record is
    # obsolete or that two files have the same owner. Init only plans
    # reversible generated writes; archival remains an explicit operator act.
    del root
    return []


def _canonical_documents(
    root: Path, readme_path: str, excluded: set[str]
) -> tuple[str, ...]:
    del root, excluded
    return (readme_path,)


def _binding_candidate(result: SourceClaimResult) -> BindingCandidate:
    return BindingCandidate(
        id=result.id,
        relationship="source-claim",
        kind=result.kind,
        document=result.doc,
        anchor=result.anchor,
        source=result.source,
        locator=result.locator,
        ownership_evidence=result.ownership_evidence,
        advisory_reason=(
            "Static ownership evidence can locate a bounded fact, but it cannot "
            "prove this prose should become gate authority."
        ),
        manifest_entry={
            "id": f"source-claim-{result.id[:12]}",
            "kind": result.kind,
            "doc": result.doc,
            "anchor": result.anchor,
            "subject": result.subject,
            "source": result.source,
            "locator": result.locator,
        },
    )


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
    readme = root / readme_path
    binding_document = readme_path
    if readme.exists() and REGISTER_PROFILE not in readme.read_text(encoding="utf-8"):
        binding_document = GENERATED_REFERENCE
        generated_reference = root / binding_document
        if (
            generated_reference.exists()
            and f"<!-- sourcebound:begin {REFERENCE_REGION} -->"
            not in generated_reference.read_text(encoding="utf-8")
        ):
            raise ConfigurationError(
                f"init cannot replace the reserved generated document: {binding_document}"
            )
    archive_candidates = _archive_moves(root)
    moves = [] if accept_hygiene_baseline else archive_candidates
    canonical_documents = _canonical_documents(
        root, readme_path, {item.source for item in archive_candidates}
    )
    existing_manifest = root / ".sourcebound.yml"
    manifest_text = _manifest_text(binding_document, canonical_documents)
    if existing_manifest.exists() and existing_manifest.read_text(encoding="utf-8") != manifest_text:
        raise ConfigurationError(
            "init cannot replace an existing manifest; remove it or run inventory and add bindings"
        )
    report = scan_inventory(root)
    facts = tuple(item for item in report.items if item.kind in INCLUDED_KINDS)
    candidate_report = scan_source_claims(root)
    binding_candidates = tuple(
        _binding_candidate(candidate)
        for candidate in candidate_report.candidates[:PLAN_CANDIDATE_LIMIT]
    )
    candidate_population = sum(
        count for _status, count in candidate_report.candidate_totals
    )
    direct_protection = DirectProtectionSummary(
        directly_protected=0,
        cataloged_only_after_init=len(report.items),
        candidate_population=candidate_population,
        candidate_shown=len(binding_candidates),
        candidate_truncated=max(0, candidate_population - len(binding_candidates)),
    )
    model = build_model_record(root, facts, provider) if provider else None
    reference = _reference_document(
        root,
        binding_document,
        model.drafts if model else (),
    )
    moved = {item.source for item in moves}
    manifest = Manifest(
        path=root / ".sourcebound.yml",
        version=1,
        bindings=(_binding(binding_document),),
        projections=ProjectionConfig(
            llms_txt=LlmsTxtProjection(
                Path("llms.txt"),
                "Repository documentation",
                "Bound facts and explicitly declared canonical repository context.",
                tuple(Path(path) for path in canonical_documents if path != binding_document),
            )
        ),
    )
    assert manifest.projections is not None
    llms_config = manifest.projections.llms_txt
    assert llms_config is not None
    indexed_documents = {
        path: (
            reference.encode("utf-8")
            if path == binding_document
            else (root / path).read_bytes()
        )
        for path in canonical_documents
    }
    indexed_documents[binding_document] = reference.encode("utf-8")
    llms = render_llms_txt(
        manifest,
        title=llms_config.title,
        summary=llms_config.summary,
        documents=indexed_documents,
        output_path=root / llms_config.output,
    )
    writes = [
        item for item in (
            _planned_write(
                root,
                binding_document,
                reference,
                "bind detected repository surfaces",
            ),
            _planned_write(root, ".sourcebound.yml", manifest_text, "declare the generated binding"),
            _planned_write(root, "llms.txt", llms, "index the source-bound documentation"),
        ) if item is not None
    ]
    purpose_gaps: list[str] = []
    for path in list_documents(root):
        relative = path.relative_to(root).as_posix()
        if relative == binding_document or relative in moved:
            continue
        current = path.read_text(encoding="utf-8")
        if REGISTER_PROFILE not in current:
            continue
        profile = classify_document(path.relative_to(root), current)
        if not profile.applies("purpose-contract"):
            continue
        updated = ensure_purpose_contract(current, fallback=False)
        if "<!-- sourcebound:purpose -->" not in updated:
            purpose_gaps.append(
                f"purpose contract needs authored judgment: {relative}"
            )
            continue
        planned = _planned_write(
            root,
            relative,
            updated,
            "mark the document-level purpose contract",
        )
        if planned is not None:
            writes.append(planned)
    planned_content = {write.path: write.content for write in writes}
    indexed_documents = {
        path: (
            planned_content[path]
            if path in planned_content
            else (root / path).read_text(encoding="utf-8")
        ).encode("utf-8")
        for path in canonical_documents
    }
    indexed_documents[binding_document] = (
        planned_content.get(binding_document, reference).encode("utf-8")
    )
    final_llms = render_llms_txt(
        manifest,
        title=llms_config.title,
        summary=llms_config.summary,
        documents=indexed_documents,
        output_path=root / llms_config.output,
    )
    writes = [write for write in writes if write.path != "llms.txt"]
    llms_write = _planned_write(root, "llms.txt", final_llms, "index the canonical documentation")
    if llms_write is not None:
        writes.append(llms_write)
    supported = {"Python", "TypeScript", "JavaScript"}
    gaps = tuple(
        f"language adapter missing: {language}"
        for language in report.languages
        if language not in supported
    )
    if not facts and not report.languages:
        gaps += (
            "no supported source facts detected; use a complete source checkout or add a binding manually",
        )
    if not accept_hygiene_baseline:
        gaps += tuple(purpose_gaps)
    introduced_secret = False
    for item in writes:
        target = root / item.path
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        before_rules = set(redact_secrets(before)[1])
        after_rules = set(redact_secrets(item.content)[1])
        if after_rules - before_rules:
            introduced_secret = True
            break
    if introduced_secret:
        gaps += ("secret detected in generated documentation",)
    payload = json.dumps({
        "facts": [item.id + ":" + item.digest for item in facts],
        "writes": [(item.path, hashlib.sha256(item.content.encode()).hexdigest()) for item in writes],
        "moves": [(item.source, item.path) for item in moves],
        "gaps": gaps,
        "model": model.as_dict() if model else None,
        "direct_protection": direct_protection.as_dict(),
        "binding_candidates": [candidate.as_dict() for candidate in binding_candidates],
        "accept_hygiene_baseline": accept_hygiene_baseline,
        "canonical_documents": canonical_documents,
    }, sort_keys=True, separators=(",", ":"))
    return BootstrapPlan(
        facts,
        tuple(writes),
        tuple(moves),
        gaps,
        model,
        hashlib.sha256(payload.encode()).hexdigest(),
        canonical_documents,
        accept_hygiene_baseline,
        direct_protection,
        binding_candidates,
    )


def apply_bootstrap_plan(root: Path, plan: BootstrapPlan) -> None:
    root = root.resolve()
    if plan.gaps:
        raise ConfigurationError("cannot initialize unsupported surfaces: " + "; ".join(plan.gaps))
    originals = {
        write.path: (root / write.path).read_bytes() if (root / write.path).exists() else None
        for write in plan.writes
    }
    parent_existed = {
        (root / write.path).parent: (root / write.path).parent.exists()
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
        results = evaluate(root, root / ".sourcebound.yml")
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
        manifest = load_manifest(root / ".sourcebound.yml")
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
        for parent, existed in sorted(
            parent_existed.items(),
            key=lambda item: len(item[0].parts),
            reverse=True,
        ):
            if not existed:
                try:
                    parent.rmdir()
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
