"""Build deterministic release facts from normalized evidence at two git refs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError
from clean_docs.inventory import InventoryItem, scan_inventory
from clean_docs.policy import check_prose
from clean_docs.plugins import discover_plugin_items, merge_plugin_inventory
from clean_docs.manifest import load_manifest
from clean_docs.snapshot import RepositorySnapshot
from clean_docs.standard import load_default_pack


DELTA_KINDS = ("added", "removed", "changed")


@dataclass(frozen=True)
class EvidenceDelta:
    id: str
    change: str
    kind: str
    name: str
    source: str
    locator: str
    adapter: str
    before_sha256: str | None
    after_sha256: str | None


@dataclass(frozen=True)
class ReleaseReport:
    from_ref: str
    to_ref: str
    deltas: tuple[EvidenceDelta, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "sourcebound.release-delta.v1",
            "from": self.from_ref,
            "to": self.to_ref,
            "deltas": [asdict(delta) for delta in self.deltas],
            "counts": {
                change: sum(delta.change == change for delta in self.deltas)
                for change in DELTA_KINDS
            },
        }


@dataclass(frozen=True)
class NarrativeDraft:
    delta_id: str
    text: str
    citation: str


@dataclass(frozen=True)
class NarrativeResult:
    drafts: tuple[NarrativeDraft, ...]
    findings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "drafts": [asdict(draft) for draft in self.drafts],
            "findings": list(self.findings),
        }


def _items(root: Path, ref: str) -> tuple[str, dict[str, InventoryItem]]:
    snapshot = RepositorySnapshot(root, ref)
    label = snapshot.label
    with snapshot.materialized_root() as materialized:
        items = list(scan_inventory(materialized).items)
        manifest_path = materialized / ".sourcebound.yml"
        plugins = load_manifest(manifest_path).plugins if manifest_path.is_file() else ()
    merged = merge_plugin_inventory(
        tuple(items), discover_plugin_items(snapshot, plugins)
    )
    return label, {item.id: item for item in merged}


def _delta(
    identifier: str,
    change: str,
    before: InventoryItem | None,
    after: InventoryItem | None,
) -> EvidenceDelta:
    item = after or before
    if item is None:  # pragma: no cover - protected by the caller
        raise AssertionError("a release delta needs evidence")
    return EvidenceDelta(
        identifier,
        change,
        item.kind,
        item.name,
        item.source,
        item.locator,
        item.adapter,
        before.digest if before is not None else None,
        after.digest if after is not None else None,
    )


def build_release_report(root: Path, from_ref: str, to_ref: str) -> ReleaseReport:
    if not from_ref or not to_ref:
        raise ConfigurationError("release requires --from and --to refs")
    root = root.resolve()
    from_label, before = _items(root, from_ref)
    to_label, after = _items(root, to_ref)
    deltas: list[EvidenceDelta] = []
    for identifier in sorted(set(before) | set(after)):
        old = before.get(identifier)
        new = after.get(identifier)
        if old is None:
            deltas.append(_delta(identifier, "added", None, new))
        elif new is None:
            deltas.append(_delta(identifier, "removed", old, None))
        elif old != new:
            deltas.append(_delta(identifier, "changed", old, new))
    return ReleaseReport(from_label, to_label, tuple(deltas))


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    return value


def validate_release_narrative(report: ReleaseReport, response: str) -> NarrativeResult:
    try:
        raw = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"release narrative is not valid JSON: {exc}") from exc
    root = _mapping(raw, "release narrative")
    if set(root) != {"schema", "drafts"} or root.get("schema") != "sourcebound.release-narrative.v1":
        raise ConfigurationError(
            "release narrative must contain schema sourcebound.release-narrative.v1 and drafts"
        )
    if not isinstance(root["drafts"], list):
        raise ConfigurationError("release narrative drafts must be a list")
    expected = {delta.id: delta for delta in report.deltas}
    seen: set[str] = set()
    accepted: list[NarrativeDraft] = []
    findings: list[str] = []
    for index, candidate in enumerate(root["drafts"]):
        draft = _mapping(candidate, f"release narrative draft {index}")
        required = {"delta_id", "change", "kind", "name", "citation", "text"}
        if set(draft) != required:
            raise ConfigurationError(
                f"release narrative draft {index} must contain exactly: "
                + ", ".join(sorted(required))
            )
        delta_id = draft["delta_id"]
        if not isinstance(delta_id, str) or delta_id not in expected:
            findings.append(f"draft {index} names an unknown delta")
            continue
        if delta_id in seen:
            findings.append(f"delta {delta_id} has duplicate drafts")
            continue
        seen.add(delta_id)
        delta = expected[delta_id]
        mirrors = {
            "change": delta.change,
            "kind": delta.kind,
            "name": delta.name,
            "citation": f"{delta.source}#{delta.locator}",
        }
        mismatched = [key for key, value in mirrors.items() if draft[key] != value]
        text = draft["text"]
        if not isinstance(text, str) or not text.strip() or len(text) > 500:
            findings.append(f"delta {delta_id} has invalid narrative text")
            continue
        if mismatched:
            findings.append(
                f"delta {delta_id} contradicts deterministic fields: {', '.join(mismatched)}"
            )
            continue
        policy = check_prose("<release-narrative>", text, load_default_pack())
        if policy:
            findings.extend(
                f"delta {delta_id} violates {finding.rule}: {finding.detail}"
                for finding in policy
            )
            continue
        accepted.append(NarrativeDraft(delta_id, text.strip(), mirrors["citation"]))
    for delta_id in sorted(set(expected) - seen):
        findings.append(f"delta {delta_id} is omitted from the narrative")
    if findings:
        accepted = []
    return NarrativeResult(tuple(accepted), tuple(findings))


def render_release_markdown(
    report: ReleaseReport, narrative: NarrativeResult | None = None
) -> str:
    lines = [
        "# Release facts",
        "",
        f"Evidence compared from `{report.from_ref}` to `{report.to_ref}`.",
    ]
    for change in DELTA_KINDS:
        lines.extend(("", f"## {change.title()}"))
        selected = [delta for delta in report.deltas if delta.change == change]
        if not selected:
            lines.extend(("", "None."))
            continue
        lines.append("")
        for delta in selected:
            digest = delta.after_sha256 or delta.before_sha256
            lines.append(
                f"- `{delta.kind}` `{delta.name}` at "
                f"[{delta.source}]({delta.source}) locator `{delta.locator}` via "
                f"`{delta.adapter}`; evidence sha256 `{digest}`."
            )
    if narrative is not None:
        lines.extend(("", "## Narrative draft", ""))
        if narrative.ok:
            for draft in narrative.drafts:
                lines.append(f"- {draft.text} (`{draft.citation}`)")
        else:
            lines.append("Withheld because the draft did not preserve every release fact.")
            lines.extend(f"- {finding}" for finding in narrative.findings)
    return "\n".join(lines) + "\n"
