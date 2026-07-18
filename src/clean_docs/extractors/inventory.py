from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
    "runtime-constraint",
    "schema",
    "test-runner",
    "test-suite",
}


def _inventory_rows(root: Path) -> list[dict[str, str]]:
    report = scan_inventory(root)
    rows = [
        {
            "kind": item.kind,
            "name": item.name,
            "source": item.source,
            "locator": item.locator,
            "adapter": item.adapter,
            "digest": item.digest,
        }
        for item in report.items
        if item.kind in INCLUDED_KINDS
    ]
    return sorted(
        rows,
        key=lambda item: (
            item["kind"],
            item["name"],
            item["source"],
            item["locator"],
            item["adapter"],
            item["digest"],
        ),
    )


def extract_repository_inventory(
    snapshot: RepositorySnapshot, binding: RegionBinding
) -> EvidenceValue:
    with snapshot.materialized_root() as root:
        inventory_rows = _inventory_rows(root)
    rows = [
        {
            "kind": item["kind"],
            "name": item["name"],
            "source": item["source"],
            "locator": item["locator"],
        }
        for item in inventory_rows
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


def _inline(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("`", "'")
        .replace("\n", " ")
    )


def extract_repository_overview(
    snapshot: RepositorySnapshot, binding: RegionBinding
) -> EvidenceValue:
    with snapshot.materialized_root() as root:
        inventory_rows = _inventory_rows(root)
    by_kind: dict[str, list[str]] = {}
    for item in inventory_rows:
        by_kind.setdefault(item["kind"], []).append(item["name"])
    lines = [
        "| surface | discovered | examples |",
        "| --- | ---: | --- |",
    ]
    for kind in sorted(by_kind):
        names = sorted(set(by_kind[kind]))
        examples = ", ".join(f"`{_inline(name)}`" for name in names[:3])
        if len(by_kind[kind]) > 3:
            examples += f", and {len(by_kind[kind]) - 3} more"
        lines.append(f"| {_inline(kind)} | {len(by_kind[kind])} | {examples} |")
    rendered_rows = [
        {
            "kind": item["kind"],
            "name": item["name"],
            "source": item["source"],
            "locator": item["locator"],
            "adapter": item["adapter"],
        }
        for item in inventory_rows
    ]
    normalized = json.dumps(rendered_rows, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    lines.extend(("", f"<!-- clean-docs:inventory-sha256 {digest} -->"))
    return EvidenceValue(
        kind="markdown",
        value="\n".join(lines),
        provenance=Provenance(
            ref=snapshot.label,
            path=".",
            locator="public-surface-overview",
            extractor="repository-overview@1",
            digest=digest,
        ),
    )
