"""Compile review observations into authority-bounded improvement candidates."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError
from clean_docs.regions import atomic_write


OBSERVATIONS_SCHEMA = "clean-docs.review-observations.v1"
CANDIDATES_SCHEMA = "clean-docs.improvement-candidates.v1"
TEST_KINDS = {
    "command",
    "fixture",
    "integration",
    "reader-task",
    "release",
    "static-analysis",
}
EVIDENCE_KINDS = {"external", "repository", "receipt"}
SHA1 = re.compile(r"^[0-9a-f]{40}$")
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
    evidence: tuple[dict[str, str], ...]
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


def _evidence(value: Any, where: str) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{where} must be a non-empty list")
    normalized = []
    for index, item in enumerate(value):
        item_where = f"{where}[{index}]"
        raw = _mapping(item, item_where)
        _exact_keys(raw, {"kind", "source", "locator", "detail"}, item_where)
        kind = _string(raw["kind"], f"{item_where}.kind")
        if kind not in EVIDENCE_KINDS:
            raise ConfigurationError(
                f"{item_where}.kind must be one of: "
                f"{', '.join(sorted(EVIDENCE_KINDS))}"
            )
        normalized.append({
            "kind": kind,
            "source": _string(raw["source"], f"{item_where}.source"),
            "locator": _string(raw["locator"], f"{item_where}.locator"),
            "detail": _string(raw["detail"], f"{item_where}.detail"),
        })
    return tuple(normalized)


def compile_improvement_candidates(
    payload: dict[str, Any],
    *,
    source_sha256: str | None = None,
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
        evidence = _evidence(raw["evidence"], f"{where}.evidence")
        tracks = (
            _track(raw["documentation"], "documentation", f"{where}.documentation"),
            _track(raw["product"], "product", f"{where}.product"),
        )
        candidate_identity = {
            "review_id": review_id,
            "observation_id": observation_id,
            "summary": summary,
            "evidence": list(evidence),
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


def load_review_candidates(path: Path) -> ImprovementCandidateSet:
    """Load a review-observation file and compile its candidates."""
    try:
        source = path.read_bytes()
        payload = json.loads(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read review observations {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError("review observations must be an object")
    return compile_improvement_candidates(
        payload,
        source_sha256=hashlib.sha256(source).hexdigest(),
    )


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
