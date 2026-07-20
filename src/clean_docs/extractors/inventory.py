from __future__ import annotations

import hashlib
import json
from pathlib import Path

from clean_docs.inventory import InventoryItem, scan_inventory
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


def _inventory_rows_from_items(
    items: tuple[InventoryItem, ...],
) -> list[dict[str, str]]:
    rows = [
        {
            "kind": item.kind,
            "name": item.name,
            "source": item.source,
            "locator": item.locator,
            "adapter": item.adapter,
            "digest": item.digest,
        }
        for item in items
        if item.kind in INCLUDED_KINDS and not item.adapter.startswith("plugin:")
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


def _inventory_rows(root: Path) -> list[dict[str, str]]:
    return _inventory_rows_from_items(scan_inventory(root).items)


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


def _extract_repository_overview(
    snapshot: RepositorySnapshot,
    *,
    include_item_digests: bool,
    extractor: str,
    inventory_items: tuple[InventoryItem, ...] | None = None,
) -> EvidenceValue:
    if inventory_items is None:
        with snapshot.materialized_root() as root:
            inventory_rows = _inventory_rows(root)
    else:
        inventory_rows = _inventory_rows_from_items(inventory_items)
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
    receipt_rows = (
        inventory_rows
        if include_item_digests
        else [
            {
                "kind": item["kind"],
                "name": item["name"],
                "source": item["source"],
                "locator": item["locator"],
                "adapter": item["adapter"],
            }
            for item in inventory_rows
        ]
    )
    normalized = json.dumps(receipt_rows, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    lines.extend(("", f"<!-- sourcebound:inventory-sha256 {digest} -->"))
    return EvidenceValue(
        kind="markdown",
        value="\n".join(lines),
        provenance=Provenance(
            ref=snapshot.label,
            path=".",
            locator="public-surface-overview",
            extractor=extractor,
            digest=digest,
        ),
    )


def extract_repository_overview(
    snapshot: RepositorySnapshot,
    binding: RegionBinding,
    *,
    inventory_items: tuple[InventoryItem, ...] | None = None,
) -> EvidenceValue:
    return _extract_repository_overview(
        snapshot,
        include_item_digests=False,
        extractor="repository-overview@2",
        inventory_items=inventory_items,
    )


def _extract_repository_overview_legacy(
    snapshot: RepositorySnapshot,
    binding: RegionBinding,
    *,
    inventory_items: tuple[InventoryItem, ...] | None = None,
) -> EvidenceValue:
    return _extract_repository_overview(
        snapshot,
        include_item_digests=True,
        extractor="repository-overview@1",
        inventory_items=inventory_items,
    )
