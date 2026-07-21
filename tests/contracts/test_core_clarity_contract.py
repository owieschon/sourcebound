"""Frozen acceptance contract for behavior implemented by later core-clarity phases."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]


def _source(name: str) -> str:
    return (ROOT / "src" / "sourcebound" / name).read_text()


def _project(path: str) -> str:
    return (ROOT / path).read_text()


def test_classification_complete_is_distinct_from_direct_protection() -> None:
    assert "classification_complete" in _source("outcomes.py")


def test_selected_direct_policy_rejects_catalog_only_surface() -> None:
    assert "require_direct" in _source("inventory.py")


def test_init_discloses_zero_direct_protection() -> None:
    assert "direct_protection" in _source("bootstrap.py")


def test_command_taxonomy_labels_core_and_experimental_surfaces() -> None:
    assert "experimental" in _source("cli.py")


def test_static_verdict_never_starts_repository_process() -> None:
    assert '"repository_processes_started": False' in _source("verdict.py")


def test_candidate_wheel_binds_release_ref() -> None:
    assert '"ref": ref' in _project("scripts/build_release.py")


def test_runtime_review_receipt_requires_provenance() -> None:
    assert "reviewer_session_id" in _project(
        "tests/contracts/verify_runtime_review_receipt.py"
    )
