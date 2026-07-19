"""Compose one coverage-stating pull-request verdict from deterministic evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

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
    "catalog coverage is not prose coverage",
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
                "total": sum(
                    result.binding_type == mechanism for result in bindings
                ),
                "current": sum(
                    result.binding_type == mechanism
                    and not result.changed
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
        return {
            "schema": VERDICT_SCHEMA,
            "producer": {"name": "clean-docs", "version": __version__},
            "state": self.state,
            "ready": self.ok,
            "scope": "configured-contract-and-changed-surface",
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
                            result.status == "drift"
                            for result in source_claims.results
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
                "artifacts": [
                    asdict(artifact) for artifact in self.impact.artifacts
                ],
                "unsupported_documents": list(
                    self.impact.unsupported_documents
                ),
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


def validate_verdict_payload(payload: Mapping[str, object]) -> None:
    """Reject a serialized verdict that cannot be the output of this schema."""
    if payload.get("schema") != VERDICT_SCHEMA:
        raise ConfigurationError(f"verdict schema must be {VERDICT_SCHEMA}")
    if payload.get("state") not in {"ready", "not_ready", "unknown"}:
        raise ConfigurationError("verdict state is invalid")
    digest = payload.get("digest")
    if not isinstance(digest, str):
        raise ConfigurationError("verdict digest is missing")
    unsigned = {key: value for key, value in payload.items() if key != "digest"}
    if _digest(unsigned) != digest:
        raise ConfigurationError("verdict digest does not match its payload")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ConfigurationError("verdict findings must be a list")
    for finding in findings:
        if not isinstance(finding, dict):
            raise ConfigurationError("verdict finding must be an object")
        required = ("id", "rule", "level", "path", "message", "repair")
        if any(not isinstance(finding.get(field), str) for field in required):
            raise ConfigurationError("verdict finding fields are invalid")


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
        raise ConfigurationError(
            f"mutation receipt schema must be {RECEIPT_SCHEMA}"
        )
    repository = receipt.get("repository")
    inputs = receipt.get("inputs")
    if not isinstance(repository, dict) or repository.get("commit") != head:
        raise ConfigurationError("mutation receipt commit does not match verdict head")
    if not isinstance(inputs, dict) or not isinstance(
        inputs.get("relationship"), dict
    ):
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
        level = (
            "warning"
            if changed_finding.rule == "execution-skipped"
            else "error"
        )
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
                (
                    impact_unknown.paths[0]
                    if impact_unknown.paths
                    else impact.manifest
                ),
                impact_unknown.message,
                "resolve the unsupported surface or declare its disposition, "
                "then rerun clean-docs plan",
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
    errors = any(finding.level == "error" for finding in findings)
    unknown = (
        not impact.coverage_complete
        or impact.impact == "unknown"
        or any(finding.level == "warning" for finding in findings)
    )
    state = "not_ready" if errors else "unknown" if unknown else "ready"
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
        {
            str(finding["rule"])
            for finding in findings
            if isinstance(finding, dict)
        }
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
                                "shortDescription": {
                                    "text": rule.replace("-", " ")
                                },
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
                        "partialFingerprints": {
                            "cleanDocsFindingId": finding["id"]
                        },
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": finding["path"]
                                    }
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
