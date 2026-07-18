from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.verify_reader_trial import (
    ReaderTrialError,
    trial_layout,
    verify_reader_trial,
    verify_release_reader_trial,
)


ROOT = Path(__file__).parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_trial(
    root: Path,
    *,
    release_version: str = "1.0.0",
    candidate: str = "1.0.0rc9",
) -> Path:
    layout = trial_layout(release_version)
    rubric_path = root / layout.rubric
    rubric_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / layout.rubric, rubric_path)
    rubric_bytes = rubric_path.read_bytes()
    rubric = yaml.safe_load(rubric_bytes)
    context = []
    for relative in rubric["context"]:
        document = root / relative
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(f"# {relative}\n\nPublished reader context.\n")
        context.append({"path": relative, "sha256": _sha256(document.read_bytes())})

    participants = []
    for profile in rubric["profiles"]:
        profile_id = profile["id"]
        tasks = []
        for task in rubric["tasks"]:
            relative = layout.evidence_root / profile_id / f"{task['id']}.txt"
            evidence = root / relative
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(f"{profile_id} passed {task['id']} using published docs only\n")
            tasks.append({
                "id": task["id"],
                "ok": True,
                "evidence": relative.as_posix(),
                "sha256": _sha256(evidence.read_bytes()),
            })
        participants.append({
            "id": f"reader-{profile_id}",
            "profile": profile_id,
            "independent": True,
            "context": "published-docs-only",
            "completed_at": "2026-07-14T12:00:00Z",
            "tasks": tasks,
        })
    receipt = {
        "schema": "clean-docs.independent-reader-trial.v2",
        "candidate": candidate,
        "candidate_commit": "a" * 40,
        "candidate_artifact_sha256": "b" * 64,
        "rubric_sha256": _sha256(rubric_bytes),
        "context": context,
        "participants": participants,
    }
    receipt_path = root / layout.receipt
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt_path


def test_reader_trial_binds_rubric_context_participants_and_task_evidence(
    tmp_path: Path,
) -> None:
    receipt = _write_trial(tmp_path)

    summary = verify_reader_trial(tmp_path, "1.0.0")

    assert summary["candidate"] == "1.0.0rc9"
    assert summary["participants"] == {
        "anthropic-opus-4-8": 1,
        "anthropic-sonnet-5": 1,
        "codex-gpt-5-5-high": 1,
        "codex-gpt-5-6-sol-high": 1,
    }
    assert summary["tasks_per_participant"] == 5
    assert summary["receipt_sha256"] == _sha256(receipt.read_bytes())


def test_version_11_reader_trial_uses_two_families_and_learning_tasks(tmp_path: Path) -> None:
    receipt = _write_trial(
        tmp_path,
        release_version="1.1.0",
        candidate="1.1.0rc1",
    )

    summary = verify_reader_trial(tmp_path, "1.1.0")

    assert summary["candidate"] == "1.1.0rc1"
    assert summary["participants"] == {
        "anthropic-opus-4-8": 1,
        "codex-gpt-5-6-sol-high": 1,
    }
    assert summary["tasks_per_participant"] == 5
    assert summary["receipt_path"] == ".clean-docs/reader-trial-v1.1.json"
    assert summary["evidence_root"] == ".clean-docs/reader-trials-v1.1"
    assert summary["receipt_sha256"] == _sha256(receipt.read_bytes())


def test_version_11_runnable_context_includes_tutorial_prerequisites() -> None:
    rubric = yaml.safe_load(
        (ROOT / ".clean-docs/reader-trial-rubric-v1.1.yml").read_text()
    )
    tutorial = Path("docs/learn/tutorial-catch-a-lying-doc.md")
    content = (ROOT / tutorial).read_text()
    prerequisites = content.split("## Before you begin", maxsplit=1)[1].split(
        "\n## ", maxsplit=1
    )[0]
    linked_pages = {
        (
            (ROOT / tutorial.parent / match.split("#", maxsplit=1)[0])
            .resolve()
            .relative_to(ROOT)
            .as_posix()
        )
        for match in re.findall(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)", prerequisites)
    }

    assert linked_pages
    assert linked_pages <= set(rubric["context"])


def test_reader_trial_rejects_tampered_or_incomplete_evidence(tmp_path: Path) -> None:
    receipt_path = _write_trial(tmp_path)
    receipt = json.loads(receipt_path.read_text())
    evidence = tmp_path / receipt["participants"][0]["tasks"][0]["evidence"]
    evidence.write_text("changed after the trial\n")

    with pytest.raises(ReaderTrialError, match="digest does not match"):
        verify_reader_trial(tmp_path, "1.0.0")

    receipt = json.loads(receipt_path.read_text())
    first_task = receipt["participants"][0]["tasks"][0]["id"]
    profile = receipt["participants"][0]["profile"]
    evidence.write_text(f"{profile} passed {first_task} using published docs only\n")
    receipt["participants"] = receipt["participants"][:-1]
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ReaderTrialError, match="every model profile"):
        verify_reader_trial(tmp_path, "1.0.0")


def test_reader_trial_rejects_evidence_outside_its_declared_directory(
    tmp_path: Path,
) -> None:
    receipt_path = _write_trial(tmp_path)
    receipt = json.loads(receipt_path.read_text())
    result = receipt["participants"][0]["tasks"][0]
    result["evidence"] = "README.md"
    result["sha256"] = _sha256((tmp_path / "README.md").read_bytes())
    receipt_path.write_text(json.dumps(receipt))

    with pytest.raises(ReaderTrialError, match="must be under"):
        verify_reader_trial(tmp_path, "1.0.0")


def test_reader_trial_rejects_substituted_or_duplicate_model_profiles(
    tmp_path: Path,
) -> None:
    receipt_path = _write_trial(tmp_path)
    receipt = json.loads(receipt_path.read_text())
    receipt["participants"][0]["profile"] = "undeclared-model"
    receipt_path.write_text(json.dumps(receipt))

    with pytest.raises(ReaderTrialError, match="undeclared profile"):
        verify_reader_trial(tmp_path, "1.0.0")

    receipt_path = _write_trial(tmp_path)
    receipt = json.loads(receipt_path.read_text())
    receipt["participants"][0]["profile"] = receipt["participants"][1]["profile"]
    receipt_path.write_text(json.dumps(receipt))

    with pytest.raises(ReaderTrialError, match="every model profile"):
        verify_reader_trial(tmp_path, "1.0.0")


def test_stable_release_requires_reader_trial_while_candidate_build_does_not(
    tmp_path: Path,
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "fixture"\nversion = "1.0.0rc9"\n')
    assert verify_release_reader_trial(tmp_path) == {"required": False}

    project.write_text('[project]\nname = "fixture"\nversion = "1.0.0"\n')
    rubric = tmp_path / ".clean-docs/reader-trial-rubric.yml"
    rubric.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / ".clean-docs/reader-trial-rubric.yml", rubric)
    with pytest.raises(ReaderTrialError, match="cannot read independent-reader receipt"):
        verify_release_reader_trial(tmp_path)

    _write_trial(tmp_path)
    summary = verify_release_reader_trial(tmp_path)
    assert summary["required"] is True
    assert set(summary["participants"]) == {
        "anthropic-opus-4-8",
        "anthropic-sonnet-5",
        "codex-gpt-5-5-high",
        "codex-gpt-5-6-sol-high",
    }


def test_candidate_gate_does_not_import_yaml(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "fixture"\nversion = "1.0.0rc9"\n')
    script = (
        "import json, pathlib, sys; "
        "sys.modules['yaml'] = None; "
        "from scripts.verify_reader_trial import verify_release_reader_trial; "
        "print(json.dumps(verify_release_reader_trial(pathlib.Path(sys.argv[1]))))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"required": False}
