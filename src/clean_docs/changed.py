from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from clean_docs.engine import evaluate
from clean_docs.errors import ConfigurationError, ExtractionError
from clean_docs.inventory import InventoryItem, scan_inventory
from clean_docs.snapshot import RepositorySnapshot


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
    changed_files: tuple[str, ...]
    required: tuple[ChangedFinding, ...]
    gaps: tuple[ChangedFinding, ...]
    ignored: tuple[ChangedFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.required and not self.gaps

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "clean-docs.changed.v1",
            "ok": self.ok,
            "base": self.base,
            "head": self.head,
            "changed_files": list(self.changed_files),
            "required": [asdict(item) for item in self.required],
            "gaps": [asdict(item) for item in self.gaps],
            "ignored": [asdict(item) for item in self.ignored],
        }


def _finding_id(rule: str, doc: str, source: str, locator: str) -> str:
    value = json.dumps([rule, doc, source, locator], separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


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


def _inventory(root: Path, ref: str) -> tuple[InventoryItem, ...]:
    with RepositorySnapshot(root, ref).materialized_root() as snapshot:
        return scan_inventory(snapshot).items


def check_changed(
    root: Path,
    manifest_path: Path,
    *,
    base: str,
    head: str,
) -> ChangedReport:
    root = root.resolve()
    if not base or not head:
        raise ConfigurationError("check --changed requires --base and --head")
    base_sha = RepositorySnapshot(root, base).label
    head_sha = RepositorySnapshot(root, head).label
    changed_files = tuple(sorted(
        line for line in _git(root, "diff", "--name-only", base_sha, head_sha).splitlines()
        if line
    ))
    base_items = {item.id: item for item in _inventory(root, base_sha)}
    head_items = {item.id: item for item in _inventory(root, head_sha)}

    required: list[ChangedFinding] = []
    for result in evaluate(root, manifest_path, ref=head_sha):
        if not result.changed:
            continue
        rule = "binding-drift"
        required.append(ChangedFinding(
            _finding_id(rule, result.doc, result.provenance.path, result.provenance.locator),
            rule,
            result.doc,
            result.provenance.path,
            result.provenance.locator,
            f"binding {result.binding_id} changed behind {result.doc}",
            f"clean-docs drive --binding {result.binding_id}",
        ))

    gaps: list[ChangedFinding] = []
    ignored: list[ChangedFinding] = []
    for identifier in sorted(set(head_items) - set(base_items)):
        item = head_items[identifier]
        rule = "new-public-surface"
        finding = ChangedFinding(
            _finding_id(rule, "", item.source, item.locator),
            rule,
            "",
            item.source,
            item.locator,
            f"new {item.kind} {item.name!r} has coverage state {item.coverage}",
            "add a source binding or a specific .clean-docs-ignore.yml record",
        )
        if item.coverage == "ignored":
            ignored.append(finding)
        elif item.coverage != "bound":
            gaps.append(finding)
    return ChangedReport(
        base_sha,
        head_sha,
        changed_files,
        tuple(sorted(required, key=lambda item: item.id)),
        tuple(sorted(gaps, key=lambda item: item.id)),
        tuple(sorted(ignored, key=lambda item: item.id)),
    )


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
                    "name": "clean-docs",
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
