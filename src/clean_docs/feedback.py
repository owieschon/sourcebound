from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from clean_docs import __version__
from clean_docs.adapters.event_capture import deliver_event
from clean_docs.errors import ConfigurationError
from clean_docs.regions import atomic_write
from clean_docs.verdict import validate_verdict_payload

CONFIG_PATH = Path(".sourcebound/feedback.json")
STATE_DIR = Path(".sourcebound/feedback")
OUTBOX_DIR = STATE_DIR / "outbox"
DEAD_LETTER_DIR = STATE_DIR / "dead-letter"
ATTEMPTS_DIR = STATE_DIR / "attempts"
SIGNALS_DIR = STATE_DIR / "signals"
CASES_DIR = STATE_DIR / "cases"
RECEIPTS_DIR = STATE_DIR / "receipts"

CONFIG_SCHEMA = "sourcebound.feedback-config.v1"
ENVELOPE_SCHEMA = "sourcebound.feedback.v1"
SIGNAL_SCHEMA = "sourcebound.behavior-signal.v1"
CASE_SCHEMA = "sourcebound.improvement-case.v1"

DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_RECORDS = 1_000
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
MAX_DELIVERY_ATTEMPTS = 3

_CONFIG_KEYS = {
    "schema",
    "enabled",
    "installation_id",
    "sink",
    "retention_days",
    "max_records",
    "max_bytes",
}
_ENVELOPE_KEYS = {
    "schema",
    "event_id",
    "run_id",
    "outcome_id",
    "occurred_at",
    "product_version",
    "installation_id",
    "command",
    "exit_code",
    "result_class",
    "execution_policy",
    "adapter",
    "repository_size_class",
    "outcome",
}
_SIGNAL_KEYS = {
    "schema",
    "signal_id",
    "metric",
    "window",
    "counts",
    "segment",
    "data_quality",
    "privacy_class",
    "source_receipt",
    "contradictory_evidence",
    "evidence_class",
}
_CASE_STATES = (
    "observed",
    "reproduced",
    "root-cause-classified",
    "evaluation-proposed",
    "regression-added",
    "shadow-measured",
    "candidate-change",
    "ordinary-verified-pr",
)
_METRIC_KEYS = {"name", "version", "direction"}
_WINDOW_KEYS = {"start", "end"}
_COUNT_KEYS = {"numerator", "denominator"}
_SEGMENT_KEYS = {
    "scope",
    "installations",
    "contributing_installations",
    "product_versions",
    "adapters",
    "execution_policies",
    "repository_size_classes",
}
_SOURCE_RECEIPT_KEYS = {"schema", "sha256"}
_TRANSITION_RECEIPT_SCHEMAS = {
    "reproduced": "sourcebound.reproduction.v1",
    "root-cause-classified": "sourcebound.root-cause.v1",
    "evaluation-proposed": "sourcebound.evaluation-proposal.v1",
    "regression-added": "sourcebound.regression-receipt.v1",
    "shadow-measured": "sourcebound.shadow-evaluation.v1",
    "candidate-change": "sourcebound.candidate-change.v1",
    "ordinary-verified-pr": "sourcebound.pr-verdict.v1",
}
_SHADOW_KEYS = {
    "schema",
    "prior_receipt_sha256",
    "cohort_version",
    "direction",
    "baseline",
    "candidate",
    "protected_segments",
    "baseline_metric_digest",
    "candidate_metric_digest",
    "baseline_scorer_digest",
    "candidate_scorer_digest",
    "baseline_threshold_digest",
    "candidate_threshold_digest",
}
_PROTECTED_SEGMENT_KEYS = {"name", "baseline", "candidate"}
_REPRODUCTION_KEYS = {
    "schema",
    "signal_id",
    "fixture_sha256",
    "baseline_outcome_id",
    "reproduced",
    "failure_class",
}
_ROOT_CAUSE_KEYS = {
    "schema",
    "prior_receipt_sha256",
    "classification",
    "evidence_sha256",
}
_EVALUATION_PROPOSAL_KEYS = {
    "schema",
    "prior_receipt_sha256",
    "metric_sha256",
    "scorer_sha256",
    "threshold_sha256",
    "protected_segments",
}
_REGRESSION_KEYS = {
    "schema",
    "prior_receipt_sha256",
    "fixture_sha256",
    "demonstrated_red",
}
_CANDIDATE_CHANGE_KEYS = {
    "schema",
    "prior_receipt_sha256",
    "change_sha256",
    "regression_suite_sha256",
}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: object, where: str) -> datetime:
    text = _require_string(value, where)
    if not text.endswith("Z"):
        raise ConfigurationError(f"{where} must be an ISO 8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(text.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ConfigurationError(f"{where} must be an ISO 8601 UTC timestamp") from exc
    return parsed


def _require_mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    allowed: set[str],
    where: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"{where} has unknown field(s): {', '.join(unknown)}")


def _require_string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{where} must be a non-empty string")
    return value


def _require_digest(value: object, where: str) -> str:
    digest = _require_string(value, where)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ConfigurationError(f"{where} must be a lowercase SHA-256 digest")
    return digest


def _require_token(
    value: object,
    where: str,
    *,
    pattern: str = r"[a-z][a-z0-9-]{0,63}",
) -> str:
    token = _require_string(value, where)
    if re.fullmatch(pattern, token) is None:
        raise ConfigurationError(f"{where} has an invalid bounded value")
    return token


def _relative_path(value: str, where: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{where} must stay inside the repository")
    return path.as_posix()


def _confined_path(root: Path, relative: Path, where: str) -> Path:
    candidate = root / relative
    root_resolved = root.resolve()
    try:
        resolved_parent = candidate.parent.resolve()
    except OSError as exc:
        raise ConfigurationError(f"cannot resolve {where}") from exc
    if not resolved_parent.is_relative_to(root_resolved) or candidate.is_symlink():
        raise ConfigurationError(f"{where} must stay inside the repository")
    return candidate


def _require_string_list(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{where} must be a non-empty array")
    return [
        _require_string(item, f"{where}[{index}]")
        for index, item in enumerate(value)
    ]


def _require_count_pair(value: object, where: str) -> Mapping[str, int]:
    pair = _require_mapping(value, where)
    _require_exact_keys(pair, _COUNT_KEYS, where)
    numerator = pair.get("numerator")
    denominator = pair.get("denominator")
    if not isinstance(numerator, int) or numerator < 0:
        raise ConfigurationError(f"{where}.numerator must be a non-negative integer")
    if not isinstance(denominator, int) or denominator <= 0:
        raise ConfigurationError(f"{where}.denominator must be a positive integer")
    if numerator > denominator:
        raise ConfigurationError(f"{where}.numerator cannot exceed denominator")
    return {"numerator": numerator, "denominator": denominator}


def _rate(pair: Mapping[str, int]) -> float:
    return pair["numerator"] / pair["denominator"]


@dataclass(frozen=True)
class FeedbackConfig:
    enabled: bool
    installation_id: str
    sink: Mapping[str, str]
    retention_days: int
    max_records: int
    max_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": CONFIG_SCHEMA,
            "enabled": self.enabled,
            "installation_id": self.installation_id,
            "sink": dict(self.sink),
            "retention_days": self.retention_days,
            "max_records": self.max_records,
            "max_bytes": self.max_bytes,
        }


def load_feedback_config(root: Path) -> FeedbackConfig | None:
    path = _confined_path(root, CONFIG_PATH, "feedback configuration")
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read feedback configuration {path}") from exc
    data = _require_mapping(raw, "feedback configuration")
    _require_exact_keys(data, _CONFIG_KEYS, "feedback configuration")
    if data.get("schema") != CONFIG_SCHEMA:
        raise ConfigurationError(f"feedback configuration schema must be {CONFIG_SCHEMA}")
    if not isinstance(data.get("enabled"), bool):
        raise ConfigurationError("feedback configuration enabled must be a boolean")
    installation_id = _require_string(
        data.get("installation_id"),
        "feedback configuration installation_id",
    )
    try:
        uuid.UUID(installation_id)
    except ValueError as exc:
        raise ConfigurationError(
            "feedback configuration installation_id must be a UUID"
        ) from exc
    sink_raw = _require_mapping(data.get("sink"), "feedback configuration sink")
    kind = _require_string(sink_raw.get("kind"), "feedback configuration sink.kind")
    if kind not in {"local", "connected"}:
        raise ConfigurationError("feedback sink kind must be local or connected")
    sink: dict[str, str] = {"kind": kind}
    if kind == "local":
        _require_exact_keys(
            sink_raw,
            {"kind", "target"},
            "feedback configuration sink",
        )
        sink["target"] = _relative_path(
            _require_string(
                sink_raw.get("target"),
                "feedback configuration sink.target",
            ),
            "feedback configuration sink.target",
        )
    else:
        _require_exact_keys(
            sink_raw,
            {"kind", "endpoint", "token_env"},
            "feedback configuration sink",
        )
        endpoint = _require_string(
            sink_raw.get("endpoint"),
            "feedback configuration sink.endpoint",
        )
        if not endpoint.startswith("https://"):
            raise ConfigurationError("connected feedback endpoint must use HTTPS")
        sink["endpoint"] = endpoint
        sink["token_env"] = _require_string(
            sink_raw.get("token_env"),
            "feedback configuration sink.token_env",
        )
        if re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", sink["token_env"]) is None:
            raise ConfigurationError(
                "feedback configuration sink.token_env is invalid"
            )
    retention_days = data.get("retention_days")
    max_records = data.get("max_records")
    max_bytes = data.get("max_bytes")
    if not isinstance(retention_days, int) or not 1 <= retention_days <= 365:
        raise ConfigurationError("feedback retention_days must be between 1 and 365")
    if not isinstance(max_records, int) or not 1 <= max_records <= 100_000:
        raise ConfigurationError("feedback max_records must be between 1 and 100000")
    if not isinstance(max_bytes, int) or not 1_024 <= max_bytes <= 100 * 1024 * 1024:
        raise ConfigurationError(
            "feedback max_bytes must be between 1024 and 104857600"
        )
    return FeedbackConfig(
        enabled=bool(data["enabled"]),
        installation_id=installation_id,
        sink=sink,
        retention_days=retention_days,
        max_records=max_records,
        max_bytes=max_bytes,
    )


def enable_feedback(
    root: Path,
    *,
    sink: str,
    target: str | None = None,
    endpoint: str | None = None,
    token_env: str | None = None,
) -> FeedbackConfig:
    previous = load_feedback_config(root)
    installation_id = (
        previous.installation_id if previous is not None else str(uuid.uuid4())
    )
    if sink == "local":
        resolved_target = _relative_path(
            target or ".sourcebound/feedback/delivered",
            "feedback sink target",
        )
        sink_config = {
            "kind": "local",
            "target": resolved_target,
        }
    elif sink == "connected":
        if endpoint is None or token_env is None:
            raise ConfigurationError(
                "connected feedback requires --endpoint and --token-env"
            )
        if not endpoint.startswith("https://"):
            raise ConfigurationError("connected feedback endpoint must use HTTPS")
        sink_config = {
            "kind": "connected",
            "endpoint": endpoint,
            "token_env": token_env,
        }
    else:
        raise ConfigurationError("feedback sink must be local or connected")
    config = FeedbackConfig(
        enabled=True,
        installation_id=installation_id,
        sink=sink_config,
        retention_days=DEFAULT_RETENTION_DAYS,
        max_records=DEFAULT_MAX_RECORDS,
        max_bytes=DEFAULT_MAX_BYTES,
    )
    # Round-trip validation keeps the writer and reader on the same closed schema.
    atomic_write(
        _confined_path(root, CONFIG_PATH, "feedback configuration"),
        json.dumps(config.as_dict(), indent=2) + "\n",
    )
    return load_feedback_config(root) or config


def disable_feedback(root: Path) -> FeedbackConfig:
    config = load_feedback_config(root)
    if config is None:
        raise ConfigurationError("feedback is not configured")
    disabled = FeedbackConfig(
        enabled=False,
        installation_id=config.installation_id,
        sink=config.sink,
        retention_days=config.retention_days,
        max_records=config.max_records,
        max_bytes=config.max_bytes,
    )
    atomic_write(
        _confined_path(root, CONFIG_PATH, "feedback configuration"),
        json.dumps(disabled.as_dict(), indent=2) + "\n",
    )
    return disabled


def rotate_feedback_identity(root: Path) -> FeedbackConfig:
    config = load_feedback_config(root)
    if config is None:
        raise ConfigurationError("feedback is not configured")
    rotated = FeedbackConfig(
        enabled=config.enabled,
        installation_id=str(uuid.uuid4()),
        sink=config.sink,
        retention_days=config.retention_days,
        max_records=config.max_records,
        max_bytes=config.max_bytes,
    )
    atomic_write(
        _confined_path(root, CONFIG_PATH, "feedback configuration"),
        json.dumps(rotated.as_dict(), indent=2) + "\n",
    )
    return rotated


def _result_class(exit_code: int) -> str:
    return {
        0: "success",
        1: "drift",
        2: "invalid",
        3: "extraction-failed",
    }.get(exit_code, "failure")


def _repository_ref(root: Path) -> str:
    head = root / ".git/HEAD"
    try:
        value = head.read_text(encoding="utf-8").strip()
        if value.startswith("ref: "):
            ref_path = root / ".git" / value.removeprefix("ref: ")
            value = ref_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "WORKTREE"
    if len(value) == 40 and all(char in "0123456789abcdef" for char in value):
        return value
    return "WORKTREE"


def _repository_classes(root: Path) -> tuple[str, str]:
    file_count = 0
    markdown = False
    mdx = False
    excluded = {".git", ".sourcebound", ".venv", "node_modules"}
    try:
        for directory, directories, files in os.walk(root):
            directories[:] = [name for name in directories if name not in excluded]
            file_count += len(files)
            markdown = markdown or any(name.endswith(".md") for name in files)
            mdx = mdx or any(name.endswith(".mdx") for name in files)
            if file_count > 10_000:
                break
    except OSError:
        return "unknown", "unknown"
    size_class = (
        "small"
        if file_count < 100
        else "medium"
        if file_count < 1_000
        else "large"
        if file_count <= 10_000
        else "very-large"
    )
    adapter = (
        "mixed"
        if markdown and mdx
        else "mdx"
        if mdx
        else "markdown"
        if markdown
        else "none"
    )
    return adapter, size_class


def build_feedback_envelope(
    root: Path,
    config: FeedbackConfig,
    *,
    command: str,
    exit_code: int,
    execution_policy: str,
    outcome: str | None = None,
) -> dict[str, object]:
    adapter, repository_size_class = _repository_classes(root)
    run_id = _sha256(uuid.uuid4().bytes)
    outcome_material = {
        "run_id": run_id,
        "product_version": __version__,
        "repository_ref": _repository_ref(root),
        "command": command,
        "exit_code": exit_code,
        "execution_policy": execution_policy,
    }
    outcome_id = _sha256(_canonical_json(outcome_material).encode())
    event_id = _sha256(f"{config.installation_id}:{run_id}".encode())
    envelope: dict[str, object] = {
        "schema": ENVELOPE_SCHEMA,
        "event_id": event_id,
        "run_id": run_id,
        "outcome_id": outcome_id,
        "occurred_at": _utc_now(),
        "product_version": __version__,
        "installation_id": config.installation_id,
        "command": command,
        "exit_code": exit_code,
        "result_class": _result_class(exit_code),
        "execution_policy": execution_policy,
        "adapter": adapter,
        "repository_size_class": repository_size_class,
    }
    if outcome is not None:
        envelope["outcome"] = outcome
    return envelope


def _outbox_records(root: Path) -> list[Path]:
    directory = _confined_path(root, OUTBOX_DIR, "feedback outbox")
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if path.suffix == ".json")


def _prune_feedback_state(root: Path, config: FeedbackConfig) -> None:
    cutoff = time.time() - config.retention_days * 86_400
    directories = [
        _confined_path(root, OUTBOX_DIR, "feedback outbox"),
        _confined_path(root, DEAD_LETTER_DIR, "feedback dead-letter directory"),
        _confined_path(root, ATTEMPTS_DIR, "feedback attempts directory"),
    ]
    if config.sink["kind"] == "local":
        directories.append(
            _confined_path(
                root,
                Path(config.sink["target"]),
                "local feedback sink",
            )
        )
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue


def enqueue_feedback(
    root: Path,
    *,
    command: str,
    exit_code: int,
    execution_policy: str,
    outcome: str | None = None,
) -> Path | None:
    config = load_feedback_config(root)
    if config is None or not config.enabled:
        return None
    _prune_feedback_state(root, config)
    envelope = build_feedback_envelope(
        root,
        config,
        command=command,
        exit_code=exit_code,
        execution_policy=execution_policy,
        outcome=outcome,
    )
    event_id = str(envelope["event_id"])
    path = _confined_path(
        root,
        OUTBOX_DIR / f"{event_id}.json",
        "feedback outbox record",
    )
    if path.is_file():
        return path
    payload = _canonical_json(envelope)
    records = [
        *_outbox_records(root),
        *sorted(
            _confined_path(
                root,
                DEAD_LETTER_DIR,
                "feedback dead-letter directory",
            ).glob("*.json")
        ),
    ]
    total_bytes = sum(record.stat().st_size for record in records)
    if len(records) >= config.max_records:
        raise ConfigurationError("feedback outbox record quota reached")
    if total_bytes + len(payload.encode()) > config.max_bytes:
        raise ConfigurationError("feedback outbox byte quota reached")
    atomic_write(path, payload)
    return path


def preview_feedback(root: Path) -> bytes:
    records = _outbox_records(root)
    return b"".join(record.read_bytes() for record in records)


def _validate_envelope_bytes(payload: bytes) -> Mapping[str, Any]:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ConfigurationError("feedback envelope is invalid JSON") from exc
    envelope = _require_mapping(raw, "feedback envelope")
    allowed_keys = _ENVELOPE_KEYS - {"outcome"}
    if "outcome" in envelope:
        allowed_keys = _ENVELOPE_KEYS
    _require_exact_keys(envelope, allowed_keys, "feedback envelope")
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        raise ConfigurationError(f"feedback envelope schema must be {ENVELOPE_SCHEMA}")
    event_id = _require_digest(envelope.get("event_id"), "feedback envelope event_id")
    run_id = _require_digest(envelope.get("run_id"), "feedback envelope run_id")
    _require_digest(envelope.get("outcome_id"), "feedback envelope outcome_id")
    installation_id = _require_string(
        envelope.get("installation_id"),
        "feedback envelope installation_id",
    )
    try:
        uuid.UUID(installation_id)
    except ValueError as exc:
        raise ConfigurationError(
            "feedback envelope installation_id must be a UUID"
        ) from exc
    if event_id != _sha256(f"{installation_id}:{run_id}".encode()):
        raise ConfigurationError("feedback envelope event_id does not match its run")
    _parse_utc(envelope.get("occurred_at"), "feedback envelope occurred_at")
    _require_token(
        envelope.get("product_version"),
        "feedback envelope product_version",
        pattern=r"[0-9A-Za-z.+-]{1,32}",
    )
    _require_token(envelope.get("command"), "feedback envelope command")
    exit_code = envelope.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ConfigurationError("feedback envelope exit_code must be an integer")
    if envelope.get("result_class") != _result_class(exit_code):
        raise ConfigurationError("feedback envelope result_class does not match exit_code")
    if "outcome" in envelope and envelope["outcome"] not in {
        "accept", "parser-reject", "provider-failed",
    }:
        raise ConfigurationError("feedback envelope outcome is invalid")
    if envelope.get("execution_policy") not in {"trusted", "static-only"}:
        raise ConfigurationError("feedback envelope execution_policy is invalid")
    if envelope.get("adapter") not in {"none", "markdown", "mdx", "mixed", "unknown"}:
        raise ConfigurationError("feedback envelope adapter is invalid")
    if envelope.get("repository_size_class") not in {
        "small",
        "medium",
        "large",
        "very-large",
        "unknown",
    }:
        raise ConfigurationError("feedback envelope repository_size_class is invalid")
    return envelope


def _deliver_local(root: Path, config: FeedbackConfig, payload: bytes) -> None:
    envelope = _validate_envelope_bytes(payload)
    path = _confined_path(
        root,
        Path(config.sink["target"]) / f"{envelope['event_id']}.json",
        "local feedback event",
    )
    if path.is_file():
        return
    atomic_write(path, payload.decode())


def _deliver_connected(config: FeedbackConfig, payload: bytes) -> None:
    envelope = _validate_envelope_bytes(payload)
    deliver_event(
        endpoint=config.sink["endpoint"],
        token_env=config.sink["token_env"],
        envelope=envelope,
    )


def flush_feedback(root: Path) -> dict[str, int]:
    config = load_feedback_config(root)
    if config is None or not config.enabled:
        raise ConfigurationError("feedback delivery is disabled")
    _prune_feedback_state(root, config)
    delivered = 0
    duplicate = 0
    failed = 0
    for record in _outbox_records(root):
        payload = record.read_bytes()
        delivery_failed = False
        try:
            if config.sink["kind"] == "local":
                target = _confined_path(
                    root,
                    Path(config.sink["target"]) / record.name,
                    "local feedback event",
                )
                existed = target.is_file()
                _deliver_local(root, config, payload)
                duplicate += int(existed)
            else:
                _deliver_connected(config, payload)
            record.unlink()
            _confined_path(
                root,
                ATTEMPTS_DIR / record.name,
                "feedback attempt record",
            ).unlink(missing_ok=True)
            delivered += 1
        except ConfigurationError:
            failed += 1
            delivery_failed = True
        if delivery_failed:
            attempts_path = _confined_path(
                root,
                ATTEMPTS_DIR / record.name,
                "feedback attempt record",
            )
            attempts = 0
            if attempts_path.is_file():
                try:
                    attempts = int(attempts_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    attempts = MAX_DELIVERY_ATTEMPTS
            attempts += 1
            if attempts >= MAX_DELIVERY_ATTEMPTS:
                dead_letter = _confined_path(
                    root,
                    DEAD_LETTER_DIR / record.name,
                    "feedback dead-letter record",
                )
                dead_letter.parent.mkdir(parents=True, exist_ok=True)
                record.replace(dead_letter)
                attempts_path.unlink(missing_ok=True)
            else:
                atomic_write(attempts_path, f"{attempts}\n")
    return {"delivered": delivered, "duplicates": duplicate, "failed": failed}


def validate_behavior_signal(payload: Mapping[str, Any]) -> dict[str, object]:
    _require_exact_keys(payload, _SIGNAL_KEYS, "behavior signal")
    if payload.get("schema") != SIGNAL_SCHEMA:
        raise ConfigurationError(f"behavior signal schema must be {SIGNAL_SCHEMA}")
    signal_id = _require_digest(payload.get("signal_id"), "behavior signal signal_id")
    metric = _require_mapping(payload.get("metric"), "behavior signal metric")
    _require_exact_keys(metric, _METRIC_KEYS, "behavior signal metric")
    direction = _require_string(
        metric.get("direction"),
        "behavior signal metric.direction",
    )
    if direction not in {"higher-is-better", "lower-is-better"}:
        raise ConfigurationError(
            "behavior signal metric.direction must be higher-is-better or lower-is-better"
        )
    normalized_metric = {
        "name": _require_string(metric.get("name"), "behavior signal metric.name"),
        "version": _require_string(
            metric.get("version"),
            "behavior signal metric.version",
        ),
        "direction": direction,
    }
    window = _require_mapping(payload.get("window"), "behavior signal window")
    _require_exact_keys(window, _WINDOW_KEYS, "behavior signal window")
    start = _parse_utc(window.get("start"), "behavior signal window.start")
    end = _parse_utc(window.get("end"), "behavior signal window.end")
    if start >= end:
        raise ConfigurationError("behavior signal window.start must precede window.end")
    normalized_window = {
        "start": str(window["start"]),
        "end": str(window["end"]),
    }
    counts = dict(_require_count_pair(payload.get("counts"), "behavior signal counts"))
    segment = _require_mapping(payload.get("segment"), "behavior signal segment")
    _require_exact_keys(segment, _SEGMENT_KEYS, "behavior signal segment")
    scope = _require_string(segment.get("scope"), "behavior signal segment.scope")
    if scope not in {"installation", "cross-installation"}:
        raise ConfigurationError(
            "behavior signal segment.scope must be installation or cross-installation"
        )
    installations = segment.get("installations")
    contributing = segment.get("contributing_installations")
    if not isinstance(installations, int) or installations <= 0:
        raise ConfigurationError(
            "behavior signal segment.installations must be a positive integer"
        )
    if (
        not isinstance(contributing, int)
        or contributing <= 0
        or contributing > installations
    ):
        raise ConfigurationError(
            "behavior signal segment.contributing_installations must be positive "
            "and cannot exceed installations"
        )
    if scope == "cross-installation" and contributing < 2:
        raise ConfigurationError(
            "cross-installation signals require at least two contributing installations"
        )
    normalized_segment = {
        "scope": scope,
        "installations": installations,
        "contributing_installations": contributing,
        "product_versions": _require_string_list(
            segment.get("product_versions"),
            "behavior signal segment.product_versions",
        ),
        "adapters": _require_string_list(
            segment.get("adapters"),
            "behavior signal segment.adapters",
        ),
        "execution_policies": _require_string_list(
            segment.get("execution_policies"),
            "behavior signal segment.execution_policies",
        ),
        "repository_size_classes": _require_string_list(
            segment.get("repository_size_classes"),
            "behavior signal segment.repository_size_classes",
        ),
    }
    data_quality = _require_string(
        payload.get("data_quality"),
        "behavior signal data_quality",
    )
    if data_quality not in {"complete", "partial"}:
        raise ConfigurationError(
            "behavior signal data_quality must be complete or partial"
        )
    privacy_class = _require_string(
        payload.get("privacy_class"),
        "behavior signal privacy_class",
    )
    if privacy_class != "aggregate":
        raise ConfigurationError("behavior signal privacy_class must be aggregate")
    evidence_class = _require_string(
        payload.get("evidence_class"),
        "behavior signal evidence_class",
    )
    if evidence_class not in {"independent-observation", "internal-regression"}:
        raise ConfigurationError(
            "behavior signal evidence_class must be independent-observation "
            "or internal-regression"
        )
    source_receipt = _require_mapping(
        payload.get("source_receipt"),
        "behavior signal source_receipt",
    )
    _require_exact_keys(
        source_receipt,
        _SOURCE_RECEIPT_KEYS,
        "behavior signal source_receipt",
    )
    normalized_source = {
        "schema": _require_string(
            source_receipt.get("schema"),
            "behavior signal source_receipt.schema",
        ),
        "sha256": _require_digest(
            source_receipt.get("sha256"),
            "behavior signal source_receipt.sha256",
        ),
    }
    contradictions_raw = payload.get("contradictory_evidence")
    if not isinstance(contradictions_raw, list):
        raise ConfigurationError(
            "behavior signal contradictory_evidence must be an array"
        )
    contradictions = [
        _require_digest(
            item,
            f"behavior signal contradictory_evidence[{index}]",
        )
        for index, item in enumerate(contradictions_raw)
    ]
    normalized_without_id: dict[str, object] = {
        "schema": SIGNAL_SCHEMA,
        "metric": normalized_metric,
        "window": normalized_window,
        "counts": counts,
        "segment": normalized_segment,
        "data_quality": data_quality,
        "privacy_class": privacy_class,
        "source_receipt": normalized_source,
        "contradictory_evidence": contradictions,
        "evidence_class": evidence_class,
    }
    expected_id = _sha256(_canonical_json(normalized_without_id).encode())
    if signal_id != expected_id:
        raise ConfigurationError(
            "behavior signal signal_id does not match its canonical content"
        )
    return {"signal_id": signal_id, **normalized_without_id}


def prepare_behavior_signal(payload: Mapping[str, Any]) -> dict[str, object]:
    body_keys = _SIGNAL_KEYS - {"signal_id"}
    _require_exact_keys(payload, body_keys, "behavior signal body")
    missing = sorted(body_keys - set(payload))
    if missing:
        raise ConfigurationError(
            f"behavior signal body is missing field(s): {', '.join(missing)}"
        )
    signal_id = _sha256(_canonical_json(payload).encode())
    return validate_behavior_signal({"signal_id": signal_id, **payload})


def load_behavior_signal(path: Path) -> tuple[dict[str, object], bytes]:
    try:
        payload_bytes = path.read_bytes()
        raw = json.loads(payload_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read behavior signal {path}") from exc
    payload = _require_mapping(raw, "behavior signal")
    return validate_behavior_signal(payload), payload_bytes


def ingest_behavior_signal(root: Path, path: Path) -> dict[str, object]:
    signal, _source_bytes = load_behavior_signal(path)
    signal_id = str(signal["signal_id"])
    stored_signal = _confined_path(
        root,
        SIGNALS_DIR / f"{signal_id}.json",
        "behavior signal record",
    )
    canonical_signal = _canonical_json(signal)
    if stored_signal.is_file() and stored_signal.read_text(encoding="utf-8") != canonical_signal:
        raise ConfigurationError("behavior signal id conflicts with stored bytes")
    atomic_write(stored_signal, canonical_signal)
    case_path = _confined_path(
        root,
        CASES_DIR / f"{signal_id}.json",
        "improvement case",
    )
    case: dict[str, object] = {
        "schema": CASE_SCHEMA,
        "case_id": signal_id,
        "signal_id": signal_id,
        "state": "observed",
        "evidence_class": signal["evidence_class"],
        "history": [{
            "state": "observed",
            "receipt_schema": SIGNAL_SCHEMA,
            "receipt_sha256": _sha256(canonical_signal.encode()),
        }],
    }
    if case_path.is_file():
        existing = json.loads(case_path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict) or existing.get("signal_id") != signal_id:
            raise ConfigurationError("improvement case conflicts with stored signal")
        return existing
    atomic_write(case_path, json.dumps(case, indent=2) + "\n")
    return case


def _stored_receipt_path(root: Path, case_id: str, state: str) -> Path:
    if state == "observed":
        relative = SIGNALS_DIR / f"{case_id}.json"
    else:
        relative = RECEIPTS_DIR / case_id / f"{state}.json"
    return _confined_path(root, relative, "improvement receipt")


def _validated_case_history(
    root: Path,
    case_id: str,
    current_state: str,
    history_raw: object,
) -> tuple[list[object], str]:
    if not isinstance(history_raw, list) or not history_raw:
        raise ConfigurationError("improvement case history must be a non-empty array")
    current_index = _CASE_STATES.index(current_state)
    expected_states = list(_CASE_STATES[: current_index + 1])
    observed_states: list[str] = []
    for index, entry_raw in enumerate(history_raw):
        entry = _require_mapping(
            entry_raw,
            f"improvement case history[{index}]",
        )
        _require_exact_keys(
            entry,
            {"state", "receipt_schema", "receipt_sha256"},
            f"improvement case history[{index}]",
        )
        observed_states.append(
            _require_string(
                entry.get("state"),
                f"improvement case history[{index}].state",
            )
        )
        receipt_schema = _require_string(
            entry.get("receipt_schema"),
            f"improvement case history[{index}].receipt_schema",
        )
        expected_schema = (
            SIGNAL_SCHEMA
            if observed_states[-1] == "observed"
            else _TRANSITION_RECEIPT_SCHEMAS.get(observed_states[-1])
        )
        if receipt_schema != expected_schema:
            raise ConfigurationError(
                f"improvement case history[{index}] has the wrong receipt schema"
            )
        receipt_digest = _require_digest(
            entry.get("receipt_sha256"),
            f"improvement case history[{index}].receipt_sha256",
        )
        receipt_path = _stored_receipt_path(root, case_id, observed_states[-1])
        try:
            stored_digest = _sha256(receipt_path.read_bytes())
        except OSError as exc:
            raise ConfigurationError(
                f"improvement case is missing receipt for {observed_states[-1]}"
            ) from exc
        if receipt_digest != stored_digest:
            raise ConfigurationError(
                f"improvement case receipt changed for {observed_states[-1]}"
            )
    if observed_states != expected_states:
        raise ConfigurationError(
            "improvement case history does not match its adjacent state sequence"
        )
    last = _require_mapping(history_raw[-1], "improvement case prior history")
    return history_raw, _require_digest(
        last.get("receipt_sha256"),
        "improvement case prior receipt_sha256",
    )


def _validate_prior_digest(
    receipt: Mapping[str, Any],
    expected: str,
    where: str,
) -> None:
    observed = _require_digest(
        receipt.get("prior_receipt_sha256"),
        f"{where} prior_receipt_sha256",
    )
    if observed != expected:
        raise ConfigurationError(f"{where} does not chain to the prior receipt")


def _validate_transition_receipt(
    receipt: Mapping[str, Any],
    *,
    target_state: str,
    signal_id: str,
    prior_receipt_sha256: str,
) -> None:
    if target_state == "reproduced":
        _require_exact_keys(receipt, _REPRODUCTION_KEYS, "reproduction receipt")
        if receipt.get("signal_id") != signal_id:
            raise ConfigurationError("reproduction receipt signal_id does not match the case")
        _require_digest(
            receipt.get("fixture_sha256"),
            "reproduction receipt fixture_sha256",
        )
        _require_digest(
            receipt.get("baseline_outcome_id"),
            "reproduction receipt baseline_outcome_id",
        )
        if receipt.get("reproduced") is not True:
            raise ConfigurationError("reproduction receipt must record reproduced: true")
        failure_class = _require_string(
            receipt.get("failure_class"),
            "reproduction receipt failure_class",
        )
        if failure_class not in {
            "tool-defect",
            "unsupported-surface",
            "configuration-defect",
            "proposal-defect",
            "user-abandonment",
        }:
            raise ConfigurationError("reproduction receipt failure_class is invalid")
        return
    if target_state == "root-cause-classified":
        _require_exact_keys(receipt, _ROOT_CAUSE_KEYS, "root-cause receipt")
        _validate_prior_digest(receipt, prior_receipt_sha256, "root-cause receipt")
        classification = _require_string(
            receipt.get("classification"),
            "root-cause receipt classification",
        )
        if classification not in {
            "tool-defect",
            "unsupported-surface",
            "configuration-defect",
            "proposal-defect",
            "user-abandonment",
        }:
            raise ConfigurationError("root-cause receipt classification is invalid")
        _require_digest(
            receipt.get("evidence_sha256"),
            "root-cause receipt evidence_sha256",
        )
        return
    if target_state == "evaluation-proposed":
        _require_exact_keys(
            receipt,
            _EVALUATION_PROPOSAL_KEYS,
            "evaluation proposal receipt",
        )
        _validate_prior_digest(
            receipt,
            prior_receipt_sha256,
            "evaluation proposal receipt",
        )
        for field in ("metric_sha256", "scorer_sha256", "threshold_sha256"):
            _require_digest(
                receipt.get(field),
                f"evaluation proposal receipt {field}",
            )
        _require_string_list(
            receipt.get("protected_segments"),
            "evaluation proposal receipt protected_segments",
        )
        return
    if target_state == "regression-added":
        _require_exact_keys(receipt, _REGRESSION_KEYS, "regression receipt")
        _validate_prior_digest(receipt, prior_receipt_sha256, "regression receipt")
        _require_digest(
            receipt.get("fixture_sha256"),
            "regression receipt fixture_sha256",
        )
        if receipt.get("demonstrated_red") is not True:
            raise ConfigurationError(
                "regression receipt must record demonstrated_red: true"
            )
        return
    if target_state == "shadow-measured":
        _validate_prior_digest(receipt, prior_receipt_sha256, "shadow evaluation")
        _validate_shadow_receipt(receipt)
        return
    if target_state == "candidate-change":
        _require_exact_keys(
            receipt,
            _CANDIDATE_CHANGE_KEYS,
            "candidate change receipt",
        )
        _validate_prior_digest(
            receipt,
            prior_receipt_sha256,
            "candidate change receipt",
        )
        _require_digest(
            receipt.get("change_sha256"),
            "candidate change receipt change_sha256",
        )
        _require_digest(
            receipt.get("regression_suite_sha256"),
            "candidate change receipt regression_suite_sha256",
        )
        return
    validate_verdict_payload(receipt)
    if receipt.get("state") != "ready" or receipt.get("ready") is not True:
        raise ConfigurationError("ordinary verified PR requires a ready verdict")


def _validate_shadow_receipt(receipt: Mapping[str, Any]) -> None:
    _require_exact_keys(receipt, _SHADOW_KEYS, "shadow evaluation receipt")
    if receipt.get("schema") != "sourcebound.shadow-evaluation.v1":
        raise ConfigurationError(
            "shadow evaluation receipt schema must be "
            "sourcebound.shadow-evaluation.v1"
        )
    _require_string(receipt.get("cohort_version"), "shadow evaluation cohort_version")
    direction = _require_string(
        receipt.get("direction"),
        "shadow evaluation direction",
    )
    if direction not in {"higher-is-better", "lower-is-better"}:
        raise ConfigurationError(
            "shadow evaluation direction must be higher-is-better or lower-is-better"
        )
    digest_pairs = (
        ("baseline_metric_digest", "candidate_metric_digest"),
        ("baseline_scorer_digest", "candidate_scorer_digest"),
        ("baseline_threshold_digest", "candidate_threshold_digest"),
    )
    for baseline_key, candidate_key in digest_pairs:
        baseline_digest = _require_digest(
            receipt.get(baseline_key),
            f"shadow evaluation {baseline_key}",
        )
        candidate_digest = _require_digest(
            receipt.get(candidate_key),
            f"shadow evaluation {candidate_key}",
        )
        if baseline_digest != candidate_digest:
            raise ConfigurationError(
                "shadow comparison changed its metric, scorer, or threshold"
            )
    baseline = _require_count_pair(
        receipt.get("baseline"),
        "shadow evaluation baseline",
    )
    candidate = _require_count_pair(
        receipt.get("candidate"),
        "shadow evaluation candidate",
    )
    improved = (
        _rate(candidate) > _rate(baseline)
        if direction == "higher-is-better"
        else _rate(candidate) < _rate(baseline)
    )
    if not improved:
        raise ConfigurationError("shadow candidate did not improve the aggregate metric")
    protected = receipt.get("protected_segments")
    if not isinstance(protected, list) or not protected:
        raise ConfigurationError(
            "shadow evaluation protected_segments must be a non-empty array"
        )
    for index, raw_segment in enumerate(protected):
        segment = _require_mapping(
            raw_segment,
            f"shadow evaluation protected_segments[{index}]",
        )
        _require_exact_keys(
            segment,
            _PROTECTED_SEGMENT_KEYS,
            f"shadow evaluation protected_segments[{index}]",
        )
        _require_string(
            segment.get("name"),
            f"shadow evaluation protected_segments[{index}].name",
        )
        segment_baseline = _require_count_pair(
            segment.get("baseline"),
            f"shadow evaluation protected_segments[{index}].baseline",
        )
        segment_candidate = _require_count_pair(
            segment.get("candidate"),
            f"shadow evaluation protected_segments[{index}].candidate",
        )
        regressed = (
            _rate(segment_candidate) < _rate(segment_baseline)
            if direction == "higher-is-better"
            else _rate(segment_candidate) > _rate(segment_baseline)
        )
        if regressed:
            raise ConfigurationError(
                "shadow candidate regressed a protected segment"
            )


def transition_improvement_case(
    root: Path,
    *,
    case_id: str,
    target_state: str,
    receipt_path: Path,
) -> dict[str, object]:
    _require_digest(case_id, "improvement case id")
    if target_state not in _CASE_STATES:
        raise ConfigurationError(f"unknown improvement state: {target_state}")
    path = _confined_path(
        root,
        CASES_DIR / f"{case_id}.json",
        "improvement case",
    )
    try:
        case_raw = json.loads(path.read_text(encoding="utf-8"))
        receipt_bytes = receipt_path.read_bytes()
        receipt_raw = json.loads(receipt_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError("cannot read improvement case or transition receipt") from exc
    case = _require_mapping(case_raw, "improvement case")
    receipt = _require_mapping(receipt_raw, "transition receipt")
    current_state = _require_string(case.get("state"), "improvement case state")
    history_raw, prior_receipt_sha256 = _validated_case_history(
        root,
        case_id,
        current_state,
        case.get("history"),
    )
    receipt_sha256 = _sha256(receipt_bytes)
    if current_state == target_state:
        last_history = _require_mapping(
            history_raw[-1],
            "improvement case current history",
        )
        if last_history.get("receipt_sha256") != receipt_sha256:
            raise ConfigurationError(
                "improvement case state already has a different receipt"
            )
        return dict(case)
    expected_index = _CASE_STATES.index(current_state) + 1
    if expected_index >= len(_CASE_STATES) or _CASE_STATES[expected_index] != target_state:
        raise ConfigurationError(
            f"improvement case must transition from {current_state} "
            f"to {_CASE_STATES[expected_index] if expected_index < len(_CASE_STATES) else 'none'}"
        )
    expected_schema = _TRANSITION_RECEIPT_SCHEMAS[target_state]
    if receipt.get("schema") != expected_schema:
        raise ConfigurationError(
            f"{target_state} requires receipt schema {expected_schema}"
        )
    signal_id = _require_digest(
        case.get("signal_id"),
        "improvement case signal_id",
    )
    _validate_transition_receipt(
        receipt,
        target_state=target_state,
        signal_id=signal_id,
        prior_receipt_sha256=prior_receipt_sha256,
    )
    stored_receipt = _stored_receipt_path(root, case_id, target_state)
    if stored_receipt.is_file() and stored_receipt.read_bytes() != receipt_bytes:
        raise ConfigurationError(
            f"improvement case already has conflicting {target_state} receipt bytes"
        )
    atomic_write(stored_receipt, receipt_bytes.decode())
    updated = dict(case)
    updated["state"] = target_state
    updated["history"] = [
        *history_raw,
        {
            "state": target_state,
            "receipt_schema": expected_schema,
            "receipt_sha256": receipt_sha256,
        },
    ]
    atomic_write(path, json.dumps(updated, indent=2) + "\n")
    return updated


def purge_feedback(root: Path) -> None:
    state_path = root / STATE_DIR
    if state_path.is_symlink():
        state_path.unlink(missing_ok=True)
    else:
        shutil.rmtree(state_path, ignore_errors=True)
    config_path = root / CONFIG_PATH
    config_path.unlink(missing_ok=True)
