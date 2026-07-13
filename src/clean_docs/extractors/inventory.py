from __future__ import annotations

import hashlib
import json

from clean_docs.inventory import scan_inventory
from clean_docs.models import EvidenceValue, Provenance, RegionBinding
from clean_docs.snapshot import RepositorySnapshot


INCLUDED_KINDS = {
    "api-endpoint",
    "api-symbol",
    "cli-command",
    "cli-option",
    "mcp-tool",
    "package",
    "package-script",
    "schema",
    "test-runner",
    "test-suite",
}


def extract_repository_inventory(
    snapshot: RepositorySnapshot, binding: RegionBinding
) -> EvidenceValue:
    with snapshot.materialized_root() as root:
        report = scan_inventory(root)
    rows = [
        {
            "kind": item.kind,
            "name": item.name,
            "source": item.source,
            "locator": item.locator,
        }
        for item in report.items
        if item.kind in INCLUDED_KINDS
    ]
    normalized = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return EvidenceValue(
        kind="table",
        value=rows,
        provenance=Provenance(
            ref=snapshot.label,
            path=".",
            locator="public-surface",
            extractor="repository-inventory@1",
            digest=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        ),
    )
