"""Validate the append-only denominator for review observations."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError, PolicyError
from clean_docs.improvements import ImprovementCandidateSet


REVIEW_EVENT_LEDGER_SCHEMA = "sourcebound.review-event-ledger.v2"
_LEGACY_REVIEW_EVENT_LEDGER_SCHEMA = "sourcebound.review-event-ledger.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class ReviewEvent:
    id: str
    observation_id: str
    disposition: str
    candidate_id: str | None
    successor: str | None
    previous_digest: str | None
    digest: str


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    return value


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{where} must be a non-empty string")
    return value


def _identifier(value: Any, where: str) -> str:
    output = _string(value, where)
    if not _IDENTIFIER.fullmatch(output):
        raise ConfigurationError(f"{where} must be kebab-case")
    return output


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _event_digest(event: ReviewEvent) -> str:
    return _digest(
        {
            "id": event.id,
            "observation_id": event.observation_id,
            "disposition": event.disposition,
            "candidate_id": event.candidate_id,
            "successor": event.successor,
            "previous_digest": event.previous_digest,
        }
    )


def _event(value: Any, index: int) -> ReviewEvent:
    where = f"review event ledger.events[{index}]"
    raw = _object(value, where)
    expected = {
        "id",
        "observation_id",
        "disposition",
        "candidate_id",
        "successor",
        "previous_digest",
        "digest",
    }
    if set(raw) != expected:
        raise ConfigurationError(f"{where} must contain exactly: {', '.join(sorted(expected))}")
    disposition = _string(raw["disposition"], f"{where}.disposition")
    if disposition not in {"candidate", "superseded", "merged"}:
        raise ConfigurationError(f"{where}.disposition is invalid")
    candidate_id = raw["candidate_id"]
    successor = raw["successor"]
    if disposition == "candidate":
        candidate_id = _string(candidate_id, f"{where}.candidate_id")
        if not _SHA256.fullmatch(candidate_id):
            raise ConfigurationError(f"{where}.candidate_id must be a SHA-256")
        if successor is not None:
            raise ConfigurationError(f"{where}.successor must be null for a candidate")
    else:
        if candidate_id is not None:
            raise ConfigurationError(f"{where}.candidate_id must be null for {disposition}")
        successor = _identifier(successor, f"{where}.successor")
    previous_digest = raw["previous_digest"]
    if previous_digest is not None:
        previous_digest = _string(previous_digest, f"{where}.previous_digest")
        if not _SHA256.fullmatch(previous_digest):
            raise ConfigurationError(f"{where}.previous_digest must be a SHA-256 or null")
    event = ReviewEvent(
        id=_identifier(raw["id"], f"{where}.id"),
        observation_id=_identifier(raw["observation_id"], f"{where}.observation_id"),
        disposition=disposition,
        candidate_id=candidate_id,
        successor=successor,
        previous_digest=previous_digest,
        digest=_string(raw["digest"], f"{where}.digest"),
    )
    if event.digest != _event_digest(event):
        raise ConfigurationError(f"{where}.digest does not match its content")
    return event


@dataclass(frozen=True)
class ReviewEventLedger:
    schema: str
    review_id: str
    events: tuple[ReviewEvent, ...]
    head_digest: str
    migration_base_head_digest: str | None


def _load_review_event_ledger(path: Path) -> ReviewEventLedger:
    """Load one internally consistent ledger without assigning candidate authority."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read review event ledger {path}: {exc}") from exc
    root = _object(raw, "review event ledger")
    schema = _string(root.get("schema"), "review event ledger.schema")
    if schema == REVIEW_EVENT_LEDGER_SCHEMA:
        expected_keys = {
            "schema",
            "review_id",
            "events",
            "head_digest",
            "migration_base_head_digest",
        }
    elif schema == _LEGACY_REVIEW_EVENT_LEDGER_SCHEMA:
        expected_keys = {"schema", "review_id", "events", "head_digest"}
    else:
        raise ConfigurationError(
            "review event ledger schema must be "
            f"{REVIEW_EVENT_LEDGER_SCHEMA} or {_LEGACY_REVIEW_EVENT_LEDGER_SCHEMA}"
        )
    if set(root) != expected_keys:
        raise ConfigurationError("review event ledger has an invalid shape")
    review_id = _identifier(root["review_id"], "review event ledger.review_id")
    if not isinstance(root["events"], list) or not root["events"]:
        raise ConfigurationError("review event ledger.events must be a non-empty list")
    events = tuple(_event(item, index) for index, item in enumerate(root["events"]))
    seen_ids: set[str] = set()
    by_observation: dict[str, ReviewEvent] = {}
    previous: str | None = None
    for event in events:
        if event.id in seen_ids:
            raise ConfigurationError(f"duplicate review event id: {event.id}")
        seen_ids.add(event.id)
        if event.previous_digest != previous:
            raise ConfigurationError("review event ledger chain is not append-only")
        previous = event.digest
        if event.observation_id in by_observation:
            raise ConfigurationError(f"duplicate review event observation id: {event.observation_id}")
        by_observation[event.observation_id] = event
    if root["head_digest"] != previous:
        raise ConfigurationError("review event ledger.head_digest does not match the event chain")
    assert previous is not None
    migration_base_head_digest = root.get("migration_base_head_digest")
    if migration_base_head_digest is not None:
        migration_base_head_digest = _string(
            migration_base_head_digest,
            "review event ledger.migration_base_head_digest",
        )
        if not _SHA256.fullmatch(migration_base_head_digest):
            raise ConfigurationError(
                "review event ledger.migration_base_head_digest must be a SHA-256"
            )
    return ReviewEventLedger(
        schema=schema,
        review_id=review_id,
        events=events,
        head_digest=previous,
        migration_base_head_digest=migration_base_head_digest,
    )


def validate_review_event_ledger(
    path: Path,
    candidates: ImprovementCandidateSet,
    *,
    prior_path: Path | None = None,
) -> str:
    """Require one current disposition and preserve the base ledger as a prefix."""
    ledger = _load_review_event_ledger(path)
    if ledger.review_id != candidates.review_id:
        raise PolicyError("review event ledger belongs to another review")
    if prior_path is not None:
        prior = _load_review_event_ledger(prior_path)
        if prior.review_id != ledger.review_id:
            raise PolicyError("prior review event ledger belongs to another review")
        if prior.schema == REVIEW_EVENT_LEDGER_SCHEMA and ledger.schema != prior.schema:
            raise PolicyError("review event ledger cannot downgrade from the anchored schema")
        if ledger.schema == REVIEW_EVENT_LEDGER_SCHEMA and prior.schema == _LEGACY_REVIEW_EVENT_LEDGER_SCHEMA:
            if ledger.migration_base_head_digest != prior.head_digest:
                raise PolicyError("review event ledger migration does not bind the legacy head")
        else:
            if ledger.events[: len(prior.events)] != prior.events:
                raise PolicyError("review event ledger rewrites the immutable base history")
            if ledger.migration_base_head_digest != prior.migration_base_head_digest:
                raise PolicyError("review event ledger rewrites its migration anchor")
    events = ledger.events
    by_observation = {event.observation_id: event for event in events}
    candidate_ids = {candidate.observation_id: candidate.id for candidate in candidates.candidates}
    for observation_id, candidate_id in candidate_ids.items():
        ledger_event = by_observation.get(observation_id)
        if ledger_event is None:
            raise PolicyError(f"review event ledger is missing observation: {observation_id}")
        if ledger_event.disposition != "candidate" or ledger_event.candidate_id != candidate_id:
            raise PolicyError(f"review event ledger retargets observation: {observation_id}")
    for event in events:
        if event.disposition == "candidate" and event.observation_id not in candidate_ids:
            raise PolicyError(f"review candidate is silently removed from the review: {event.observation_id}")
        if event.disposition != "candidate":
            successor = by_observation.get(event.successor or "")
            if successor is None or successor.disposition != "candidate":
                raise PolicyError(f"review event {event.id} has no candidate successor")
    return events[-1].digest
