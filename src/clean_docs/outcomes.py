"""Build one local outcome receipt from deterministic repository checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clean_docs import __version__
from clean_docs.audit import audit
from clean_docs.changed import ChangedReport, check_changed
from clean_docs.engine import evaluate
from clean_docs.errors import ConfigurationError
from clean_docs.manifest import load_manifest
from clean_docs.projections import evaluate_projections
from clean_docs.snapshot import RepositorySnapshot


@dataclass(frozen=True)
class OutcomeReceipt:
    ref: str
    documents: int
    archived_documents: int
    hygiene_findings: int
    bindings: int
    current_bindings: int
    drifted_bindings: int
    projections: int
    current_projections: int
    stale_projections: int
    changed: ChangedReport | None = None

    @property
    def ok(self) -> bool:
        return (
            self.hygiene_findings == 0
            and self.drifted_bindings == 0
            and self.stale_projections == 0
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
            "schema": "clean-docs.outcome.v1",
            "version": __version__,
            "ref": self.ref,
            "ok": self.ok,
            "outcomes": {
                "protected_baseline_current": self.ok and self.changed is None,
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
            },
            "bindings": {
                "total": self.bindings,
                "current": self.current_bindings,
                "drifted": self.drifted_bindings,
            },
            "projections": {
                "total": self.projections,
                "current": self.current_projections,
                "stale": self.stale_projections,
            },
            "changed": changed,
            "network_requests": 0,
        }


def build_outcome_receipt(
    root: Path,
    manifest_path: Path,
    *,
    base: str | None = None,
    head: str | None = None,
    project: Path = Path("."),
) -> OutcomeReceipt:
    if (base is None) != (head is None):
        raise ConfigurationError("verify requires both --base and --head")
    root = root.resolve()
    manifest = load_manifest(manifest_path)
    audit_report = audit(root)
    bindings = evaluate(root, manifest_path)
    projections = (
        evaluate_projections(root, manifest) if manifest.projections is not None else []
    )
    changed = None
    if base is not None and head is not None:
        changed = check_changed(
            root,
            manifest_path,
            base=base,
            head=head,
            project=project,
        )
    return OutcomeReceipt(
        RepositorySnapshot(root).label,
        len(audit_report.documents),
        len(audit_report.ignored_documents),
        len(audit_report.findings),
        len(bindings),
        sum(not item.changed for item in bindings),
        sum(item.changed for item in bindings),
        len(projections),
        sum(not item.changed for item in projections),
        sum(item.changed for item in projections),
        changed,
    )
