from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import uuid

import pytest

from clean_docs import cli
from clean_docs.errors import ConfigurationError
from clean_docs.feedback import (
    CONFIG_PATH,
    DEAD_LETTER_DIR,
    OUTBOX_DIR,
    enable_feedback,
    enqueue_feedback,
    flush_feedback,
    load_feedback_config,
    preview_feedback,
    purge_feedback,
    ingest_behavior_signal,
    prepare_behavior_signal,
    transition_improvement_case,
    validate_behavior_signal,
)


def test_disabled_feedback_has_zero_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    network_attempts = 0

    def count_request(*_args: object, **_kwargs: object) -> None:
        nonlocal network_attempts
        network_attempts += 1

    monkeypatch.setattr("urllib.request.urlopen", count_request)

    assert enqueue_feedback(
        root,
        command="check",
        exit_code=0,
        execution_policy="static-only",
    ) is None

    assert not (root / ".sourcebound").exists()
    assert network_attempts == 0


def test_local_feedback_preview_flush_and_deduplication(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    config = enable_feedback(root, sink="local")

    first = enqueue_feedback(
        root,
        command="check",
        exit_code=1,
        execution_policy="static-only",
    )
    second = enqueue_feedback(
        root,
        command="check",
        exit_code=1,
        execution_policy="static-only",
    )

    assert first is not None
    assert second is not None
    assert first != second
    first_bytes = first.read_bytes()
    exact_pending_bytes = b"".join(
        path.read_bytes() for path in sorted((first, second))
    )
    assert preview_feedback(root) == exact_pending_bytes
    envelope = json.loads(first_bytes)
    assert set(envelope) == {
        "adapter",
        "command",
        "event_id",
        "execution_policy",
        "exit_code",
        "installation_id",
        "occurred_at",
        "outcome_id",
        "product_version",
        "repository_size_class",
        "result_class",
        "run_id",
        "schema",
    }
    assert envelope["installation_id"] == config.installation_id

    result = flush_feedback(root)

    assert result == {"delivered": 2, "duplicates": 0, "failed": 0}
    delivered = root / config.sink["target"] / first.name
    assert delivered.read_bytes() == first_bytes
    assert preview_feedback(root) == b""

    repeated = root / OUTBOX_DIR / delivered.name
    repeated.parent.mkdir(parents=True, exist_ok=True)
    repeated.write_bytes(delivered.read_bytes())
    repeated_result = flush_feedback(root)
    assert repeated_result == {"delivered": 1, "duplicates": 1, "failed": 0}


def test_disable_preserves_pending_but_removes_delivery_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert cli.main([
        "--root",
        str(root),
        "feedback",
        "enable",
        "--sink",
        "local",
    ]) == 0
    pending = enqueue_feedback(
        root,
        command="audit",
        exit_code=0,
        execution_policy="trusted",
    )
    assert pending is not None

    assert cli.main(["--root", str(root), "feedback", "disable"]) == 0

    assert pending.is_file()
    assert load_feedback_config(root).enabled is False  # type: ignore[union-attr]
    with pytest.raises(ConfigurationError, match="disabled"):
        flush_feedback(root)
    assert enqueue_feedback(
        root,
        command="audit",
        exit_code=0,
        execution_policy="trusted",
    ) is None


def test_feedback_failure_never_changes_gate_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Example\n\nA repository.\n", encoding="utf-8")
    expected_exit = cli._main(["--root", str(root), "audit"])

    def fail_capture(*_args: object, **_kwargs: object) -> None:
        raise ConfigurationError("outbox unavailable")

    monkeypatch.setattr(cli, "enqueue_feedback", fail_capture)

    assert cli.main(["--root", str(root), "audit"]) == expected_exit


def test_connected_delivery_is_explicit_and_dead_letters_after_three_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    enable_feedback(
        root,
        sink="connected",
        endpoint="https://example.invalid/capture",
        token_env="CLEAN_DOCS_TEST_TOKEN",
    )
    record = enqueue_feedback(
        root,
        command="verify",
        exit_code=0,
        execution_policy="trusted",
    )
    assert record is not None
    network_attempts = 0

    def fail_request(*_args: object, **_kwargs: object) -> None:
        nonlocal network_attempts
        network_attempts += 1
        raise OSError("offline")

    monkeypatch.setenv("CLEAN_DOCS_TEST_TOKEN", "test-token")
    monkeypatch.setattr("urllib.request.urlopen", fail_request)

    assert network_attempts == 0
    assert flush_feedback(root)["failed"] == 1
    assert flush_feedback(root)["failed"] == 1
    assert flush_feedback(root)["failed"] == 1
    assert network_attempts == 3
    assert not (root / OUTBOX_DIR / record.name).exists()
    assert (root / DEAD_LETTER_DIR / record.name).is_file()


def test_tampered_envelope_never_reaches_sink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    config = enable_feedback(root, sink="local")
    record = enqueue_feedback(
        root,
        command="verify",
        exit_code=0,
        execution_policy="trusted",
    )
    assert record is not None
    payload = json.loads(record.read_text(encoding="utf-8"))
    payload["event_id"] = "f" * 64
    record.write_text(json.dumps(payload), encoding="utf-8")

    result = flush_feedback(root)

    assert result["failed"] == 1
    delivered = root / config.sink["target"]
    assert not delivered.exists()


def test_connected_event_maps_idempotency_and_keeps_token_out_of_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    token = "project-token-value"
    enable_feedback(
        root,
        sink="connected",
        endpoint="https://events.example.test/capture",
        token_env="CLEAN_DOCS_TEST_TOKEN",
    )
    record = enqueue_feedback(
        root,
        command="check",
        exit_code=0,
        execution_policy="static-only",
    )
    assert record is not None
    outbox_bytes = record.read_bytes()
    monkeypatch.setenv("CLEAN_DOCS_TEST_TOKEN", token)
    captured: dict[str, object] = {}

    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return b"ok"

    def capture_request(request: object, *, timeout: int) -> Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", capture_request)

    result = flush_feedback(root)

    assert result == {"delivered": 1, "duplicates": 0, "failed": 0}
    request = captured["request"]
    wire = json.loads(request.data)  # type: ignore[attr-defined]
    assert wire["api_key"] == token
    assert wire["uuid"] == str(uuid.UUID(hex=wire["properties"]["event_id"][:32]))
    assert wire["properties"]["$process_person_profile"] is False
    state_bytes = (root / CONFIG_PATH).read_bytes()
    assert token.encode() not in state_bytes
    assert token.encode() not in outbox_bytes


def test_purge_removes_configuration_identifier_and_all_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    enable_feedback(root, sink="local")
    enqueue_feedback(
        root,
        command="check",
        exit_code=0,
        execution_policy="trusted",
    )

    purge_feedback(root)

    assert not (root / CONFIG_PATH).exists()
    assert not (root / ".sourcebound/feedback").exists()


def test_local_sink_cannot_escape_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(ConfigurationError, match="inside the repository"):
        enable_feedback(root, sink="local", target="../../outside")


def test_local_sink_symlink_cannot_escape_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "delivery").symlink_to(outside, target_is_directory=True)
    enable_feedback(root, sink="local", target="delivery")
    with pytest.raises(ConfigurationError, match="inside the repository"):
        enqueue_feedback(
            root,
            command="check",
            exit_code=0,
            execution_policy="trusted",
        )
    assert list(outside.iterdir()) == []


def test_retention_prunes_expired_outbox_records(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    enable_feedback(root, sink="local")
    expired = enqueue_feedback(
        root,
        command="check",
        exit_code=0,
        execution_policy="trusted",
    )
    assert expired is not None
    os.utime(expired, (0, 0))

    enqueue_feedback(
        root,
        command="audit",
        exit_code=0,
        execution_policy="trusted",
    )

    assert not expired.exists()


def _signal(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": "sourcebound.behavior-signal.v1",
        "metric": {
            "name": "successful_repair_rate",
            "version": "1",
            "direction": "higher-is-better",
        },
        "window": {
            "start": "2026-07-01T00:00:00Z",
            "end": "2026-07-08T00:00:00Z",
        },
        "counts": {"numerator": 8, "denominator": 10},
        "segment": {
            "scope": "cross-installation",
            "installations": 3,
            "contributing_installations": 2,
            "product_versions": ["1.2.0"],
            "adapters": ["markdown"],
            "execution_policies": ["static-only"],
            "repository_size_classes": ["small"],
        },
        "data_quality": "complete",
        "privacy_class": "aggregate",
        "source_receipt": {"schema": "controller.aggregate.v1", "sha256": "a" * 64},
        "contradictory_evidence": [],
        "evidence_class": "independent-observation",
    }
    body.update(overrides)
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode() + b"\n"
    return {"signal_id": hashlib.sha256(encoded).hexdigest(), **body}


def test_prepare_signal_adds_reproducible_content_id() -> None:
    signal = _signal()
    body = {key: value for key, value in signal.items() if key != "signal_id"}

    prepared = prepare_behavior_signal(body)

    assert prepared == signal


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_behavior_signal_requires_denominator_and_multiple_contributors() -> None:
    missing_denominator = _signal(counts={"numerator": 8})
    with pytest.raises(ConfigurationError, match="unknown field|denominator"):
        validate_behavior_signal(missing_denominator)

    noisy = _signal(segment={
        "scope": "cross-installation",
        "installations": 8,
        "contributing_installations": 1,
        "product_versions": ["1.2.0"],
        "adapters": ["markdown"],
        "execution_policies": ["static-only"],
        "repository_size_classes": ["small"],
    })
    with pytest.raises(ConfigurationError, match="two contributing"):
        validate_behavior_signal(noisy)


def test_signal_ingest_is_idempotent_and_cannot_skip_states(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    signal_path = root / "signal.json"
    _write_json(signal_path, _signal())

    first = ingest_behavior_signal(root, signal_path)
    second = ingest_behavior_signal(root, signal_path)

    assert first == second
    assert first["state"] == "observed"
    receipt = root / "regression.json"
    _write_json(receipt, {"schema": "sourcebound.regression-receipt.v1"})
    with pytest.raises(ConfigurationError, match="must transition"):
        transition_improvement_case(
            root,
            case_id=str(first["case_id"]),
            target_state="regression-added",
            receipt_path=receipt,
        )
    with pytest.raises(ConfigurationError, match="SHA-256"):
        transition_improvement_case(
            root,
            case_id="../../outside",
            target_state="reproduced",
            receipt_path=receipt,
        )


def _shadow_receipt(
    *,
    prior_receipt_sha256: str = "e" * 64,
    protected_candidate: tuple[int, int] = (9, 10),
    candidate_threshold_digest: str = "c" * 64,
) -> dict[str, object]:
    return {
        "schema": "sourcebound.shadow-evaluation.v1",
        "prior_receipt_sha256": prior_receipt_sha256,
        "cohort_version": "repair-v1",
        "direction": "higher-is-better",
        "baseline": {"numerator": 8, "denominator": 10},
        "candidate": {"numerator": 9, "denominator": 10},
        "protected_segments": [{
            "name": "static-only",
            "baseline": {"numerator": 8, "denominator": 10},
            "candidate": {
                "numerator": protected_candidate[0],
                "denominator": protected_candidate[1],
            },
        }],
        "baseline_metric_digest": "a" * 64,
        "candidate_metric_digest": "a" * 64,
        "baseline_scorer_digest": "b" * 64,
        "candidate_scorer_digest": "b" * 64,
        "baseline_threshold_digest": "c" * 64,
        "candidate_threshold_digest": candidate_threshold_digest,
    }


def _ready_verdict() -> dict[str, object]:
    unsigned: dict[str, object] = {
        "schema": "sourcebound.pr-verdict.v1",
        "state": "ready",
        "ready": True,
        "findings": [],
    }
    digest = hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {**unsigned, "digest": digest}


def _transition_receipt(
    state: str,
    *,
    signal_id: str,
    prior_receipt_sha256: str,
) -> dict[str, object]:
    if state == "reproduced":
        return {
            "schema": "sourcebound.reproduction.v1",
            "signal_id": signal_id,
            "fixture_sha256": "1" * 64,
            "baseline_outcome_id": "2" * 64,
            "reproduced": True,
            "failure_class": "tool-defect",
        }
    if state == "root-cause-classified":
        return {
            "schema": "sourcebound.root-cause.v1",
            "prior_receipt_sha256": prior_receipt_sha256,
            "classification": "tool-defect",
            "evidence_sha256": "3" * 64,
        }
    if state == "evaluation-proposed":
        return {
            "schema": "sourcebound.evaluation-proposal.v1",
            "prior_receipt_sha256": prior_receipt_sha256,
            "metric_sha256": "4" * 64,
            "scorer_sha256": "5" * 64,
            "threshold_sha256": "6" * 64,
            "protected_segments": ["static-only"],
        }
    if state == "regression-added":
        return {
            "schema": "sourcebound.regression-receipt.v1",
            "prior_receipt_sha256": prior_receipt_sha256,
            "fixture_sha256": "7" * 64,
            "demonstrated_red": True,
        }
    if state == "shadow-measured":
        return _shadow_receipt(prior_receipt_sha256=prior_receipt_sha256)
    if state == "candidate-change":
        return {
            "schema": "sourcebound.candidate-change.v1",
            "prior_receipt_sha256": prior_receipt_sha256,
            "change_sha256": "8" * 64,
            "regression_suite_sha256": "9" * 64,
        }
    return _ready_verdict()


def test_improvement_case_requires_every_receipted_transition(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    signal_path = root / "signal.json"
    _write_json(signal_path, _signal(evidence_class="internal-regression"))
    case = ingest_behavior_signal(root, signal_path)
    case_id = str(case["case_id"])
    transitions = [
        "reproduced",
        "root-cause-classified",
        "evaluation-proposed",
        "regression-added",
        "shadow-measured",
        "candidate-change",
        "ordinary-verified-pr",
    ]
    prior_receipt_sha256 = "0" * 64
    for index, state in enumerate(transitions):
        receipt = _transition_receipt(
            state,
            signal_id=case_id,
            prior_receipt_sha256=prior_receipt_sha256,
        )
        receipt_path = root / f"receipt-{index}.json"
        _write_json(receipt_path, receipt)
        case = transition_improvement_case(
            root,
            case_id=case_id,
            target_state=state,
            receipt_path=receipt_path,
        )
        assert case["state"] == state
        assert transition_improvement_case(
            root,
            case_id=case_id,
            target_state=state,
            receipt_path=receipt_path,
        ) == case
        prior_receipt_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    assert case["evidence_class"] == "internal-regression"
    assert len(case["history"]) == 8  # type: ignore[arg-type]


def test_improvement_case_rejects_a_changed_prior_receipt(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    signal_path = root / "signal.json"
    _write_json(signal_path, _signal())
    case = ingest_behavior_signal(root, signal_path)
    case_id = str(case["case_id"])
    reproduction = root / "reproduction.json"
    _write_json(
        reproduction,
        _transition_receipt(
            "reproduced",
            signal_id=case_id,
            prior_receipt_sha256="0" * 64,
        ),
    )
    transition_improvement_case(
        root,
        case_id=case_id,
        target_state="reproduced",
        receipt_path=reproduction,
    )
    stored = (
        root
        / ".sourcebound/feedback/receipts"
        / case_id
        / "reproduced.json"
    )
    stored.write_text('{"schema":"tampered"}', encoding="utf-8")
    root_cause = root / "root-cause.json"
    _write_json(
        root_cause,
        _transition_receipt(
            "root-cause-classified",
            signal_id=case_id,
            prior_receipt_sha256=hashlib.sha256(reproduction.read_bytes()).hexdigest(),
        ),
    )

    with pytest.raises(ConfigurationError, match="receipt changed"):
        transition_improvement_case(
            root,
            case_id=case_id,
            target_state="root-cause-classified",
            receipt_path=root_cause,
        )


@pytest.mark.parametrize(
    ("receipt", "message"),
    [
        (_shadow_receipt(protected_candidate=(7, 10)), "protected segment"),
        (_shadow_receipt(candidate_threshold_digest="d" * 64), "changed its metric"),
    ],
)
def test_shadow_measurement_rejects_regression_or_moving_scorer(
    tmp_path: Path,
    receipt: dict[str, object],
    message: str,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    signal_path = root / "signal.json"
    _write_json(signal_path, _signal())
    case = ingest_behavior_signal(root, signal_path)
    case_id = str(case["case_id"])
    prior_receipt_sha256 = "0" * 64
    for index, state in enumerate((
        "reproduced",
        "root-cause-classified",
        "evaluation-proposed",
        "regression-added",
    )):
        path = root / f"pre-{index}.json"
        _write_json(
            path,
            _transition_receipt(
                state,
                signal_id=case_id,
                prior_receipt_sha256=prior_receipt_sha256,
            ),
        )
        transition_improvement_case(
            root,
            case_id=case_id,
            target_state=state,
            receipt_path=path,
        )
        prior_receipt_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    shadow = root / "shadow.json"
    receipt["prior_receipt_sha256"] = prior_receipt_sha256
    _write_json(shadow, receipt)

    with pytest.raises(ConfigurationError, match=message):
        transition_improvement_case(
            root,
            case_id=case_id,
            target_state="shadow-measured",
            receipt_path=shadow,
        )
