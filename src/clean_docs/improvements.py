"""Compile review observations into authority-bounded improvement candidates."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError, ExtractionError, PolicyError
from clean_docs.regions import atomic_write
from clean_docs.snapshot import RepositorySnapshot


OBSERVATIONS_SCHEMA = "clean-docs.review-observations.v1"
CANDIDATES_SCHEMA = "clean-docs.improvement-candidates.v1"
LIFECYCLE_SCHEMA = "clean-docs.improvement-candidate-lifecycle.v1"
TEST_KINDS = {
    "command",
    "fixture",
    "integration",
    "reader-task",
    "release",
    "static-analysis",
}
EVIDENCE_KINDS = {"external", "repository", "receipt"}
LIFECYCLE_EVIDENCE_KINDS = {"commit", "decision", "issue", "test-receipt"}
LIFECYCLE_STATES = {"proposed", "reproduced", "implemented", "verified", "declined"}
LIFECYCLE_TRANSITIONS = {
    "proposed": {"reproduced", "declined"},
    "reproduced": {"implemented", "declined"},
    "implemented": {"verified", "declined"},
    "verified": set(),
    "declined": set(),
}
LIFECYCLE_EVIDENCE_BY_STATE = {
    "reproduced": {"test-receipt"},
    "implemented": {"commit", "issue"},
    "verified": {"test-receipt"},
    "declined": {"decision", "issue"},
}
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class CandidateTest:
    kind: str
    setup: str
    action: str
    passes_when: str


@dataclass(frozen=True)
class CandidateTrack:
    target: str
    proposed_change: str
    test: CandidateTest


@dataclass(frozen=True)
class ImprovementCandidate:
    id: str
    observation_id: str
    summary: str
    evidence: tuple[dict[str, Any], ...]
    tracks: tuple[CandidateTrack, ...]
    state: str = "proposed"
    authority: str = "assessment"
    gate_authority: bool = False
    change_authority: bool = False


@dataclass(frozen=True)
class ImprovementCandidateSet:
    review_id: str
    repository_commit: str
    source_urls: tuple[str, ...]
    source_sha256: str
    candidates: tuple[ImprovementCandidate, ...]
    digest: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": CANDIDATES_SCHEMA,
            "review": {
                "id": self.review_id,
                "repository_commit": self.repository_commit,
                "source_urls": list(self.source_urls),
                "source_sha256": self.source_sha256,
            },
            "authority": {
                "state": "assessment",
                "gate_authority": False,
                "change_authority": False,
                "next_step": (
                    "Reproduce the observation and implement its proposed test before "
                    "requesting an ordinary verified change."
                ),
            },
            "candidates": [
                {
                    **asdict(candidate),
                    "evidence": list(candidate.evidence),
                    "tracks": [
                        {
                            "target": track.target,
                            "proposed_change": track.proposed_change,
                            "test": asdict(track.test),
                        }
                        for track in candidate.tracks
                    ],
                }
                for candidate in self.candidates
            ],
            "digest": self.digest,
        }


@dataclass(frozen=True)
class LifecycleEvidence:
    kind: str
    reference: str
    detail: str


@dataclass(frozen=True)
class LifecycleEvent:
    from_state: str
    to_state: str
    evidence: LifecycleEvidence


@dataclass(frozen=True)
class CandidateLifecycle:
    observation_id: str
    candidate_id: str
    state: str
    history: tuple[LifecycleEvent, ...]


@dataclass(frozen=True)
class CandidateLifecycleSet:
    review_id: str
    candidate_digest: str
    candidates: tuple[CandidateLifecycle, ...]
    digest: str

    def as_dict(self) -> dict[str, object]:
        payload = _lifecycle_payload(
            self.review_id,
            self.candidate_digest,
            self.candidates,
        )
        return {"schema": LIFECYCLE_SCHEMA, **payload, "digest": self.digest}


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    if set(value) != expected:
        raise ConfigurationError(
            f"{where} must contain exactly: {', '.join(sorted(expected))}"
        )


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{where} must be a non-empty string")
    return value.strip()


def _identifier(value: Any, where: str) -> str:
    identifier = _string(value, where)
    if not IDENTIFIER.fullmatch(identifier):
        raise ConfigurationError(f"{where} must be a lowercase kebab-case identifier")
    return identifier


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _test(value: Any, where: str) -> CandidateTest:
    raw = _mapping(value, where)
    _exact_keys(raw, {"kind", "setup", "action", "passes_when"}, where)
    kind = _string(raw["kind"], f"{where}.kind")
    if kind not in TEST_KINDS:
        raise ConfigurationError(
            f"{where}.kind must be one of: {', '.join(sorted(TEST_KINDS))}"
        )
    return CandidateTest(
        kind=kind,
        setup=_string(raw["setup"], f"{where}.setup"),
        action=_string(raw["action"], f"{where}.action"),
        passes_when=_string(raw["passes_when"], f"{where}.passes_when"),
    )


def _track(value: Any, target: str, where: str) -> CandidateTrack:
    raw = _mapping(value, where)
    _exact_keys(raw, {"proposed_change", "test"}, where)
    return CandidateTrack(
        target=target,
        proposed_change=_string(raw["proposed_change"], f"{where}.proposed_change"),
        test=_test(raw["test"], f"{where}.test"),
    )


def _receipt_evidence(
    value: Any,
    *,
    where: str,
    source: str,
    repository_commit: str,
    root: Path | None,
) -> dict[str, object]:
    raw = _mapping(value, where)
    _exact_keys(
        raw,
        {"sha256", "producer_version", "repository_commit", "command"},
        where,
    )
    digest = _string(raw["sha256"], f"{where}.sha256")
    if not SHA256.fullmatch(digest):
        raise ConfigurationError(f"{where}.sha256 must be a lowercase SHA-256")
    receipt_commit = _string(raw["repository_commit"], f"{where}.repository_commit")
    if receipt_commit != repository_commit:
        raise ConfigurationError(f"{where}.repository_commit must match the review commit")
    command = raw["command"]
    if not isinstance(command, list) or not command or not all(
        isinstance(item, str) and item for item in command
    ):
        raise ConfigurationError(f"{where}.command must be a non-empty string list")
    receipt: dict[str, object] = {
        "sha256": digest,
        "producer_version": _string(raw["producer_version"], f"{where}.producer_version"),
        "repository_commit": receipt_commit,
        "command": list(command),
        "state": "unknown",
    }
    if root is None:
        return receipt
    receipt_path = root / source
    try:
        receipt_path.resolve().relative_to(root.resolve())
        observed = receipt_path.read_bytes()
    except (OSError, ValueError):
        return receipt
    if hashlib.sha256(observed).hexdigest() != digest:
        raise ConfigurationError(f"{where}.sha256 does not match receipt bytes")
    receipt["state"] = "grounded"
    return receipt


def _evidence(
    value: Any,
    where: str,
    *,
    repository_commit: str,
    root: Path | None,
) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{where} must be a non-empty list")
    normalized = []
    for index, item in enumerate(value):
        item_where = f"{where}[{index}]"
        raw = _mapping(item, item_where)
        _exact_keys(
            raw,
            ({"kind", "source", "locator", "detail", "receipt"}
             if raw.get("kind") == "receipt"
             else {"kind", "source", "locator", "detail"}),
            item_where,
        )
        kind = _string(raw["kind"], f"{item_where}.kind")
        if kind not in EVIDENCE_KINDS:
            raise ConfigurationError(
                f"{item_where}.kind must be one of: "
                f"{', '.join(sorted(EVIDENCE_KINDS))}"
            )
        evidence: dict[str, object] = {
            "kind": kind,
            "source": _string(raw["source"], f"{item_where}.source"),
            "locator": _string(raw["locator"], f"{item_where}.locator"),
            "detail": _string(raw["detail"], f"{item_where}.detail"),
        }
        if kind == "receipt":
            evidence["receipt"] = _receipt_evidence(
                raw["receipt"],
                where=f"{item_where}.receipt",
                source=str(evidence["source"]),
                repository_commit=repository_commit,
                root=root,
            )
        normalized.append(evidence)
    return tuple(normalized)


def _candidate_identity_evidence(
    evidence: tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    """Keep availability observations out of a candidate's stable identity."""
    identity = []
    for item in evidence:
        normalized = dict(item)
        receipt = normalized.get("receipt")
        if isinstance(receipt, dict):
            normalized["receipt"] = {
                key: value for key, value in receipt.items() if key != "state"
            }
        identity.append(normalized)
    return identity


def compile_improvement_candidates(
    payload: dict[str, Any],
    *,
    source_sha256: str | None = None,
    root: Path | None = None,
) -> ImprovementCandidateSet:
    """Validate one review and compile its observations into stable candidates."""
    _exact_keys(
        payload,
        {"schema", "review_id", "repository_commit", "source_urls", "observations"},
        "review observations",
    )
    if payload["schema"] != OBSERVATIONS_SCHEMA:
        raise ConfigurationError(
            f"review observations schema must be {OBSERVATIONS_SCHEMA}"
        )
    review_id = _identifier(payload["review_id"], "review observations.review_id")
    repository_commit = _string(
        payload["repository_commit"],
        "review observations.repository_commit",
    )
    if not SHA1.fullmatch(repository_commit):
        raise ConfigurationError(
            "review observations.repository_commit must be a full lowercase SHA-1"
        )
    source_urls_raw = payload["source_urls"]
    if not isinstance(source_urls_raw, list) or not source_urls_raw:
        raise ConfigurationError(
            "review observations.source_urls must be a non-empty list"
        )
    source_urls = tuple(
        _string(value, f"review observations.source_urls[{index}]")
        for index, value in enumerate(source_urls_raw)
    )
    if len(set(source_urls)) != len(source_urls):
        raise ConfigurationError("review observations.source_urls must be unique")
    observations = payload["observations"]
    if not isinstance(observations, list) or not observations:
        raise ConfigurationError(
            "review observations.observations must be a non-empty list"
        )

    compiled = []
    seen: set[str] = set()
    for index, value in enumerate(observations):
        where = f"review observations.observations[{index}]"
        raw = _mapping(value, where)
        _exact_keys(
            raw,
            {"id", "summary", "evidence", "documentation", "product"},
            where,
        )
        observation_id = _identifier(raw["id"], f"{where}.id")
        if observation_id in seen:
            raise ConfigurationError(
                f"duplicate review observation id: {observation_id}"
            )
        seen.add(observation_id)
        summary = _string(raw["summary"], f"{where}.summary")
        evidence = _evidence(
            raw["evidence"],
            f"{where}.evidence",
            repository_commit=repository_commit,
            root=root,
        )
        tracks = (
            _track(raw["documentation"], "documentation", f"{where}.documentation"),
            _track(raw["product"], "product", f"{where}.product"),
        )
        candidate_identity = {
            "review_id": review_id,
            "observation_id": observation_id,
            "summary": summary,
            "evidence": _candidate_identity_evidence(evidence),
            "tracks": [
                {
                    "target": track.target,
                    "proposed_change": track.proposed_change,
                    "test": asdict(track.test),
                }
                for track in tracks
            ],
        }
        compiled.append(
            ImprovementCandidate(
                id=_digest(candidate_identity),
                observation_id=observation_id,
                summary=summary,
                evidence=evidence,
                tracks=tracks,
            )
        )

    compiled.sort(key=lambda item: item.observation_id)
    source_digest = source_sha256 or _digest(payload)
    unsigned = {
        "review": {
            "id": review_id,
            "repository_commit": repository_commit,
            "source_urls": list(source_urls),
            "source_sha256": source_digest,
        },
        "candidates": [
            {
                **asdict(candidate),
                "evidence": list(candidate.evidence),
                "tracks": [
                    {
                        "target": track.target,
                        "proposed_change": track.proposed_change,
                        "test": asdict(track.test),
                    }
                    for track in candidate.tracks
                ],
            }
            for candidate in compiled
        ],
    }
    return ImprovementCandidateSet(
        review_id=review_id,
        repository_commit=repository_commit,
        source_urls=source_urls,
        source_sha256=source_digest,
        candidates=tuple(compiled),
        digest=_digest(unsigned),
    )


def ground_review_candidates(
    root: Path,
    candidates: ImprovementCandidateSet,
) -> ImprovementCandidateSet:
    """Resolve repository evidence at the review's pinned commit.

    Unknown evidence remains assessment-only. It never becomes a false grounded claim.
    """
    snapshot = RepositorySnapshot(root, candidates.repository_commit)
    try:
        resolved_commit = snapshot.label
    except ExtractionError as exc:
        resolved_commit = None
        unavailable_detail = str(exc)
    grounded_candidates = []
    for candidate in candidates.candidates:
        evidence = []
        for item in candidate.evidence:
            grounded_item = dict(item)
            if item["kind"] == "repository":
                if resolved_commit is None:
                    grounding = {
                        "state": "unknown",
                        "detail": f"pinned commit is unavailable: {unavailable_detail}",
                    }
                else:
                    try:
                        source = Path(str(item["source"]))
                        text = snapshot.read_text(source)
                    except ExtractionError as exc:
                        grounding = {
                            "state": "unknown",
                            "commit": resolved_commit,
                            "detail": str(exc),
                        }
                    else:
                        locator = str(item["locator"])
                        if locator not in text:
                            grounding = {
                                "state": "unknown",
                                "commit": resolved_commit,
                                "content_sha256": hashlib.sha256(
                                    text.encode("utf-8")
                                ).hexdigest(),
                                "detail": "locator is absent from the pinned source bytes",
                            }
                        else:
                            grounding = {
                                "state": "grounded",
                                "commit": resolved_commit,
                                "content_sha256": hashlib.sha256(
                                    text.encode("utf-8")
                                ).hexdigest(),
                            }
            else:
                grounding = {
                    "state": "unverified",
                    "detail": (
                        "external evidence requires an immutable retrieval receipt"
                        if item["kind"] == "external"
                        else "receipt evidence requires immutable bytes and execution context"
                    ),
                }
            grounded_item["grounding"] = grounding
            evidence.append(grounded_item)
        grounded_candidates.append(
            ImprovementCandidate(
                id=candidate.id,
                observation_id=candidate.observation_id,
                summary=candidate.summary,
                evidence=tuple(evidence),
                tracks=candidate.tracks,
            )
        )
    grounded_candidates_tuple = tuple(grounded_candidates)
    unsigned = {
        "review": {
            "id": candidates.review_id,
            "repository_commit": candidates.repository_commit,
            "source_urls": list(candidates.source_urls),
            "source_sha256": candidates.source_sha256,
        },
        "candidates": [
            {
                **asdict(candidate),
                "evidence": list(candidate.evidence),
                "tracks": [
                    {
                        "target": track.target,
                        "proposed_change": track.proposed_change,
                        "test": asdict(track.test),
                    }
                    for track in candidate.tracks
                ],
            }
            for candidate in grounded_candidates_tuple
        ],
    }
    return ImprovementCandidateSet(
        review_id=candidates.review_id,
        repository_commit=candidates.repository_commit,
        source_urls=candidates.source_urls,
        source_sha256=candidates.source_sha256,
        candidates=grounded_candidates_tuple,
        digest=_digest(unsigned),
    )

def load_review_candidates(
    path: Path,
    *,
    root: Path | None = None,
) -> ImprovementCandidateSet:
    """Load a review-observation file and compile its candidates."""
    try:
        source = path.read_bytes()
        payload = json.loads(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read review observations {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError("review observations must be an object")
    candidates = compile_improvement_candidates(
        payload,
        source_sha256=hashlib.sha256(source).hexdigest(),
        root=root,
    )
    return ground_review_candidates(root, candidates) if root is not None else candidates


def write_improvement_candidates(
    candidates: ImprovementCandidateSet,
    output: Path,
) -> Path:
    """Write one deterministic candidate set."""
    atomic_write(
        output,
        json.dumps(candidates.as_dict(), indent=2, ensure_ascii=False) + "\n",
    )
    return output


def _lifecycle_authority() -> dict[str, object]:
    return {
        "state": "assessment",
        "gate_authority": False,
        "change_authority": False,
        "next_step": (
            "Use linked evidence to record the candidate lifecycle; ordinary repository "
            "gates still decide whether a change is accepted."
        ),
    }


def _lifecycle_payload(
    review_id: str,
    candidate_digest: str,
    candidates: tuple[CandidateLifecycle, ...],
) -> dict[str, object]:
    return {
        "candidate_set": {
            "review_id": review_id,
            "digest": candidate_digest,
        },
        "authority": _lifecycle_authority(),
        "candidates": [
            {
                "observation_id": candidate.observation_id,
                "candidate_id": candidate.candidate_id,
                "state": candidate.state,
                "history": [
                    {
                        "from": event.from_state,
                        "to": event.to_state,
                        "evidence": asdict(event.evidence),
                    }
                    for event in candidate.history
                ],
            }
            for candidate in candidates
        ],
    }


def _lifecycle_digest(
    review_id: str,
    candidate_digest: str,
    candidates: tuple[CandidateLifecycle, ...],
) -> str:
    return _digest(_lifecycle_payload(review_id, candidate_digest, candidates))


def _lifecycle_evidence(value: Any, where: str) -> LifecycleEvidence:
    raw = _mapping(value, where)
    _exact_keys(raw, {"kind", "reference", "detail"}, where)
    kind = _string(raw["kind"], f"{where}.kind")
    if kind not in LIFECYCLE_EVIDENCE_KINDS:
        raise ConfigurationError(
            f"{where}.kind must be one of: "
            f"{', '.join(sorted(LIFECYCLE_EVIDENCE_KINDS))}"
        )
    return LifecycleEvidence(
        kind=kind,
        reference=_string(raw["reference"], f"{where}.reference"),
        detail=_string(raw["detail"], f"{where}.detail"),
    )


def _lifecycle_event(value: Any, where: str) -> LifecycleEvent:
    raw = _mapping(value, where)
    _exact_keys(raw, {"from", "to", "evidence"}, where)
    from_state = _string(raw["from"], f"{where}.from")
    to_state = _string(raw["to"], f"{where}.to")
    if from_state not in LIFECYCLE_STATES or to_state not in LIFECYCLE_STATES:
        raise ConfigurationError(f"{where} has an invalid lifecycle state")
    if to_state not in LIFECYCLE_TRANSITIONS[from_state]:
        raise ConfigurationError(
            f"{where} cannot transition from {from_state} to {to_state}"
        )
    evidence = _lifecycle_evidence(raw["evidence"], f"{where}.evidence")
    if evidence.kind not in LIFECYCLE_EVIDENCE_BY_STATE[to_state]:
        raise ConfigurationError(
            f"{where}.evidence.kind must support transition to {to_state}"
        )
    return LifecycleEvent(from_state, to_state, evidence)


def initialize_candidate_lifecycle(
    candidates: ImprovementCandidateSet,
) -> CandidateLifecycleSet:
    """Start an assessment-only lifecycle for every candidate in one review."""
    records = tuple(
        CandidateLifecycle(
            observation_id=candidate.observation_id,
            candidate_id=candidate.id,
            state="proposed",
            history=(),
        )
        for candidate in candidates.candidates
    )
    return CandidateLifecycleSet(
        review_id=candidates.review_id,
        candidate_digest=candidates.digest,
        candidates=records,
        digest=_lifecycle_digest(candidates.review_id, candidates.digest, records),
    )


def load_candidate_lifecycle(
    path: Path,
    candidates: ImprovementCandidateSet,
) -> CandidateLifecycleSet:
    """Load a lifecycle record and prove that it still matches one candidate set."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read candidate lifecycle {path}: {exc}") from exc
    root = _mapping(raw, "candidate lifecycle")
    _exact_keys(
        root,
        {"schema", "candidate_set", "authority", "candidates", "digest"},
        "candidate lifecycle",
    )
    if root["schema"] != LIFECYCLE_SCHEMA:
        raise ConfigurationError(f"candidate lifecycle schema must be {LIFECYCLE_SCHEMA}")
    candidate_set = _mapping(root["candidate_set"], "candidate lifecycle.candidate_set")
    _exact_keys(candidate_set, {"review_id", "digest"}, "candidate lifecycle.candidate_set")
    review_id = _identifier(candidate_set["review_id"], "candidate lifecycle.candidate_set.review_id")
    candidate_digest = _string(
        candidate_set["digest"], "candidate lifecycle.candidate_set.digest"
    )
    if not re.fullmatch(r"[0-9a-f]{64}", candidate_digest):
        raise ConfigurationError("candidate lifecycle.candidate_set.digest must be a SHA-256")
    authority = _mapping(root["authority"], "candidate lifecycle.authority")
    if authority != _lifecycle_authority():
        raise ConfigurationError("candidate lifecycle.authority must preserve assessment-only authority")
    raw_records = root["candidates"]
    if not isinstance(raw_records, list):
        raise ConfigurationError("candidate lifecycle.candidates must be a list")
    records = []
    seen: set[str] = set()
    for index, item in enumerate(raw_records):
        where = f"candidate lifecycle.candidates[{index}]"
        record = _mapping(item, where)
        _exact_keys(record, {"observation_id", "candidate_id", "state", "history"}, where)
        observation_id = _identifier(record["observation_id"], f"{where}.observation_id")
        if observation_id in seen:
            raise ConfigurationError(f"duplicate lifecycle observation id: {observation_id}")
        seen.add(observation_id)
        candidate_id = _string(record["candidate_id"], f"{where}.candidate_id")
        if not re.fullmatch(r"[0-9a-f]{64}", candidate_id):
            raise ConfigurationError(f"{where}.candidate_id must be a SHA-256")
        state = _string(record["state"], f"{where}.state")
        if state not in LIFECYCLE_STATES:
            raise ConfigurationError(f"{where}.state is invalid")
        raw_history = record["history"]
        if not isinstance(raw_history, list):
            raise ConfigurationError(f"{where}.history must be a list")
        history = tuple(
            _lifecycle_event(event, f"{where}.history[{event_index}]")
            for event_index, event in enumerate(raw_history)
        )
        derived = "proposed"
        for event in history:
            if event.from_state != derived:
                raise ConfigurationError(
                    f"{where}.history does not continue from {derived}"
                )
            derived = event.to_state
        if state != derived:
            raise ConfigurationError(f"{where}.state contradicts its history")
        records.append(CandidateLifecycle(observation_id, candidate_id, state, history))
    records.sort(key=lambda record: record.observation_id)
    records_tuple = tuple(records)
    expected_records = tuple(
        (candidate.observation_id, candidate.id)
        for candidate in candidates.candidates
    )
    observed_records = tuple(
        (record.observation_id, record.candidate_id) for record in records_tuple
    )
    if review_id != candidates.review_id or candidate_digest != candidates.digest:
        raise PolicyError("candidate lifecycle is stale for the current review candidate set")
    if observed_records != expected_records:
        raise PolicyError("candidate lifecycle records do not match the current candidate set")
    digest = _string(root["digest"], "candidate lifecycle.digest")
    expected_digest = _lifecycle_digest(review_id, candidate_digest, records_tuple)
    if digest != expected_digest:
        raise ConfigurationError("candidate lifecycle.digest does not match its content")
    return CandidateLifecycleSet(review_id, candidate_digest, records_tuple, digest)


def transition_candidate_lifecycle(
    lifecycle: CandidateLifecycleSet,
    *,
    observation_id: str,
    to_state: str,
    evidence: LifecycleEvidence,
) -> CandidateLifecycleSet:
    """Apply one evidence-backed adjacent transition without granting authority."""
    observation_id = _identifier(observation_id, "lifecycle observation id")
    if to_state not in LIFECYCLE_STATES:
        raise ConfigurationError("lifecycle transition target state is invalid")
    evidence = _lifecycle_evidence(asdict(evidence), "lifecycle transition evidence")
    records = []
    found = False
    for record in lifecycle.candidates:
        if record.observation_id != observation_id:
            records.append(record)
            continue
        found = True
        if to_state not in LIFECYCLE_TRANSITIONS[record.state]:
            raise ConfigurationError(
                f"candidate {observation_id} cannot transition from {record.state} to {to_state}"
            )
        if evidence.kind not in LIFECYCLE_EVIDENCE_BY_STATE[to_state]:
            raise ConfigurationError(
                f"evidence kind {evidence.kind} cannot support transition to {to_state}"
            )
        records.append(
            CandidateLifecycle(
                observation_id=record.observation_id,
                candidate_id=record.candidate_id,
                state=to_state,
                history=(*record.history, LifecycleEvent(record.state, to_state, evidence)),
            )
        )
    if not found:
        raise ConfigurationError(f"candidate observation id was not found: {observation_id}")
    records_tuple = tuple(records)
    return CandidateLifecycleSet(
        review_id=lifecycle.review_id,
        candidate_digest=lifecycle.candidate_digest,
        candidates=records_tuple,
        digest=_lifecycle_digest(
            lifecycle.review_id,
            lifecycle.candidate_digest,
            records_tuple,
        ),
    )


def write_candidate_lifecycle(
    lifecycle: CandidateLifecycleSet,
    output: Path,
) -> Path:
    """Write one explicit lifecycle record."""
    atomic_write(output, json.dumps(lifecycle.as_dict(), indent=2, ensure_ascii=False) + "\n")
    return output
