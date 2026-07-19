from __future__ import annotations

import json
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
