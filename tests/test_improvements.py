from __future__ import annotations

import json
import hashlib
from copy import deepcopy
import subprocess
from pathlib import Path

import pytest

from clean_docs.cli import main
from clean_docs.errors import ConfigurationError, PolicyError
from clean_docs.improvements import (
    CANDIDATES_SCHEMA,
    compile_improvement_candidates,
    initialize_candidate_lifecycle,
    LifecycleEvidence,
    load_candidate_lifecycle,
    load_review_candidates,
    transition_candidate_lifecycle,
    write_candidate_lifecycle,
)
from clean_docs.review_ledger import REVIEW_EVENT_LEDGER_SCHEMA, validate_review_event_ledger


def _test(kind: str = "fixture") -> dict[str, str]:
    return {
        "kind": kind,
        "setup": "Create the smallest repository that reproduces the observation.",
        "action": "Run the candidate check.",
        "passes_when": "The fixture fails before the change and passes after it.",
    }


def _payload() -> dict[str, object]:
    return {
        "schema": "clean-docs.review-observations.v1",
        "review_id": "published-docs-review",
        "repository_commit": "a" * 40,
        "source_urls": ["https://example.com/documentation-standard"],
        "observations": [
            {
                "id": "unreachable-task-page",
                "summary": "A task page has no incoming route from the documentation hub.",
                "evidence": [
                    {
                        "kind": "repository",
                        "source": "README.md",
                        "locator": "routing table",
                        "detail": "The task is absent from every reader route.",
                    }
                ],
                "documentation": {
                    "proposed_change": "Add the missing route to the canonical hub.",
                    "test": {
                        **_test("static-analysis"),
                        "passes_when": "Every declared task page is reachable from the hub.",
                    },
                },
                "product": {
                    "proposed_change": "Report unreachable declared reader pages as candidates.",
                    "test": _test(),
                },
            }
        ],
    }


def _repository(root: Path) -> str:
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Tests"], check=True)
    (root / "README.md").write_text("# Docs\n\nrouting table\n")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
def _receipt_payload(root: Path) -> dict[str, object]:
    payload = _payload()
    receipt = root / "receipt.json"
    receipt.write_text('{"count":9}\n')
    payload["observations"][0]["evidence"] = [{
        "kind": "receipt",
        "source": "receipt.json",
        "locator": "count",
        "detail": "The recorded count is reproducible from immutable receipt bytes.",
        "receipt": {
            "sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
            "producer_version": "clean-docs 1.2.0",
            "repository_commit": "a" * 40,
            "command": ["clean-docs", "audit", "--format", "json"],
        },
    }]
    return payload


def _ledger_event(
    *,
    event_id: str,
    observation_id: str,
    candidate_id: str | None,
    disposition: str = "candidate",
    successor: str | None = None,
    previous_digest: str | None = None,
) -> dict[str, object]:
    payload = {
        "id": event_id,
        "observation_id": observation_id,
        "disposition": disposition,
        "candidate_id": candidate_id,
        "successor": successor,
        "previous_digest": previous_digest,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {**payload, "digest": digest}


def _ledger(
    candidates,
    events: list[dict[str, object]] | None = None,
    *,
    schema: str = REVIEW_EVENT_LEDGER_SCHEMA,
    migration_base_head_digest: str | None = None,
) -> dict[str, object]:
    if events is None:
        events = []
        previous_digest = None
        for candidate in candidates.candidates:
            event = _ledger_event(
                event_id=f"event-{candidate.observation_id}",
                observation_id=candidate.observation_id,
                candidate_id=candidate.id,
                previous_digest=previous_digest,
            )
            events.append(event)
            previous_digest = event["digest"]
    root = {
        "schema": schema,
        "review_id": candidates.review_id,
        "events": events,
        "head_digest": events[-1]["digest"],
    }
    if schema == REVIEW_EVENT_LEDGER_SCHEMA:
        root["migration_base_head_digest"] = (
            migration_base_head_digest or "a" * 64
        )
    return root


def test_compiles_stable_dual_track_candidates_without_authority() -> None:
    first = compile_improvement_candidates(_payload())
    second = compile_improvement_candidates(_payload())

    assert first.as_dict() == second.as_dict()
    assert first.as_dict()["schema"] == CANDIDATES_SCHEMA
    assert len(first.candidates) == 1
    candidate = first.candidates[0]
    assert len(candidate.id) == 64
    assert [track.target for track in candidate.tracks] == [
        "documentation",
        "product",
    ]
    assert candidate.authority == "assessment"
    assert not candidate.gate_authority
    assert not candidate.change_authority
    assert first.as_dict()["authority"] == {
        "state": "assessment",
        "gate_authority": False,
        "change_authority": False,
        "next_step": (
            "Reproduce the observation and implement its proposed test before "
            "requesting an ordinary verified change."
        ),
    }


def test_review_event_ledger_rejects_deleted_duplicate_or_retargeted_candidates(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["observations"].append(deepcopy(payload["observations"][0]))
    payload["observations"][1]["id"] = "second-task-page"
    candidates = compile_improvement_candidates(payload)
    ledger_path = tmp_path / "events.json"
    ledger_path.write_text(json.dumps(_ledger(candidates)))
    assert validate_review_event_ledger(ledger_path, candidates)

    deleted_payload = deepcopy(payload)
    deleted_payload["observations"] = deleted_payload["observations"][1:]
    deleted = compile_improvement_candidates(deleted_payload)
    with pytest.raises(PolicyError, match="silently removed"):
        validate_review_event_ledger(ledger_path, deleted)

    duplicate = _ledger(candidates)
    duplicate["events"].append(duplicate["events"][0])
    duplicate["head_digest"] = duplicate["events"][-1]["digest"]
    ledger_path.write_text(json.dumps(duplicate))
    with pytest.raises(ConfigurationError, match="duplicate review event id"):
        validate_review_event_ledger(ledger_path, candidates)

    single_candidates = compile_improvement_candidates(_payload())
    retargeted = _ledger(single_candidates)
    event = retargeted["events"][0]
    assert isinstance(event, dict)
    event["candidate_id"] = "f" * 64
    event["digest"] = hashlib.sha256(
        json.dumps(
            {key: event[key] for key in event if key != "digest"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    retargeted["head_digest"] = event["digest"]
    ledger_path.write_text(json.dumps(retargeted))
    with pytest.raises(PolicyError, match="retargets"):
        validate_review_event_ledger(ledger_path, single_candidates)


def test_review_event_ledger_keeps_explicit_merged_history(tmp_path: Path) -> None:
    candidates = compile_improvement_candidates(_payload())
    candidate = candidates.candidates[0]
    first = _ledger_event(
        event_id="event-merged", observation_id="merged-observation", candidate_id=None,
        disposition="merged", successor=candidate.observation_id,
    )
    second = _ledger_event(
        event_id="event-current", observation_id=candidate.observation_id,
        candidate_id=candidate.id, previous_digest=first["digest"],
    )
    ledger_path = tmp_path / "events.json"
    ledger_path.write_text(json.dumps(_ledger(candidates, [first, second])))
    assert validate_review_event_ledger(ledger_path, candidates) == second["digest"]


def test_review_event_ledger_requires_the_base_history_as_an_exact_prefix(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["observations"].append(deepcopy(payload["observations"][0]))
    payload["observations"][1]["id"] = "second-task-page"
    candidates = compile_improvement_candidates(payload)
    base_path = tmp_path / "base.json"
    base_path.write_text(json.dumps(_ledger(candidates)))

    rewritten_payload = deepcopy(payload)
    rewritten_payload["observations"] = rewritten_payload["observations"][:1]
    rewritten_candidates = compile_improvement_candidates(rewritten_payload)
    rewritten_path = tmp_path / "rewritten.json"
    rewritten_path.write_text(json.dumps(_ledger(rewritten_candidates)))

    with pytest.raises(PolicyError, match="rewrites the immutable base history"):
        validate_review_event_ledger(
            rewritten_path, rewritten_candidates, prior_path=base_path
        )

    appended = _ledger(candidates)
    candidate = candidates.candidates[0]
    previous = appended["events"][-1]["digest"]
    appended["events"].append(
        _ledger_event(
            event_id="event-merged-observation",
            observation_id="merged-observation",
            candidate_id=None,
            disposition="merged",
            successor=candidate.observation_id,
            previous_digest=previous,
        )
    )
    appended["head_digest"] = appended["events"][-1]["digest"]
    appended_path = tmp_path / "appended.json"
    appended_path.write_text(json.dumps(appended))
    assert validate_review_event_ledger(
        appended_path, candidates, prior_path=base_path
    ) == appended["head_digest"]


def test_review_event_ledger_allows_one_explicit_legacy_migration_only(
    tmp_path: Path,
) -> None:
    legacy_schema = "clean-docs.review-event-ledger.v1"
    payload = _payload()
    payload["observations"].append(deepcopy(payload["observations"][0]))
    payload["observations"][1]["id"] = "second-task-page"
    candidates = compile_improvement_candidates(payload)
    legacy = _ledger(candidates, schema=legacy_schema)
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(legacy))

    rewritten_payload = deepcopy(payload)
    rewritten_payload["observations"] = rewritten_payload["observations"][:1]
    rewritten_candidates = compile_improvement_candidates(rewritten_payload)
    migrated = _ledger(
        rewritten_candidates,
        migration_base_head_digest=legacy["head_digest"],
    )
    migrated_path = tmp_path / "migrated.json"
    migrated_path.write_text(json.dumps(migrated))
    assert validate_review_event_ledger(
        migrated_path, rewritten_candidates, prior_path=legacy_path
    ) == migrated["head_digest"]

    rewritten_again_path = tmp_path / "rewritten-again.json"
    rewritten_again_path.write_text(json.dumps(_ledger(candidates)))
    with pytest.raises(PolicyError, match="rewrites the immutable base history"):
        validate_review_event_ledger(
            rewritten_again_path, candidates, prior_path=migrated_path
        )

    migrated["migration_base_head_digest"] = "f" * 64
    migrated_path.write_text(json.dumps(migrated))
    with pytest.raises(PolicyError, match="migration does not bind"):
        validate_review_event_ledger(
            migrated_path, rewritten_candidates, prior_path=legacy_path
        )

    stable_path = tmp_path / "stable.json"
    stable_path.write_text(json.dumps(_ledger(candidates)))
    downgraded_path = tmp_path / "downgraded.json"
    downgraded_path.write_text(json.dumps(_ledger(candidates, schema=legacy_schema)))
    with pytest.raises(PolicyError, match="cannot downgrade"):
        validate_review_event_ledger(
            downgraded_path, candidates, prior_path=stable_path
        )

    changed_anchor = _ledger(candidates, migration_base_head_digest="b" * 64)
    changed_anchor_path = tmp_path / "changed-anchor.json"
    changed_anchor_path.write_text(json.dumps(changed_anchor))
    with pytest.raises(PolicyError, match="rewrites its migration anchor"):
        validate_review_event_ledger(
            changed_anchor_path, candidates, prior_path=stable_path
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["observations"][0].pop("product"),
            "documentation, evidence, id, product, summary",
        ),
        (
            lambda payload: payload["observations"].append(
                dict(payload["observations"][0])
            ),
            "duplicate review observation id",
        ),
        (
            lambda payload: payload["observations"][0]["documentation"]["test"].update(
                {"kind": "opinion"}
            ),
            "must be one of",
        ),
    ],
)
def test_rejects_incomplete_or_untestable_observations(mutation, message: str) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(ConfigurationError, match=message):
        compile_improvement_candidates(payload)


def test_loaded_source_digest_binds_exact_review_bytes(tmp_path: Path) -> None:
    source = tmp_path / "review.json"
    source.write_text(json.dumps(_payload(), indent=2) + "\n")
    first = load_review_candidates(source)

    source.write_text(json.dumps(_payload(), separators=(",", ":")) + "\n")
    second = load_review_candidates(source)

    assert first.candidates == second.candidates
    assert first.source_sha256 != second.source_sha256
    assert first.digest != second.digest


def test_repository_evidence_is_grounded_at_the_pinned_commit(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    commit = _repository(root)
    payload = _payload()
    payload["repository_commit"] = commit
    source = tmp_path / "review.json"
    source.write_text(json.dumps(payload))

    ungrounded = load_review_candidates(source)
    assert "grounding" not in ungrounded.candidates[0].evidence[0]

    grounded = load_review_candidates(source, root=root)
    evidence = grounded.candidates[0].evidence[0]
    assert evidence["grounding"]["state"] == "grounded"
    assert evidence["grounding"]["commit"] == commit

    payload["observations"][0]["evidence"][0]["source"] = "MOVED.md"
    source.write_text(json.dumps(payload))
    moved = load_review_candidates(source, root=root)
    assert moved.candidates[0].evidence[0]["grounding"]["state"] == "unknown"

    payload["observations"][0]["evidence"][0]["source"] = "README.md"
    payload["observations"][0]["evidence"][0]["locator"] = "missing locator"
    source.write_text(json.dumps(payload))
    missing_locator = load_review_candidates(source, root=root)
    assert missing_locator.candidates[0].evidence[0]["grounding"]["state"] == "unknown"


def test_repository_evidence_rejects_abbreviated_or_unavailable_commits(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    commit = _repository(root)
    payload = _payload()
    payload["repository_commit"] = commit[:12]
    source = tmp_path / "review.json"
    source.write_text(json.dumps(payload))
    with pytest.raises(ConfigurationError, match="full lowercase SHA-1"):
        load_review_candidates(source, root=root)

    payload["repository_commit"] = "a" * 40
    source.write_text(json.dumps(payload))
    unavailable = load_review_candidates(source, root=root)
    assert unavailable.candidates[0].evidence[0]["grounding"]["state"] == "unknown"

    no_repository = load_review_candidates(source, root=tmp_path / "not-a-repository")
    assert no_repository.candidates[0].evidence[0]["grounding"]["state"] == "unknown"
def test_receipt_evidence_binds_bytes_command_and_repository_commit(tmp_path: Path) -> None:
    payload = _receipt_payload(tmp_path)

    candidates = compile_improvement_candidates(payload, root=tmp_path)

    receipt = candidates.candidates[0].evidence[0]["receipt"]
    assert receipt["state"] == "grounded"
    assert receipt["command"] == ["clean-docs", "audit", "--format", "json"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload, root: (root / "receipt.json").write_text('{"count":10}\n'),
            "does not match receipt bytes",
        ),
        (
            lambda payload, root: payload["observations"][0]["evidence"][0]["receipt"].update(
                {"repository_commit": "b" * 40}
            ),
            "must match the review commit",
        ),
        (
            lambda payload, root: payload["observations"][0]["evidence"][0].pop("receipt"),
            "must contain exactly",
        ),
    ],
)
def test_receipt_evidence_rejects_mutated_or_incomplete_context(
    tmp_path: Path, mutation, message: str
) -> None:
    payload = _receipt_payload(tmp_path)
    mutation(payload, tmp_path)

    with pytest.raises(ConfigurationError, match=message):
        compile_improvement_candidates(payload, root=tmp_path)


def test_missing_receipt_bytes_remain_unknown(tmp_path: Path) -> None:
    payload = _receipt_payload(tmp_path)
    grounded = compile_improvement_candidates(payload, root=tmp_path)
    (tmp_path / "receipt.json").unlink()

    candidates = compile_improvement_candidates(payload, root=tmp_path)

    assert candidates.candidates[0].evidence[0]["receipt"]["state"] == "unknown"
    assert candidates.candidates[0].id == grounded.candidates[0].id


def test_cli_writes_and_checks_candidate_set(tmp_path: Path, capsys) -> None:
    source = tmp_path / "review.json"
    source.write_text(json.dumps(_payload()))

    assert main([
        "--root",
        str(tmp_path),
        "review",
        "candidates",
        "--input",
        "review.json",
        "--out",
        ".clean-docs/candidates.json",
        "--format",
        "text",
    ]) == 0
    output = tmp_path / ".clean-docs/candidates.json"
    assert output.is_file()
    assert "[written] .clean-docs/candidates.json: 1 candidate(s)" in capsys.readouterr().out

    assert main([
        "--root",
        str(tmp_path),
        "review",
        "candidates",
        "--input",
        "review.json",
        "--out",
        ".clean-docs/candidates.json",
        "--check",
        "--format",
        "text",
    ]) == 0
    assert "[current] .clean-docs/candidates.json" in capsys.readouterr().out

    output.write_text("{}\n")
    assert main([
        "--root",
        str(tmp_path),
        "review",
        "candidates",
        "--input",
        "review.json",
        "--out",
        ".clean-docs/candidates.json",
        "--check",
        "--format",
        "text",
    ]) == 1
    assert "[drift] .clean-docs/candidates.json" in capsys.readouterr().out


def test_cli_requires_explicit_internal_output_for_check(tmp_path: Path, capsys) -> None:
    source = tmp_path / "review.json"
    source.write_text(json.dumps(_payload()))

    assert main([
        "--root",
        str(tmp_path),
        "review",
        "candidates",
        "--input",
        "review.json",
        "--check",
    ]) == 2
    assert "--check requires --out" in capsys.readouterr().err

    assert main([
        "--root",
        str(tmp_path),
        "review",
        "candidates",
        "--input",
        "review.json",
        "--out",
        str(tmp_path.parent / "outside.json"),
    ]) == 2
    assert "--out must stay inside" in capsys.readouterr().err


def test_lifecycle_tracks_adjacent_evidence_backed_transitions(tmp_path: Path) -> None:
    candidates = compile_improvement_candidates(_payload())
    initial = initialize_candidate_lifecycle(candidates)

    assert initial.as_dict()["authority"] == {
        "state": "assessment",
        "gate_authority": False,
        "change_authority": False,
        "next_step": (
            "Use linked evidence to record the candidate lifecycle; ordinary repository "
            "gates still decide whether a change is accepted."
        ),
    }
    assert initial.candidates[0].state == "proposed"

    reproduced = transition_candidate_lifecycle(
        initial,
        observation_id="unreachable-task-page",
        to_state="reproduced",
        evidence=LifecycleEvidence(
            kind="test-receipt",
            reference="tests/test_navigation.py::test_unreachable_task_page",
            detail="The fixture reproduces the missing route.",
        ),
    )
    record = reproduced.candidates[0]
    assert record.state == "reproduced"
    assert record.history[0].from_state == "proposed"
    assert record.history[0].evidence.kind == "test-receipt"

    path = tmp_path / "lifecycle.json"
    write_candidate_lifecycle(reproduced, path)
    assert load_candidate_lifecycle(path, candidates) == reproduced


def test_lifecycle_rejects_invalid_or_stale_transitions(tmp_path: Path) -> None:
    candidates = compile_improvement_candidates(_payload())
    initial = initialize_candidate_lifecycle(candidates)

    with pytest.raises(ConfigurationError, match="cannot transition"):
        transition_candidate_lifecycle(
            initial,
            observation_id="unreachable-task-page",
            to_state="verified",
            evidence=LifecycleEvidence(
                kind="test-receipt",
                reference="tests/test_navigation.py",
                detail="The fixture passes.",
            ),
        )
    with pytest.raises(ConfigurationError, match="cannot support transition to reproduced"):
        transition_candidate_lifecycle(
            initial,
            observation_id="unreachable-task-page",
            to_state="reproduced",
            evidence=LifecycleEvidence(
                kind="issue",
                reference="issue-42",
                detail="The issue names the reproduction.",
            ),
        )

    path = tmp_path / "lifecycle.json"
    write_candidate_lifecycle(initial, path)
    changed_payload = _payload()
    changed_payload["observations"][0]["summary"] = "The hub does not route to one task page."
    changed_candidates = compile_improvement_candidates(changed_payload)
    with pytest.raises(PolicyError, match="stale"):
        load_candidate_lifecycle(path, changed_candidates)


def test_cli_initializes_transitions_and_checks_lifecycle(tmp_path: Path, capsys) -> None:
    source = tmp_path / "review.json"
    source.write_text(json.dumps(_payload()))
    state = ".clean-docs/lifecycle.json"

    assert main([
        "--root", str(tmp_path), "review", "lifecycle", "init",
        "--input", "review.json", "--out", state, "--format", "text",
    ]) == 0
    assert "[written] .clean-docs/lifecycle.json: 1 candidate(s)" in capsys.readouterr().out

    assert main([
        "--root", str(tmp_path), "review", "lifecycle", "init",
        "--input", "review.json", "--out", state,
    ]) == 2
    assert "refuses to replace" in capsys.readouterr().err

    assert main([
        "--root", str(tmp_path), "review", "lifecycle", "transition",
        "--input", "review.json", "--state", state,
        "--observation", "unreachable-task-page", "--to", "reproduced",
        "--evidence-kind", "test-receipt", "--reference", "tests/test_navigation.py",
        "--detail", "The fixture reproduces the missing route.", "--format", "text",
    ]) == 0
    assert "[transitioned] unreachable-task-page: reproduced" in capsys.readouterr().out

    assert main([
        "--root", str(tmp_path), "review", "lifecycle", "check",
        "--input", "review.json", "--state", state, "--format", "text",
    ]) == 0
    assert "[current] .clean-docs/lifecycle.json" in capsys.readouterr().out
