from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from clean_docs.claims import extract_source_facts
from clean_docs.cli import main
from clean_docs.errors import ConfigurationError
from clean_docs.evaluation import run_evaluation
from clean_docs.sensitivity import (
    FACT_SCHEMA,
    PROPOSAL_SCHEMA,
    evaluate_binding_sensitivity,
)


def _commit(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "sensitivity fixture",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _fixture(tmp_path: Path, *, duplicate: bool = False) -> tuple[Path, str]:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    scope = "'scope': Field(), 'scope': Field()" if duplicate else "'scope': Field()"
    (root / "src/system.py").write_text(
        "ANNOTATIONS = Table("
        "name='annotations', "
        f"fields={{'id': Field(), {scope}}}"
        ")\n"
        "raise RuntimeError('target code must not execute')\n"
    )
    (root / "docs/reference.md").write_text(
        "# Reference\n\n"
        "## Annotations (`system.annotations`)\n\n"
        "### Columns\n\n"
        "Column | Type\n"
        "--- | ---\n"
        "`id` | text\n"
        "`scope` | text\n"
    )
    return root, _commit(root)


def _fact(root: Path, commit: str) -> dict[str, object]:
    source = (root / "src/system.py").read_text()
    observed = next(
        fact
        for fact in extract_source_facts("src/system.py", source)
        if fact.locator == "ANNOTATIONS.fields#keys"
    )
    return {
        "schema": FACT_SCHEMA,
        "repository_commit": commit,
        "selection_basis": "frozen-evaluation-fact",
        "kind": "identifier-set",
        "source": "src/system.py",
        "locator": "ANNOTATIONS.fields#keys",
        "member": "scope",
        "value_sha256": observed.digest,
    }


def _proposal(
    commit: str,
    *,
    doc: str = "docs/reference.md",
    anchor: str = "annotations-systemannotations",
    subject: str = "annotation",
) -> dict[str, object]:
    return {
        "schema": PROPOSAL_SCHEMA,
        "repository_commit": commit,
        "relationship": {
            "id": "annotation-columns",
            "kind": "identifier-set",
            "doc": doc,
            "anchor": anchor,
            "subject": subject,
            "source": "src/system.py",
            "locator": "ANNOTATIONS.fields#keys",
        },
    }


def _encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _run(
    root: Path,
    proposal: dict[str, object],
    fact: dict[str, object],
) -> dict[str, object]:
    proposal_bytes = _encoded(proposal)
    fact_bytes = _encoded(fact)
    return evaluate_binding_sensitivity(
        root,
        proposal,
        fact,
        proposal_bytes=proposal_bytes,
        fact_bytes=fact_bytes,
        expected_fact_file_sha256=hashlib.sha256(fact_bytes).hexdigest(),
    )


def test_static_identifier_relationship_becomes_sensitive_without_execution(
    tmp_path: Path,
) -> None:
    root, commit = _fixture(tmp_path)

    receipt = _run(root, _proposal(commit), _fact(root, commit))

    assert receipt["state"] == "sensitive"
    assert receipt["sensitive"] is True
    assert receipt["semantic_relationship_authorized"] is False
    assert receipt["execution"] == {
        "disposable_copy": True,
        "target_code_executed": False,
        "repository_commands_executed": False,
        "caller_files_written": 0,
    }
    assert receipt["repository"]["caller_worktree_unchanged"] is True
    assert receipt["repository"]["caller_repository_unchanged"] is True
    assert receipt["mutation"]["generator"] == "python-identifier-set-key@1"
    assert len(receipt["baseline"]["source_blob_id"]) == 40
    assert receipt["baseline"]["result"]["status"] == "current"
    assert receipt["mutated"]["result"]["status"] == "drift"
    assert subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout == ""


def test_wrong_semantic_relationship_can_be_sensitive_without_becoming_authorized(
    tmp_path: Path,
) -> None:
    root, commit = _fixture(tmp_path)
    (root / "docs/reference.md").write_text(
        "# Reference\n\n"
        "## Releases (`system.releases`)\n\n"
        "### Columns\n\n"
        "Column | Type\n"
        "--- | ---\n"
        "`id` | text\n"
        "`scope` | text\n"
    )
    commit = _commit_after_change(root)
    proposal = _proposal(
        commit,
        anchor="releases-systemreleases",
        subject="release",
    )

    receipt = _run(root, proposal, _fact(root, commit))

    assert receipt["state"] == "sensitive"
    assert receipt["semantic_relationship_authorized"] is False
    assert "depends" not in str(receipt["detail"]).lower()


def _commit_after_change(root: Path) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "change fixture",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def test_stale_baseline_is_invalid_and_never_mutated(tmp_path: Path) -> None:
    root, commit = _fixture(tmp_path)
    (root / "docs/reference.md").write_text(
        (root / "docs/reference.md").read_text().replace("`scope` | text\n", "")
    )
    commit = _commit_after_change(root)

    receipt = _run(root, _proposal(commit), _fact(root, commit))

    assert receipt["state"] == "invalid"
    assert receipt["sensitive"] is False
    assert receipt["mutation"] is None
    assert "baseline is drift" in receipt["detail"]


def test_ambiguous_duplicate_mapping_key_is_unsupported(tmp_path: Path) -> None:
    root, commit = _fixture(tmp_path, duplicate=True)

    receipt = _run(root, _proposal(commit), _fact(root, commit))

    assert receipt["state"] == "unsupported"
    assert receipt["sensitive"] is False
    assert receipt["mutation"] is None
    assert "exactly one mapping key" in receipt["detail"]


def test_stale_independent_fact_is_invalid(tmp_path: Path) -> None:
    root, commit = _fixture(tmp_path)
    fact = _fact(root, commit)
    fact["value_sha256"] = "0" * 64

    receipt = _run(root, _proposal(commit), fact)

    assert receipt["state"] == "invalid"
    assert receipt["mutation"] is None
    assert "frozen fact does not match" in receipt["detail"]


def test_dirty_caller_worktree_fails_before_disposable_mutation(
    tmp_path: Path,
) -> None:
    root, commit = _fixture(tmp_path)
    (root / "untracked.txt").write_text("caller work\n")

    with pytest.raises(
        ConfigurationError,
        match="requires a clean caller worktree",
    ):
        _run(root, _proposal(commit), _fact(root, commit))


def test_cli_requires_fact_digest_and_uses_state_exit_classes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, commit = _fixture(tmp_path)
    proposal_path = tmp_path / "proposal.json"
    fact_path = tmp_path / "fact.json"
    proposal_path.write_bytes(_encoded(_proposal(commit)))
    fact_path.write_bytes(_encoded(_fact(root, commit)))
    fact_digest = hashlib.sha256(fact_path.read_bytes()).hexdigest()

    assert main(
        [
            "--root",
            str(root),
            "binding",
            "sensitivity",
            "--proposal",
            str(proposal_path),
            "--fact",
            str(fact_path),
            "--fact-sha256",
            fact_digest,
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "clean-docs.binding-sensitivity.v1"
    assert payload["state"] == "sensitive"

    assert main(
        [
            "--root",
            str(root),
            "binding",
            "sensitivity",
            "--proposal",
            str(proposal_path),
            "--fact",
            str(fact_path),
            "--fact-sha256",
            "0" * 64,
        ]
    ) == 2
    assert "does not match" in capsys.readouterr().err


def test_cli_accepts_provider_proposal_on_standard_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, commit = _fixture(tmp_path)
    fact_path = tmp_path / "fact.json"
    fact_path.write_bytes(_encoded(_fact(root, commit)))
    fact_digest = hashlib.sha256(fact_path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(_encoded(_proposal(commit)).decode()),
    )

    assert main(
        [
            "--root",
            str(root),
            "binding",
            "sensitivity",
            "--proposal",
            "-",
            "--fact",
            str(fact_path),
            "--fact-sha256",
            fact_digest,
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "sensitive"


def test_evaluation_mutation_red_scorer_reuses_the_sensitivity_primitive(
    tmp_path: Path,
) -> None:
    evaluation_root = tmp_path / "evaluation"
    evaluation_root.mkdir()
    target, commit = _fixture(evaluation_root)
    proposal_bytes = _encoded(_proposal(commit))
    fact_bytes = _encoded(_fact(target, commit))
    (evaluation_root / "proposal.json").write_bytes(proposal_bytes)
    (evaluation_root / "fact.json").write_bytes(fact_bytes)
    (evaluation_root / "context.md").write_text(
        "# Relationship\n\nPropose the annotation column relationship as JSON.\n"
    )
    (evaluation_root / "source.txt").write_text("Evaluation fixture\n")
    (evaluation_root / "README.md").write_text(
        "# Evaluation\n\n"
        "<!-- clean-docs:purpose -->\n"
        "Use this fixture to replay a binding-sensitivity proposal. It gives the "
        "scorer one frozen target repository.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "<!-- clean-docs:begin overview -->\n"
        "Evaluation fixture\n"
        "<!-- clean-docs:end overview -->\n"
    )
    (evaluation_root / ".clean-docs.yml").write_text(
        "version: 1\n"
        "bindings:\n"
        "  - id: overview\n"
        "    type: region\n"
        "    doc: README.md\n"
        "    region: overview\n"
        "    extractor: file\n"
        "    source: {path: source.txt}\n"
        "    renderer: scalar\n"
    )
    (evaluation_root / "eval.yml").write_text(
        "version: 1\n"
        "tasks:\n"
        "  - id: relationship-sensitivity\n"
        "    audience: agent\n"
        "    prompt: Propose the frozen source relationship.\n"
        "    context: [context.md]\n"
        "    model:\n"
        "      adapter: recorded\n"
        "      name: fixture-provider\n"
        "      response: proposal.json\n"
        "    scorer:\n"
        "      type: mutation-red\n"
        "      repository: repo\n"
        "      fact: fact.json\n"
        f"      fact_sha256: {hashlib.sha256(fact_bytes).hexdigest()}\n"
        "      expected_state: sensitive\n"
    )

    report = run_evaluation(
        evaluation_root,
        evaluation_root / ".clean-docs.yml",
        evaluation_root / "eval.yml",
    )

    assert report.ok
    result = report.agent_tasks[0]
    assert result.scorer == "mutation-red"
    assert "semantic relationship remains unauthorized" in result.detail
    assert "receipt sha256=" in result.detail
