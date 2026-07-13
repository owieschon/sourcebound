#!/usr/bin/env python3
"""Verify content-addressed independent-reader evidence for a stable release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised on Python 3.10 in CI
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
RUBRIC = Path(".clean-docs/reader-trial-rubric.yml")
RECEIPT = Path(".clean-docs/reader-trial.json")
EVIDENCE_ROOT = Path(".clean-docs/reader-trials")
STABLE_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
CANDIDATE_VERSION = re.compile(r"^(?P<line>[0-9]+\.[0-9]+\.[0-9]+)rc[0-9]+$")
PARTICIPANT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_EVIDENCE_BYTES = 1_000_000


class ReaderTrialError(ValueError):
    """The reader-trial evidence does not prove the release gate."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mapping(value: Any, *, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ReaderTrialError(f"{label} must contain exactly {', '.join(sorted(keys))}")
    return value


def _list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ReaderTrialError(f"{label} must be a non-empty list")
    return value


def _relative_file(root: Path, raw: Any, *, prefix: Path | None = None) -> Path:
    if not isinstance(raw, str):
        raise ReaderTrialError("evidence path must be a string")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReaderTrialError(f"evidence path escapes the repository: {raw}")
    if prefix is not None and not relative.is_relative_to(prefix):
        raise ReaderTrialError(f"evidence path must be under {prefix.as_posix()}: {raw}")
    path = root / relative
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ReaderTrialError(f"evidence path contains a symbolic link: {raw}")
    if not path.is_file():
        raise ReaderTrialError(f"evidence file is missing: {raw}")
    return path


def _timestamp(value: Any, *, label: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReaderTrialError(f"{label} must be an ISO 8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReaderTrialError(f"{label} must be an ISO 8601 UTC timestamp") from exc
    if parsed.utcoffset() is None:
        raise ReaderTrialError(f"{label} must include a UTC offset")


def _load_rubric(root: Path) -> tuple[dict[str, Any], bytes]:
    try:
        import yaml
    except ImportError as exc:
        raise ReaderTrialError(
            "stable reader-trial verification requires PyYAML"
        ) from exc
    path = root / RUBRIC
    try:
        data = path.read_bytes()
        raw: Any = yaml.safe_load(data)
    except (OSError, yaml.YAMLError) as exc:
        raise ReaderTrialError(f"cannot read reader rubric: {exc}") from exc
    rubric = _mapping(
        raw,
        label="reader rubric",
        keys={"version", "context", "profiles", "tasks"},
    )
    if rubric["version"] != 1:
        raise ReaderTrialError("reader rubric version must be 1")
    context = _list(rubric["context"], label="reader rubric context")
    if not all(isinstance(item, str) for item in context) or len(set(context)) != len(context):
        raise ReaderTrialError("reader rubric context paths must be unique strings")
    profiles = _list(rubric["profiles"], label="reader rubric profiles")
    profile_ids: list[str] = []
    for index, value in enumerate(profiles):
        profile = _mapping(
            value,
            label=f"reader rubric profile {index}",
            keys={"id", "provider", "model"},
        )
        if not all(isinstance(profile[key], str) and profile[key].strip() for key in profile):
            raise ReaderTrialError(
                f"reader rubric profile {index} fields must be non-empty strings"
            )
        if PARTICIPANT_ID.fullmatch(profile["id"]) is None:
            raise ReaderTrialError(f"reader rubric profile {index} id is unsafe")
        profile_ids.append(profile["id"])
    if len(set(profile_ids)) != len(profile_ids):
        raise ReaderTrialError("reader rubric profile ids must be unique")
    tasks = _list(rubric["tasks"], label="reader rubric tasks")
    identifiers: list[str] = []
    for index, value in enumerate(tasks):
        task = _mapping(
            value,
            label=f"reader rubric task {index}",
            keys={"id", "instruction", "passes_when"},
        )
        if not all(isinstance(task[key], str) and task[key].strip() for key in task):
            raise ReaderTrialError(f"reader rubric task {index} fields must be non-empty strings")
        identifiers.append(task["id"])
    if len(set(identifiers)) != len(identifiers):
        raise ReaderTrialError("reader rubric task ids must be unique")
    return rubric, data


def verify_reader_trial(root: Path, release_version: str) -> dict[str, object]:
    """Return a release-safe summary or raise when evidence is incomplete."""
    root = root.resolve()
    rubric, rubric_bytes = _load_rubric(root)
    receipt_path = root / RECEIPT
    try:
        receipt_bytes = receipt_path.read_bytes()
        raw: Any = json.loads(receipt_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReaderTrialError(f"cannot read independent-reader receipt: {exc}") from exc
    receipt = _mapping(
        raw,
        label="independent-reader receipt",
        keys={
            "schema",
            "candidate",
            "candidate_commit",
            "candidate_artifact_sha256",
            "rubric_sha256",
            "context",
            "participants",
        },
    )
    if receipt["schema"] != "clean-docs.independent-reader-trial.v2":
        raise ReaderTrialError("independent-reader receipt schema is unsupported")
    candidate = receipt["candidate"]
    match = CANDIDATE_VERSION.fullmatch(candidate) if isinstance(candidate, str) else None
    if match is None or match.group("line") != release_version:
        raise ReaderTrialError(f"reader trial candidate must be a release candidate for {release_version}")
    candidate_commit = receipt["candidate_commit"]
    if not isinstance(candidate_commit, str) or COMMIT_SHA.fullmatch(candidate_commit) is None:
        raise ReaderTrialError("reader trial candidate commit must be a full commit SHA")
    candidate_artifact = receipt["candidate_artifact_sha256"]
    if not isinstance(candidate_artifact, str) or SHA256.fullmatch(candidate_artifact) is None:
        raise ReaderTrialError("reader trial candidate artifact digest must be SHA-256")
    rubric_digest = _sha256(rubric_bytes)
    if receipt["rubric_sha256"] != rubric_digest:
        raise ReaderTrialError("reader trial rubric digest does not match the current rubric")

    expected_context = rubric["context"]
    context = _list(receipt["context"], label="reader receipt context")
    if len(context) != len(expected_context):
        raise ReaderTrialError("reader receipt must bind every rubric context document exactly once")
    bound_context: dict[str, str] = {}
    for index, value in enumerate(context):
        item = _mapping(value, label=f"reader context {index}", keys={"path", "sha256"})
        path = item["path"]
        digest = item["sha256"]
        if not isinstance(path, str) or path in bound_context:
            raise ReaderTrialError("reader context paths must be unique strings")
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise ReaderTrialError(f"reader context digest is invalid: {path}")
        document = _relative_file(root, path)
        actual = _sha256(document.read_bytes())
        if digest != actual:
            raise ReaderTrialError(f"reader context digest does not match: {path}")
        bound_context[path] = digest
    if set(bound_context) != set(expected_context):
        raise ReaderTrialError("reader receipt context does not match the rubric")

    expected_tasks = {task["id"] for task in rubric["tasks"]}
    participants = _list(receipt["participants"], label="reader receipt participants")
    required_profiles = {profile["id"] for profile in rubric["profiles"]}
    completed_profiles: dict[str, int] = {
        profile_id: 0 for profile_id in sorted(required_profiles)
    }
    participant_ids: set[str] = set()
    evidence_paths: set[str] = set()
    for index, value in enumerate(participants):
        participant = _mapping(
            value,
            label=f"reader participant {index}",
            keys={"id", "profile", "independent", "context", "completed_at", "tasks"},
        )
        identifier = participant["id"]
        if (
            not isinstance(identifier, str)
            or PARTICIPANT_ID.fullmatch(identifier) is None
            or identifier in participant_ids
        ):
            raise ReaderTrialError("reader participant ids must be unique safe identifiers")
        participant_ids.add(identifier)
        profile = participant["profile"]
        if profile not in completed_profiles:
            raise ReaderTrialError(f"reader participant {identifier} uses an undeclared profile")
        completed_profiles[profile] += 1
        if participant["independent"] is not True:
            raise ReaderTrialError(f"reader participant {identifier} did not attest independence")
        if participant["context"] != "published-docs-only":
            raise ReaderTrialError(f"reader participant {identifier} used undeclared context")
        _timestamp(participant["completed_at"], label=f"reader participant {identifier} completion")
        results = _list(participant["tasks"], label=f"reader participant {identifier} tasks")
        task_ids: set[str] = set()
        for task_index, value in enumerate(results):
            result = _mapping(
                value,
                label=f"reader participant {identifier} task {task_index}",
                keys={"id", "ok", "evidence", "sha256"},
            )
            task_id = result["id"]
            if not isinstance(task_id, str) or task_id in task_ids:
                raise ReaderTrialError(f"reader participant {identifier} task ids must be unique")
            task_ids.add(task_id)
            if result["ok"] is not True:
                raise ReaderTrialError(f"reader participant {identifier} did not pass {task_id}")
            evidence = result["evidence"]
            digest = result["sha256"]
            if not isinstance(evidence, str) or evidence in evidence_paths:
                raise ReaderTrialError("reader task evidence paths must be unique strings")
            if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
                raise ReaderTrialError(f"reader task evidence digest is invalid: {evidence}")
            evidence_path = _relative_file(root, evidence, prefix=EVIDENCE_ROOT)
            evidence_bytes = evidence_path.read_bytes()
            if not evidence_bytes or len(evidence_bytes) > MAX_EVIDENCE_BYTES:
                raise ReaderTrialError(f"reader task evidence size is invalid: {evidence}")
            if _sha256(evidence_bytes) != digest:
                raise ReaderTrialError(f"reader task evidence digest does not match: {evidence}")
            evidence_paths.add(evidence)
        if task_ids != expected_tasks:
            raise ReaderTrialError(f"reader participant {identifier} did not complete the exact rubric")
    if set(completed_profiles.values()) != {1} or len(participants) != len(required_profiles):
        raise ReaderTrialError("reader trial requires exactly one participant for every model profile")

    context_digest = _sha256(
        json.dumps(bound_context, sort_keys=True, separators=(",", ":")).encode()
    )
    return {
        "schema": receipt["schema"],
        "candidate": candidate,
        "candidate_commit": candidate_commit,
        "candidate_artifact_sha256": candidate_artifact,
        "receipt_sha256": _sha256(receipt_bytes),
        "rubric_sha256": rubric_digest,
        "context_sha256": context_digest,
        "participants": completed_profiles,
        "tasks_per_participant": len(expected_tasks),
    }


def project_version(root: Path) -> str:
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        version = project["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise ReaderTrialError(f"cannot read project version: {exc}") from exc
    if not isinstance(version, str):
        raise ReaderTrialError("project version must be a string")
    return version


def verify_release_reader_trial(root: Path) -> dict[str, object]:
    """Require external reader evidence only for a stable release."""
    version = project_version(root)
    if STABLE_VERSION.fullmatch(version) is None:
        return {"required": False}
    summary = verify_reader_trial(root, version)
    return {"required": True, **summary}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--release-version")
    args = parser.parse_args()
    try:
        version = args.release_version or project_version(args.root)
        summary = verify_reader_trial(args.root, version)
    except ReaderTrialError as exc:
        print(f"reader trial: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
