"""Build one local outcome receipt from deterministic repository checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clean_docs import __version__
from clean_docs.audit import AuditReport, audit
from clean_docs.changed import ChangedReport, check_changed
from clean_docs.claims import SourceClaimReport, scan_source_claims
from clean_docs.engine import evaluate
from clean_docs.errors import ConfigurationError
from clean_docs.execution import ExecutionPolicy
from clean_docs.manifest import load_manifest
from clean_docs.inventory import InventoryReport, scan_inventory
from clean_docs.models import BindingResult, Manifest
from clean_docs.projections import evaluate_projections
from clean_docs.snapshot import RepositorySnapshot


@dataclass(frozen=True)
class RepositoryEvidence:
    manifest: Manifest
    audit: AuditReport
    inventory: InventoryReport
    bindings: tuple[BindingResult, ...]
    projections: tuple[BindingResult, ...]
    source_claims: SourceClaimReport | None
    changed: ChangedReport | None


@dataclass(frozen=True)
class OutcomeReceipt:
    ref: str
    documents: int
    archived_documents: int
    hygiene_findings: int
    baselined_hygiene_findings: int
    bindings: int
    current_bindings: int
    drifted_bindings: int
    skipped_bindings: int
    regions: int
    command_pins: int
    symbols: int
    projections: int
    current_projections: int
    stale_projections: int
    inventory_items: int
    covered_inventory_items: int
    cataloged_inventory_items: int
    ignored_inventory_items: int
    standard_gaps: int
    source_claims: int
    current_source_claims: int
    drifted_source_claims: int
    missing_source_claims: int
    execution_mode: str = ExecutionPolicy.TRUSTED.value
    manifest_deprecations: tuple[str, ...] = ()
    changed: ChangedReport | None = None

    @property
    def ok(self) -> bool:
        return (
            self.hygiene_findings == 0
            and self.drifted_bindings == 0
            and self.skipped_bindings == 0
            and self.stale_projections == 0
            and self.drifted_source_claims == 0
            and self.missing_source_claims == 0
            and (self.changed is None or self.changed.ok)
        )

    def as_dict(self) -> dict[str, object]:
        changed = None
        if self.changed is not None:
            changed = {
                "base": self.changed.base,
                "head": self.changed.head,
                "required": len(self.changed.required),
                "coverage_gaps": len(self.changed.gaps),
                "reasoned_ignores": len(self.changed.ignored),
                "ok": self.changed.ok,
            }
        return {
            "schema": "clean-docs.outcome.v2",
            "version": __version__,
            "ref": self.ref,
            "ok": self.ok,
            "assurance": {
                "scope": "configured-contract",
                "region_bytes_checked": self.regions > 0,
                "command_pin_output_checked": self.command_pins > 0,
                "command_pin_prose_checked": False,
                "symbol_existence_checked": self.symbols > 0,
                "accepted_source_claim_prose_checked": self.source_claims > 0,
                "cataloged_surfaces_check_prose": False,
                "judgment_prose_certified": False,
            },
            "outcomes": {
                "protected_baseline_current": (
                    self.ok and self.changed is None and self.standard_gaps == 0
                ),
                "coverage_complete": self.standard_gaps == 0,
                "direct_coverage_complete": (
                    self.standard_gaps == 0 and self.cataloged_inventory_items == 0
                ),
                "drift_caught_before_merge": (
                    0
                    if self.changed is None
                    else len(self.changed.required) + len(self.changed.gaps)
                ),
            },
            "documentation": {
                "active": self.documents,
                "archived": self.archived_documents,
                "hygiene_findings": self.hygiene_findings,
                "baselined_hygiene_findings": self.baselined_hygiene_findings,
            },
            "coverage": {
                "total": self.inventory_items,
                "bound": self.covered_inventory_items,
                "cataloged": self.cataloged_inventory_items,
                "ignored": self.ignored_inventory_items,
                "standard_gaps": self.standard_gaps,
            },
            "bindings": {
                "total": self.bindings,
                "current": self.current_bindings,
                "drifted": self.drifted_bindings,
                "skipped": self.skipped_bindings,
                "regions": self.regions,
                "command_pins": self.command_pins,
                "symbols": self.symbols,
            },
            "projections": {
                "total": self.projections,
                "current": self.current_projections,
                "stale": self.stale_projections,
            },
            "source_claims": {
                "total": self.source_claims,
                "current": self.current_source_claims,
                "drifted": self.drifted_source_claims,
                "missing": self.missing_source_claims,
            },
            "changed": changed,
            "execution": {
                "mode": self.execution_mode,
                "declared_processes": (
                    "skipped"
                    if self.execution_mode == ExecutionPolicy.STATIC_ONLY.value
                    else "permitted-by-manifest"
                ),
                "network_isolation": "not-provided",
                "network_observation": "not-instrumented",
            },
            "deprecations": list(self.manifest_deprecations),
        }


def build_outcome_receipt(
    root: Path,
    manifest_path: Path,
    *,
    base: str | None = None,
    head: str | None = None,
    project: Path = Path("."),
    execution_policy: ExecutionPolicy = ExecutionPolicy.TRUSTED,
    use_cache: bool = True,
) -> OutcomeReceipt:
    evidence = collect_repository_evidence(
        root,
        manifest_path,
        base=base,
        head=head,
        project=project,
        execution_policy=execution_policy,
        use_cache=use_cache,
    )
    root = root.resolve()
    inventory = evidence.inventory
    audit_report = evidence.audit
    bindings = evidence.bindings
    projections = evidence.projections
    source_claim_report = evidence.source_claims
    changed = evidence.changed
    manifest = evidence.manifest
    covered_items = sum(item.coverage == "bound" for item in inventory.items)
    cataloged_items = sum(item.coverage == "cataloged" for item in inventory.items)
    ignored_items = sum(item.coverage == "ignored" for item in inventory.items)
    standard_gaps = sum(item.coverage == "standard-gap" for item in inventory.items)
    return OutcomeReceipt(
        RepositorySnapshot(root).label,
        len(audit_report.documents),
        len(audit_report.ignored_documents),
        len(audit_report.findings) + len(audit_report.stale_baseline),
        len(audit_report.baselined_findings),
        len(bindings),
        sum(not item.changed for item in bindings),
        sum(
            item.changed and item.state != "skipped-untrusted-execution"
            for item in bindings
        ),
        sum(item.state == "skipped-untrusted-execution" for item in bindings),
        sum(item.binding_type == "region" for item in bindings),
        sum(
            item.binding_type == "command-pin"
            and item.state != "skipped-untrusted-execution"
            for item in bindings
        ),
        sum(item.binding_type == "symbol" for item in bindings),
        len(projections),
        sum(not item.changed for item in projections),
        sum(item.changed for item in projections),
        len(inventory.items),
        covered_items,
        cataloged_items,
        ignored_items,
        standard_gaps,
        0 if source_claim_report is None else len(source_claim_report.results),
        0
        if source_claim_report is None
        else sum(item.status == "current" for item in source_claim_report.results),
        0
        if source_claim_report is None
        else sum(item.status == "drift" for item in source_claim_report.results),
        0 if source_claim_report is None else len(source_claim_report.missing),
        execution_policy.value,
        manifest.deprecations,
        changed,
    )


def collect_repository_evidence(
    root: Path,
    manifest_path: Path,
    *,
    base: str | None = None,
    head: str | None = None,
    project: Path = Path("."),
    execution_policy: ExecutionPolicy = ExecutionPolicy.TRUSTED,
    use_cache: bool = True,
) -> RepositoryEvidence:
    if (base is None) != (head is None):
        raise ConfigurationError("verify requires both --base and --head")
    root = root.resolve()
    manifest = load_manifest(manifest_path)
    audit_report = audit(root)
    inventory = scan_inventory(root)
    bindings = tuple(evaluate(root, manifest_path, execution_policy=execution_policy))
    projections = (
        tuple(evaluate_projections(root, manifest))
        if manifest.projections is not None
        else ()
    )
    source_claim_report = (
        scan_source_claims(
            root,
            manifest.source_claim_checks,
            discover=False,
        )
        if manifest.source_claim_checks
        else None
    )
    changed = None
    if base is not None and head is not None:
        changed = check_changed(
            root,
            manifest_path,
            base=base,
            head=head,
            project=project,
            execution_policy=execution_policy,
            use_cache=use_cache,
        )
    return RepositoryEvidence(
        manifest,
        audit_report,
        inventory,
        bindings,
        projections,
        source_claim_report,
        changed,
    )
