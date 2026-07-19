"""Compose one coverage-stating pull-request verdict from deterministic evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from clean_docs import __version__
from clean_docs.errors import ConfigurationError
from clean_docs.execution import ExecutionPolicy
from clean_docs.impact import ImpactPlan, build_impact_plan
from clean_docs.models import ClaimBinding
from clean_docs.outcomes import RepositoryEvidence, collect_repository_evidence
from clean_docs.sensitivity import RECEIPT_SCHEMA, load_json_object


VERDICT_SCHEMA = "clean-docs.pr-verdict.v1"
NON_CLAIMS = (
    "unbound prose is not certified",
    "judgment prose is not certified",
    "mutation sensitivity is not semantic correctness",
    "review-contract co-change is not semantic correctness",
    "catalog coverage is not prose coverage",
    "gate readiness is not observation completeness",
)


@dataclass(frozen=True)
class VerdictFinding:
    id: str
    rule: str
    level: str
    path: str
    message: str
    repair: str


@dataclass(frozen=True)
class MutationReceiptSummary:
    sha256: str
    state: str
    relationship_id: str
    plan_sha256: str | None
    semantic_relationship_authorized: bool


@dataclass(frozen=True)
class PullRequestVerdict:
    state: str
    requested_base: str
    merge_base: str
    head: str
    manifest: str
    manifest_sha256: str
    impact: ImpactPlan
    evidence: RepositoryEvidence
    findings: tuple[VerdictFinding, ...]
    mutation_receipts: tuple[MutationReceiptSummary, ...]

    @property
    def ok(self) -> bool:
        return self.state == "ready"

    @property
    def digest(self) -> str:
        return _digest(self._payload())

    def _payload(self) -> dict[str, object]:
        bindings = self.evidence.bindings
        projections = self.evidence.projections
        source_claims = self.evidence.source_claims
        inventory = self.evidence.inventory
        changed = self.evidence.changed
        assert changed is not None
        skipped_bindings = {
            result.binding_id
            for result in bindings
            if result.state == "skipped-untrusted-execution"
        }
        configured_bindings = {
            binding.id: binding for binding in self.evidence.manifest.bindings
        }
        skipped_commands = sorted(
            binding.command
            for binding_id in skipped_bindings
            if isinstance(
                (binding := configured_bindings.get(binding_id)),
                ClaimBinding,
            )
        )
        counts = {
            state: sum(item.coverage == state for item in inventory.items)
            for state in ("bound", "cataloged", "ignored", "standard-gap")
        }
        mechanism_states = {
            mechanism: {
                "total": sum(result.binding_type == mechanism for result in bindings),
                "current": sum(
                    result.binding_type == mechanism and not result.changed
                    for result in bindings
                ),
                "drifted": sum(
                    result.binding_type == mechanism
                    and result.changed
                    and result.state != "skipped-untrusted-execution"
                    for result in bindings
                ),
                "skipped": sum(
                    result.binding_type == mechanism
                    and result.state == "skipped-untrusted-execution"
                    for result in bindings
                ),
            }
            for mechanism in ("region", "command-pin", "symbol", "plugin")
        }
        review_contract_states = {
            state: sum(result.state == state for result in self.impact.review_contracts)
            for state in (
                "unaffected",
                "review-recommended",
                "cochanged",
                "unknown",
            )
        }
        observation_state = (
            "unknown"
            if review_contract_states["unknown"]
            else "review-recommended"
            if review_contract_states["review-recommended"]
            else "clear"
        )
        return {
            "schema": VERDICT_SCHEMA,
            "producer": {"name": "clean-docs", "version": __version__},
            "state": self.state,
            "ready": self.ok,
            "gate": {
                "state": self.state,
                "ready": self.ok,
            },
            "observations": {
                "state": observation_state,
                "complete": review_contract_states["unknown"] == 0,
                "total": len(self.impact.review_contracts),
                "counts": review_contract_states,
            },
            "scope": "required-gates-and-changed-surface",
            "read_only": True,
            "refs": {
                "requested_base": self.requested_base,
                "merge_base": self.merge_base,
                "head": self.head,
            },
            "inputs": {
                "manifest": self.manifest,
                "manifest_sha256": self.manifest_sha256,
                "impact_plan_sha256": self.impact.digest,
            },
            "execution": {
                "mode": ExecutionPolicy.STATIC_ONLY.value,
                "repository_commands": "skipped",
                "plugins": "skipped",
                "skipped_binding_ids": sorted(skipped_bindings),
                "skipped_command_ids": skipped_commands,
                "skipped_plugin_ids": sorted(
                    plugin.id for plugin in self.evidence.manifest.plugins
                ),
            },
            "audit": {
                "ok": self.evidence.audit.ok,
                "active_documents": len(self.evidence.audit.documents),
                "findings": len(self.evidence.audit.findings),
                "baselined": len(self.evidence.audit.baselined_findings),
                "stale_baseline": len(self.evidence.audit.stale_baseline),
                "baseline_current": not self.evidence.audit.stale_baseline,
                "unsupported_documents": list(
                    self.evidence.audit.unsupported_documents
                ),
            },
            "mechanisms": {
                **mechanism_states,
                "source-claim": {
                    "total": (
                        0 if source_claims is None else len(source_claims.results)
                    ),
                    "current": (
                        0
                        if source_claims is None
                        else sum(
                            result.status == "current"
                            for result in source_claims.results
                        )
                    ),
                    "drifted": (
                        0
                        if source_claims is None
                        else sum(
                            result.status == "drift" for result in source_claims.results
                        )
                    ),
                    "missing": (
                        0 if source_claims is None else len(source_claims.missing)
                    ),
                },
                "projection": {
                    "total": len(projections),
                    "current": sum(not result.changed for result in projections),
                    "stale": sum(result.changed for result in projections),
                },
                "review-contract": {
                    "total": len(self.impact.review_contracts),
                    **review_contract_states,
                    "semantic_correctness_checked": False,
                },
            },
            "changed_surface": {
                "files": list(changed.changed_files),
                "required": len(changed.required),
                "gaps": len(changed.gaps),
                "ignored": len(changed.ignored),
                "unknown": len(self.impact.unknown),
                "coverage_complete": self.impact.coverage_complete,
                "impact": self.impact.impact,
                "impact_findings": {
                    "required": len(self.impact.required),
                    "recommended": len(self.impact.recommended),
                    "unrelated": len(self.impact.unrelated),
                    "unknown": len(self.impact.unknown),
                },
                "artifacts": [asdict(artifact) for artifact in self.impact.artifacts],
                "unsupported_documents": list(self.impact.unsupported_documents),
            },
            "coverage": {
                "inventory_total": len(inventory.items),
                "directly_bound": counts["bound"],
                "catalog_only": counts["cataloged"],
                "ignored": counts["ignored"],
                "unsupported_or_unknown": counts["standard-gap"],
                "unbound_prose_checked": False,
            },
            "mutation_receipts": [
                asdict(receipt) for receipt in self.mutation_receipts
            ],
            "review_contracts": [
                result.as_dict() for result in self.impact.review_contracts
            ],
            "findings": [asdict(finding) for finding in self.findings],
            "non_claims": list(NON_CLAIMS),
        }

    def as_dict(self) -> dict[str, object]:
        payload = self._payload()
        payload["digest"] = self.digest
        return payload


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _object(
    value: object,
    where: str,
    keys: frozenset[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    actual = frozenset(value)
    if actual != keys:
        raise ConfigurationError(f"{where} fields are invalid")
    return value


def _string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{where} must be a non-empty string")
    return value


def _boolean(value: object, where: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{where} must be a boolean")
    return value


def _count(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigurationError(f"{where} must be a non-negative integer")
    return value


def _strings(value: object, where: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise ConfigurationError(f"{where} must be a list of strings")
    return list(value)


def _sha256_or_none(value: object, where: str) -> str | None:
    if value is None:
        return None
    digest = _string(value, where)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ConfigurationError(f"{where} must be a lowercase SHA-256 digest")
    return digest


def _validate_count_group(
    value: object,
    where: str,
    fields: tuple[str, ...],
) -> dict[str, int]:
    data = _object(value, where, frozenset(("total", *fields)))
    counts = {
        field: _count(data[field], f"{where}.{field}") for field in ("total", *fields)
    }
    if counts["total"] != sum(counts[field] for field in fields):
        raise ConfigurationError(f"{where} counts do not sum to total")
    return counts


def _validate_locator_evidence(
    value: object,
    where: str,
) -> tuple[str, str | None, str | None]:
    data = _object(
        value,
        where,
        frozenset(
            {
                "id",
                "path",
                "extractor",
                "locator",
                "base_digest",
                "head_digest",
                "state",
            }
        ),
    )
    _string(data["id"], f"{where}.id")
    _string(data["path"], f"{where}.path")
    extractor = data["extractor"]
    if extractor not in {
        "markdown-section",
        "python-symbol",
        "structured-data",
    }:
        raise ConfigurationError(f"{where}.extractor is invalid")
    _string(data["locator"], f"{where}.locator")
    base_digest = _sha256_or_none(data["base_digest"], f"{where}.base_digest")
    head_digest = _sha256_or_none(data["head_digest"], f"{where}.head_digest")
    state = data["state"]
    if state not in {"added", "changed", "removed", "unchanged", "unknown"}:
        raise ConfigurationError(f"{where}.state is invalid")
    if state == "added" and not (base_digest is None and head_digest is not None):
        raise ConfigurationError(f"{where} added state contradicts its digests")
    if state == "removed" and not (base_digest is not None and head_digest is None):
        raise ConfigurationError(f"{where} removed state contradicts its digests")
    if state == "changed" and not (
        base_digest is not None
        and head_digest is not None
        and base_digest != head_digest
    ):
        raise ConfigurationError(f"{where} changed state contradicts its digests")
    if state == "unchanged" and not (
        base_digest is not None and base_digest == head_digest
    ):
        raise ConfigurationError(f"{where} unchanged state contradicts its digests")
    if state == "unknown" and base_digest is not None and head_digest is not None:
        raise ConfigurationError(f"{where} unknown state contradicts its digests")
    return state, base_digest, head_digest


def _validate_review_contract(
    value: object,
    where: str,
) -> str:
    data = _object(
        value,
        where,
        frozenset(
            {
                "id",
                "mode",
                "state",
                "sources",
                "targets",
                "semantic_correctness_checked",
            }
        ),
    )
    _string(data["id"], f"{where}.id")
    if data["mode"] != "observe":
        raise ConfigurationError(f"{where}.mode must be observe")
    if data["semantic_correctness_checked"] is not False:
        raise ConfigurationError(f"{where}.semantic_correctness_checked must be false")
    source_values = data["sources"]
    target_values = data["targets"]
    if not isinstance(source_values, list) or not source_values:
        raise ConfigurationError(f"{where}.sources must be a non-empty list")
    if not isinstance(target_values, list) or not target_values:
        raise ConfigurationError(f"{where}.targets must be a non-empty list")
    source_states = [
        _validate_locator_evidence(item, f"{where}.sources[{index}]")[0]
        for index, item in enumerate(source_values)
    ]
    target_results = [
        _validate_locator_evidence(item, f"{where}.targets[{index}]")
        for index, item in enumerate(target_values)
    ]
    target_states = [result[0] for result in target_results]
    target_head_digests = [result[2] for result in target_results]
    expected = (
        "unknown"
        if "unknown" in source_states + target_states
        or any(digest is None for digest in target_head_digests)
        else "unaffected"
        if not any(state in {"added", "changed", "removed"} for state in source_states)
        else "cochanged"
        if all(state in {"added", "changed"} for state in target_states)
        else "review-recommended"
    )
    state = data["state"]
    if state != expected:
        raise ConfigurationError(f"{where}.state contradicts locator evidence")
    return expected


def _derive_gate_state(
    finding_levels: Iterable[str],
    *,
    coverage_complete: bool,
    impact: str,
) -> str:
    levels = tuple(finding_levels)
    if "error" in levels:
        return "not_ready"
    if not coverage_complete or impact == "unknown" or "warning" in levels:
        return "unknown"
    return "ready"


def _validate_findings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigurationError("verdict findings must be a list")
    levels: list[str] = []
    for finding in value:
        finding_data = _object(
            finding,
            "verdict finding",
            frozenset({"id", "rule", "level", "path", "message", "repair"}),
        )
        for field in ("id", "rule", "path", "message", "repair"):
            _string(finding_data[field], f"verdict finding {field}")
        if finding_data["level"] not in {"error", "warning", "note"}:
            raise ConfigurationError("verdict finding level is invalid")
        levels.append(finding_data["level"])
    return tuple(levels)


def _validate_legacy_verdict_payload(payload: Mapping[str, object]) -> None:
    allowed = (
        frozenset({"schema", "state", "ready", "findings", "digest"}),
        frozenset({"schema", "producer", "state", "ready", "findings", "digest"}),
    )
    if frozenset(payload) not in allowed:
        raise ConfigurationError("legacy verdict fields are invalid")
    state = payload["state"]
    if state not in {"ready", "not_ready", "unknown"}:
        raise ConfigurationError("legacy verdict state is invalid")
    ready = _boolean(payload["ready"], "legacy verdict.ready")
    if ready != (state == "ready"):
        raise ConfigurationError("legacy verdict ready contradicts state")
    if "producer" in payload:
        producer = _object(
            payload["producer"],
            "legacy verdict.producer",
            frozenset({"name", "version"}),
        )
        if producer["name"] != "clean-docs":
            raise ConfigurationError("legacy verdict.producer.name must be clean-docs")
        _string(producer["version"], "legacy verdict.producer.version")
    findings = payload["findings"]
    if not isinstance(findings, list):
        raise ConfigurationError("legacy verdict findings must be a list")
    if findings:
        _validate_findings(findings)


def validate_verdict_payload(payload: Mapping[str, object]) -> None:
    """Reject a serialized verdict that cannot be the output of this schema."""
    if payload.get("schema") != VERDICT_SCHEMA:
        raise ConfigurationError(f"verdict schema must be {VERDICT_SCHEMA}")
    digest = payload.get("digest")
    if _sha256_or_none(digest, "verdict digest") is None:
        raise ConfigurationError("verdict digest is missing")
    unsigned = {key: value for key, value in payload.items() if key != "digest"}
    if _digest(unsigned) != digest:
        raise ConfigurationError("verdict digest does not match its payload")
    if "gate" not in payload:
        _validate_legacy_verdict_payload(payload)
        return

    data = _object(
        dict(payload),
        "verdict",
        frozenset(
            {
                "schema",
                "producer",
                "state",
                "ready",
                "gate",
                "observations",
                "scope",
                "read_only",
                "refs",
                "inputs",
                "execution",
                "audit",
                "mechanisms",
                "changed_surface",
                "coverage",
                "mutation_receipts",
                "review_contracts",
                "findings",
                "non_claims",
                "digest",
            }
        ),
    )
    producer = _object(
        data["producer"],
        "verdict.producer",
        frozenset({"name", "version"}),
    )
    if producer["name"] != "clean-docs":
        raise ConfigurationError("verdict.producer.name must be clean-docs")
    _string(producer["version"], "verdict.producer.version")

    states = {"ready", "not_ready", "unknown"}
    state = data["state"]
    if state not in states:
        raise ConfigurationError("verdict state is invalid")
    ready = _boolean(data["ready"], "verdict.ready")
    if ready != (state == "ready"):
        raise ConfigurationError("verdict ready contradicts state")
    gate = _object(
        data["gate"],
        "verdict.gate",
        frozenset({"state", "ready"}),
    )
    if gate["state"] not in states:
        raise ConfigurationError("verdict.gate.state is invalid")
    gate_ready = _boolean(gate["ready"], "verdict.gate.ready")
    if gate["state"] != state or gate_ready != ready:
        raise ConfigurationError("legacy verdict aliases must match gate")

    if data["scope"] != "required-gates-and-changed-surface":
        raise ConfigurationError("verdict scope is invalid")
    if data["read_only"] is not True:
        raise ConfigurationError("verdict read_only must be true")

    refs = _object(
        data["refs"],
        "verdict.refs",
        frozenset({"requested_base", "merge_base", "head"}),
    )
    for field in ("requested_base", "merge_base", "head"):
        _string(refs[field], f"verdict.refs.{field}")

    inputs = _object(
        data["inputs"],
        "verdict.inputs",
        frozenset({"manifest", "manifest_sha256", "impact_plan_sha256"}),
    )
    _string(inputs["manifest"], "verdict.inputs.manifest")
    if (
        _sha256_or_none(
            inputs["manifest_sha256"],
            "verdict.inputs.manifest_sha256",
        )
        is None
    ):
        raise ConfigurationError("verdict.inputs.manifest_sha256 is missing")
    if (
        _sha256_or_none(
            inputs["impact_plan_sha256"],
            "verdict.inputs.impact_plan_sha256",
        )
        is None
    ):
        raise ConfigurationError("verdict.inputs.impact_plan_sha256 is missing")

    execution = _object(
        data["execution"],
        "verdict.execution",
        frozenset(
            {
                "mode",
                "repository_commands",
                "plugins",
                "skipped_binding_ids",
                "skipped_command_ids",
                "skipped_plugin_ids",
            }
        ),
    )
    if execution["mode"] != ExecutionPolicy.STATIC_ONLY.value:
        raise ConfigurationError("verdict.execution.mode is invalid")
    if execution["repository_commands"] != "skipped":
        raise ConfigurationError(
            "verdict.execution.repository_commands must be skipped"
        )
    if execution["plugins"] != "skipped":
        raise ConfigurationError("verdict.execution.plugins must be skipped")
    for field in (
        "skipped_binding_ids",
        "skipped_command_ids",
        "skipped_plugin_ids",
    ):
        values = _strings(execution[field], f"verdict.execution.{field}")
        if values != sorted(set(values)):
            raise ConfigurationError(
                f"verdict.execution.{field} must be sorted and unique"
            )

    audit = _object(
        data["audit"],
        "verdict.audit",
        frozenset(
            {
                "ok",
                "active_documents",
                "findings",
                "baselined",
                "stale_baseline",
                "baseline_current",
                "unsupported_documents",
            }
        ),
    )
    audit_ok = _boolean(audit["ok"], "verdict.audit.ok")
    audit_findings = _count(audit["findings"], "verdict.audit.findings")
    stale_baseline = _count(
        audit["stale_baseline"],
        "verdict.audit.stale_baseline",
    )
    _count(audit["active_documents"], "verdict.audit.active_documents")
    _count(audit["baselined"], "verdict.audit.baselined")
    baseline_current = _boolean(
        audit["baseline_current"],
        "verdict.audit.baseline_current",
    )
    _strings(
        audit["unsupported_documents"],
        "verdict.audit.unsupported_documents",
    )
    if baseline_current != (stale_baseline == 0):
        raise ConfigurationError(
            "verdict.audit.baseline_current contradicts stale_baseline"
        )
    if audit_ok != (audit_findings == 0 and stale_baseline == 0):
        raise ConfigurationError("verdict.audit.ok contradicts audit counts")

    mechanisms = _object(
        data["mechanisms"],
        "verdict.mechanisms",
        frozenset(
            {
                "region",
                "command-pin",
                "symbol",
                "plugin",
                "source-claim",
                "projection",
                "review-contract",
            }
        ),
    )
    for mechanism in ("region", "command-pin", "symbol", "plugin"):
        _validate_count_group(
            mechanisms[mechanism],
            f"verdict.mechanisms.{mechanism}",
            ("current", "drifted", "skipped"),
        )
    source_claim = _object(
        mechanisms["source-claim"],
        "verdict.mechanisms.source-claim",
        frozenset({"total", "current", "drifted", "missing"}),
    )
    source_claim_counts = {
        field: _count(
            source_claim[field],
            f"verdict.mechanisms.source-claim.{field}",
        )
        for field in ("total", "current", "drifted", "missing")
    }
    if source_claim_counts["total"] != (
        source_claim_counts["current"] + source_claim_counts["drifted"]
    ):
        raise ConfigurationError(
            "verdict.mechanisms.source-claim counts do not sum to total"
        )
    _validate_count_group(
        mechanisms["projection"],
        "verdict.mechanisms.projection",
        ("current", "stale"),
    )

    review_mechanism = _object(
        mechanisms["review-contract"],
        "verdict.mechanisms.review-contract",
        frozenset(
            {
                "total",
                "unaffected",
                "review-recommended",
                "cochanged",
                "unknown",
                "semantic_correctness_checked",
            }
        ),
    )
    if review_mechanism["semantic_correctness_checked"] is not False:
        raise ConfigurationError(
            "verdict.mechanisms.review-contract semantic check must be false"
        )
    review_counts = {
        field: _count(
            review_mechanism[field],
            f"verdict.mechanisms.review-contract.{field}",
        )
        for field in (
            "total",
            "unaffected",
            "review-recommended",
            "cochanged",
            "unknown",
        )
    }
    if review_counts["total"] != sum(
        review_counts[field]
        for field in (
            "unaffected",
            "review-recommended",
            "cochanged",
            "unknown",
        )
    ):
        raise ConfigurationError(
            "verdict.mechanisms.review-contract counts do not sum to total"
        )

    changed = _object(
        data["changed_surface"],
        "verdict.changed_surface",
        frozenset(
            {
                "files",
                "required",
                "gaps",
                "ignored",
                "unknown",
                "coverage_complete",
                "impact",
                "impact_findings",
                "artifacts",
                "unsupported_documents",
            }
        ),
    )
    _strings(changed["files"], "verdict.changed_surface.files")
    for field in ("required", "gaps", "ignored", "unknown"):
        _count(changed[field], f"verdict.changed_surface.{field}")
    coverage_complete = _boolean(
        changed["coverage_complete"],
        "verdict.changed_surface.coverage_complete",
    )
    if changed["impact"] not in {"none", "recommended", "required", "unknown"}:
        raise ConfigurationError("verdict.changed_surface.impact is invalid")
    impact_counts_data = _object(
        changed["impact_findings"],
        "verdict.changed_surface.impact_findings",
        frozenset({"required", "recommended", "unrelated", "unknown"}),
    )
    impact_counts = {
        field: _count(
            impact_counts_data[field],
            f"verdict.changed_surface.impact_findings.{field}",
        )
        for field in ("required", "recommended", "unrelated", "unknown")
    }
    expected_impact = (
        "unknown"
        if impact_counts["unknown"]
        else "required"
        if impact_counts["required"]
        else "recommended"
        if impact_counts["recommended"]
        else "none"
    )
    if changed["impact"] != expected_impact:
        raise ConfigurationError(
            "verdict.changed_surface.impact contradicts finding counts"
        )
    if changed["unknown"] != impact_counts["unknown"]:
        raise ConfigurationError("verdict.changed_surface unknown counts disagree")
    if coverage_complete != (impact_counts["unknown"] == 0):
        raise ConfigurationError(
            "verdict.changed_surface coverage contradicts unknown count"
        )
    artifacts = changed["artifacts"]
    if not isinstance(artifacts, list):
        raise ConfigurationError("verdict.changed_surface.artifacts must be a list")
    for index, artifact_value in enumerate(artifacts):
        artifact = _object(
            artifact_value,
            f"verdict.changed_surface.artifacts[{index}]",
            frozenset(
                {
                    "path",
                    "change",
                    "base_blob",
                    "head_blob",
                    "adapter",
                    "decision",
                    "may_expose_public_surface",
                    "coverage",
                    "graph_roots",
                }
            ),
        )
        _string(artifact["path"], f"verdict artifact {index}.path")
        if artifact["change"] not in {"added", "modified", "removed"}:
            raise ConfigurationError(f"verdict artifact {index}.change is invalid")
        for field in ("base_blob", "head_blob"):
            if artifact[field] is not None:
                _string(artifact[field], f"verdict artifact {index}.{field}")
        _string(artifact["adapter"], f"verdict artifact {index}.adapter")
        _string(artifact["decision"], f"verdict artifact {index}.decision")
        _boolean(
            artifact["may_expose_public_surface"],
            f"verdict artifact {index}.may_expose_public_surface",
        )
        if artifact["coverage"] not in {
            "adapter-covered",
            "document-direct",
            "generated",
            "graph-covered",
            "unknown",
            "unrelated-covered",
        }:
            raise ConfigurationError(f"verdict artifact {index}.coverage is invalid")
        _strings(artifact["graph_roots"], f"verdict artifact {index}.graph_roots")
    _strings(
        changed["unsupported_documents"],
        "verdict.changed_surface.unsupported_documents",
    )

    coverage = _object(
        data["coverage"],
        "verdict.coverage",
        frozenset(
            {
                "inventory_total",
                "directly_bound",
                "catalog_only",
                "ignored",
                "unsupported_or_unknown",
                "unbound_prose_checked",
            }
        ),
    )
    coverage_counts = {
        field: _count(coverage[field], f"verdict.coverage.{field}")
        for field in (
            "inventory_total",
            "directly_bound",
            "catalog_only",
            "ignored",
            "unsupported_or_unknown",
        )
    }
    if coverage_counts["inventory_total"] != sum(
        coverage_counts[field]
        for field in (
            "directly_bound",
            "catalog_only",
            "ignored",
            "unsupported_or_unknown",
        )
    ):
        raise ConfigurationError("verdict coverage counts do not sum to total")
    if coverage["unbound_prose_checked"] is not False:
        raise ConfigurationError("verdict.coverage.unbound_prose_checked must be false")

    review_contracts = data["review_contracts"]
    if not isinstance(review_contracts, list):
        raise ConfigurationError("verdict.review_contracts must be a list")
    calculated_review_counts = {
        "unaffected": 0,
        "review-recommended": 0,
        "cochanged": 0,
        "unknown": 0,
    }
    for index, contract in enumerate(review_contracts):
        contract_state = _validate_review_contract(
            contract,
            f"verdict.review_contracts[{index}]",
        )
        calculated_review_counts[contract_state] += 1
    if len(review_contracts) != review_counts["total"] or any(
        calculated_review_counts[field] != review_counts[field]
        for field in calculated_review_counts
    ):
        raise ConfigurationError(
            "verdict review-contract mechanism counts disagree with evidence"
        )

    observations = _object(
        data["observations"],
        "verdict.observations",
        frozenset({"state", "complete", "total", "counts"}),
    )
    observation_counts_data = _object(
        observations["counts"],
        "verdict.observations.counts",
        frozenset(calculated_review_counts),
    )
    observation_counts = {
        field: _count(
            observation_counts_data[field],
            f"verdict.observations.counts.{field}",
        )
        for field in calculated_review_counts
    }
    observation_total = _count(
        observations["total"],
        "verdict.observations.total",
    )
    if observation_counts != calculated_review_counts or observation_total != len(
        review_contracts
    ):
        raise ConfigurationError(
            "verdict observations disagree with review-contract evidence"
        )
    expected_observation_state = (
        "unknown"
        if observation_counts["unknown"]
        else "review-recommended"
        if observation_counts["review-recommended"]
        else "clear"
    )
    if observations["state"] != expected_observation_state:
        raise ConfigurationError("verdict observation state contradicts its counts")
    observation_complete = _boolean(
        observations["complete"],
        "verdict.observations.complete",
    )
    if observation_complete != (observation_counts["unknown"] == 0):
        raise ConfigurationError(
            "verdict observation completeness contradicts unknown count"
        )

    mutation_receipts = data["mutation_receipts"]
    if not isinstance(mutation_receipts, list):
        raise ConfigurationError("verdict.mutation_receipts must be a list")
    for index, receipt_value in enumerate(mutation_receipts):
        receipt = _object(
            receipt_value,
            f"verdict.mutation_receipts[{index}]",
            frozenset(
                {
                    "sha256",
                    "state",
                    "relationship_id",
                    "plan_sha256",
                    "semantic_relationship_authorized",
                }
            ),
        )
        _sha256_or_none(
            receipt["sha256"],
            f"verdict.mutation_receipts[{index}].sha256",
        )
        if receipt["state"] not in {
            "sensitive",
            "insensitive",
            "invalid",
            "unsupported",
        }:
            raise ConfigurationError(
                f"verdict.mutation_receipts[{index}].state is invalid"
            )
        _string(
            receipt["relationship_id"],
            f"verdict.mutation_receipts[{index}].relationship_id",
        )
        plan_digest = _sha256_or_none(
            receipt["plan_sha256"],
            f"verdict.mutation_receipts[{index}].plan_sha256",
        )
        if receipt["state"] in {"sensitive", "insensitive"} and plan_digest is None:
            raise ConfigurationError(
                f"verdict.mutation_receipts[{index}] requires a plan digest"
            )
        if receipt["semantic_relationship_authorized"] is not False:
            raise ConfigurationError(
                f"verdict.mutation_receipts[{index}] cannot authorize semantics"
            )

    finding_levels = _validate_findings(data["findings"])
    expected_gate_state = _derive_gate_state(
        finding_levels,
        coverage_complete=coverage_complete,
        impact=changed["impact"],
    )
    if state != expected_gate_state:
        raise ConfigurationError(
            "verdict gate state contradicts validated evidence"
        )

    non_claims = _strings(data["non_claims"], "verdict.non_claims")
    if tuple(non_claims) != NON_CLAIMS:
        raise ConfigurationError("verdict non_claims are invalid")


def _git(root: Path, *args: str) -> bytes:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(f"cannot inspect verdict repository: {exc}") from exc
    if process.returncode != 0:
        detail = process.stderr.decode(errors="replace").strip()
        raise ConfigurationError(detail or f"git {' '.join(args)} failed")
    return process.stdout


def _finding(
    rule: str,
    level: str,
    path: str,
    message: str,
    repair: str,
) -> VerdictFinding:
    return VerdictFinding(
        _digest([rule, path, message]),
        rule,
        level,
        path,
        message,
        repair,
    )


def _mutation_summary(path: Path, head: str) -> MutationReceiptSummary:
    if path.is_symlink():
        raise ConfigurationError("mutation receipt must not be a symbolic link")
    receipt, raw = load_json_object(path, "mutation receipt")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ConfigurationError(f"mutation receipt schema must be {RECEIPT_SCHEMA}")
    repository = receipt.get("repository")
    inputs = receipt.get("inputs")
    if not isinstance(repository, dict) or repository.get("commit") != head:
        raise ConfigurationError("mutation receipt commit does not match verdict head")
    if not isinstance(inputs, dict) or not isinstance(inputs.get("relationship"), dict):
        raise ConfigurationError("mutation receipt has no relationship identity")
    relationship_id = inputs["relationship"].get("id")
    if not isinstance(relationship_id, str) or not relationship_id:
        raise ConfigurationError("mutation receipt relationship id is invalid")
    state = receipt.get("state")
    if state not in {"sensitive", "insensitive", "invalid", "unsupported"}:
        raise ConfigurationError("mutation receipt state is invalid")
    semantic = receipt.get("semantic_relationship_authorized")
    if semantic is not False:
        raise ConfigurationError(
            "mutation receipt cannot authorize a semantic relationship"
        )
    mutation = receipt.get("mutation")
    plan_sha256 = None
    if mutation is not None:
        if not isinstance(mutation, dict):
            raise ConfigurationError("mutation receipt plan is invalid")
        plan_sha256 = mutation.get("plan_sha256")
        if not isinstance(plan_sha256, str):
            raise ConfigurationError("mutation receipt plan digest is missing")
        plan = {key: value for key, value in mutation.items() if key != "plan_sha256"}
        if _digest(plan) != plan_sha256:
            raise ConfigurationError("mutation receipt plan digest does not match")
    if state in {"sensitive", "insensitive"} and plan_sha256 is None:
        raise ConfigurationError("mutation receipt state requires a mutation plan")
    return MutationReceiptSummary(
        hashlib.sha256(raw).hexdigest(),
        state,
        relationship_id,
        plan_sha256,
        False,
    )


def _collect_findings(
    evidence: RepositoryEvidence,
    impact: ImpactPlan,
) -> tuple[VerdictFinding, ...]:
    findings: list[VerdictFinding] = []
    for audit_finding in evidence.audit.findings:
        findings.append(
            _finding(
                audit_finding.rule,
                "error",
                audit_finding.path,
                audit_finding.detail,
                f"clean-docs explain {audit_finding.rule}",
            )
        )
    for stale_finding in evidence.audit.stale_baseline:
        findings.append(
            _finding(
                "stale-baseline",
                "error",
                stale_finding.path,
                f"resolved {stale_finding.rule} debt remains in the accepted baseline",
                "clean-docs audit --update-baseline",
            )
        )
    for result in evidence.bindings:
        if result.changed and result.state != "skipped-untrusted-execution":
            findings.append(
                _finding(
                    "binding-drift",
                    "error",
                    result.doc,
                    f"{result.binding_type} binding {result.binding_id} is stale",
                    (
                        f"clean-docs drive --binding {result.binding_id}"
                        if result.binding_type == "region"
                        else "repair the configured relationship, then run "
                        f"clean-docs check --binding {result.binding_id}"
                    ),
                )
            )
    for result in evidence.projections:
        if result.changed:
            findings.append(
                _finding(
                    "projection-drift",
                    "error",
                    result.doc,
                    f"projection {result.binding_id} is stale",
                    "clean-docs project",
                )
            )
    if evidence.source_claims is not None:
        for source_claim in evidence.source_claims.results:
            if source_claim.status == "drift":
                findings.append(
                    _finding(
                        "source-claim-drift",
                        "error",
                        source_claim.doc,
                        f"accepted source claim {source_claim.id} is stale",
                        "update the documented value or accepted relationship, "
                        "then run clean-docs claims",
                    )
                )
        for missing in evidence.source_claims.missing:
            findings.append(
                _finding(
                    "source-claim-missing",
                    "error",
                    missing.doc,
                    f"accepted source claim {missing.id} is missing",
                    "restore the documented claim and source locator or remove "
                    "the obsolete relationship from .clean-docs.yml",
                )
            )
    assert evidence.changed is not None
    for changed_finding in evidence.changed.required:
        level = "warning" if changed_finding.rule == "execution-skipped" else "error"
        findings.append(
            _finding(
                changed_finding.rule,
                level,
                changed_finding.doc or changed_finding.source,
                changed_finding.message,
                changed_finding.repair,
            )
        )
    for coverage_gap in evidence.changed.gaps:
        findings.append(
            _finding(
                coverage_gap.rule,
                "warning",
                coverage_gap.doc or coverage_gap.source,
                coverage_gap.message,
                coverage_gap.repair,
            )
        )
    for impact_unknown in impact.unknown:
        findings.append(
            _finding(
                impact_unknown.rule,
                "warning",
                (impact_unknown.paths[0] if impact_unknown.paths else impact.manifest),
                impact_unknown.message,
                "resolve the unsupported surface or declare its disposition, "
                "then rerun clean-docs plan",
            )
        )
    for contract in impact.review_contracts:
        targets = contract.targets or contract.sources
        path = targets[0].path if targets else impact.manifest
        if contract.state == "review-recommended":
            findings.append(
                _finding(
                    "review-contract-review-recommended",
                    "note",
                    path,
                    f"review contract {contract.contract_id} observed source "
                    "change without substantive target change",
                    "review the configured target against the source evidence; "
                    "update it only if the documented guidance changed",
                )
            )
        elif contract.state == "unknown":
            findings.append(
                _finding(
                    "review-contract-unknown",
                    "note",
                    path,
                    f"review contract {contract.contract_id} could not resolve "
                    "every configured locator",
                    "repair the unresolved review-contract locator, then rerun "
                    "clean-docs verdict",
                )
            )
    unique = {finding.id: finding for finding in findings}
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.level, item.path, item.rule, item.id),
        )
    )


def build_pr_verdict(
    root: Path,
    manifest_path: Path,
    *,
    base: str,
    head: str,
    mutation_receipt_paths: tuple[Path, ...] = (),
) -> PullRequestVerdict:
    root = root.resolve()
    status = _git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    if status:
        raise ConfigurationError("verdict requires a clean caller worktree")
    head_sha = _git(root, "rev-parse", head).decode().strip()
    caller_head = _git(root, "rev-parse", "HEAD").decode().strip()
    if caller_head != head_sha:
        raise ConfigurationError("verdict head must match the checked-out commit")
    impact = build_impact_plan(
        root,
        manifest_path,
        base=base,
        head=head_sha,
        use_cache=False,
        execution_policy=ExecutionPolicy.STATIC_ONLY,
    )
    evidence = collect_repository_evidence(
        root,
        manifest_path,
        base=impact.merge_base,
        head=head_sha,
        execution_policy=ExecutionPolicy.STATIC_ONLY,
        use_cache=False,
    )
    findings = _collect_findings(evidence, impact)
    state = _derive_gate_state(
        (finding.level for finding in findings),
        coverage_complete=impact.coverage_complete,
        impact=impact.impact,
    )
    try:
        manifest_relative = manifest_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ConfigurationError(
            "verdict manifest must be inside the repository"
        ) from exc
    summaries = tuple(
        _mutation_summary(path, head_sha) for path in mutation_receipt_paths
    )
    return PullRequestVerdict(
        state,
        impact.requested_base,
        impact.merge_base,
        head_sha,
        manifest_relative,
        impact.manifest_digest,
        impact,
        evidence,
        findings,
        summaries,
    )


def render_verdict_payload_sarif(payload: Mapping[str, object]) -> str:
    """Render SARIF from one already-computed verdict payload."""
    validate_verdict_payload(payload)
    producer = payload.get("producer")
    findings = payload["findings"]
    assert isinstance(producer, dict)
    assert isinstance(findings, list)
    version = producer.get("version")
    if not isinstance(version, str):
        raise ConfigurationError("verdict producer version is invalid")
    rules = sorted(
        {str(finding["rule"]) for finding in findings if isinstance(finding, dict)}
    )
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "clean-docs",
                        "version": version,
                        "rules": [
                            {
                                "id": rule,
                                "shortDescription": {"text": rule.replace("-", " ")},
                            }
                            for rule in rules
                        ],
                    }
                },
                "properties": {
                    "cleanDocsVerdictState": payload["state"],
                    "cleanDocsVerdictDigest": payload["digest"],
                },
                "results": [
                    {
                        "ruleId": finding["rule"],
                        "level": finding["level"],
                        "message": {
                            "text": (
                                f"{finding['message']}. Repair: {finding['repair']}"
                            )
                        },
                        "partialFingerprints": {"cleanDocsFindingId": finding["id"]},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": finding["path"]}
                                }
                            }
                        ],
                    }
                    for finding in findings
                ],
            }
        ],
    }
    return json.dumps(sarif, indent=2, sort_keys=True) + "\n"


def render_verdict_sarif(verdict: PullRequestVerdict) -> str:
    return render_verdict_payload_sarif(verdict.as_dict())
