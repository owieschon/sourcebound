from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.evaluation import (
    DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    CommandResponseProvider,
    _command_environment,
    load_evaluation_tasks,
    run_evaluation,
    write_evaluation_history,
)
from clean_docs.manifest import load_manifest
from clean_docs.projections import write_projections


def test_command_environment_prefers_the_running_install() -> None:
    path = _command_environment()["PATH"].split(os.pathsep)
    assert path[0] == str(Path(sys.executable).parent)


def _manifest(command_output: str = "quickstart ok") -> str:
    return f"""\
version: 1
execution:
  commands: deny
  allowed_commands:
    install:
      argv: ["{{python}}", -c, "print('installed')"]
      timeout_seconds: 30
      network: false
    first-command:
      argv: ["{{python}}", -c, "print('{command_output}')"]
      timeout_seconds: 30
      network: false
bindings:
  - id: overview
    type: region
    doc: README.md
    region: overview
    extractor: file
    source: {{path: source.txt}}
    renderer: scalar
projections:
  bundles:
    - id: contributor
      output: .clean-docs/context/contributor.md
      include: [README.md]
"""


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    responses = root / ".clean-docs/responses"
    fixture = root / "fixture"
    responses.mkdir(parents=True)
    fixture.mkdir()
    (root / "source.txt").write_text("Bound overview\n")
    (root / "README.md").write_text(
        "# Fixture\n\n"
        "<!-- clean-docs:purpose -->\n"
        "Use this fixture when scoring repository documentation tasks. It gives evaluators one published context for every configured scorer.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "<!-- clean-docs:begin overview -->\nBound overview\n"
        "<!-- clean-docs:end overview -->\n\n"
        "## Quickstart\n\nRun the install command, then the first command.\n\n"
        "## Limits\n\nNetwork isolation belongs to the execution environment.\n"
    )
    (root / ".clean-docs.yml").write_text(_manifest())
    (fixture / "source.txt").write_text("Bound fixture\n")
    (fixture / "README.md").write_text(
        "# Target\n\n<!-- clean-docs:purpose -->\n"
        "Use this target when testing a generated manifest. It gives evaluators one source-bound fact to verify.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "<!-- clean-docs:begin fact -->\nBound fixture\n"
        "<!-- clean-docs:end fact -->\n"
    )
    (responses / "structured.json").write_text('{"command": "clean-docs check"}\n')
    (responses / "manifest.yml").write_text("""\
version: 1
bindings:
  - id: fact
    type: region
    doc: README.md
    region: fact
    extractor: file
    source: {path: source.txt}
    renderer: scalar
""")
    (responses / "limit.txt").write_text(
        "Network isolation belongs to the execution environment "
        "(README.md#limits).\n"
    )
    write_projections(root, load_manifest(root / ".clean-docs.yml"))
    tasks = {
        "version": 1,
        "tasks": [
            {
                "id": "human-quickstart",
                "audience": "human",
                "prompt": "Install the tool and run the first command.",
                "context": ["README.md"],
                "scorer": {
                    "type": "command",
                    "commands": [
                        {
                            "ref": "install",
                            "documented_as": "install command",
                            "exit_code": 0,
                            "stdout_contains": ["installed"],
                            "stderr_contains": [],
                        },
                        {
                            "ref": "first-command",
                            "documented_as": "first command",
                            "exit_code": 0,
                            "stdout_contains": ["quickstart ok"],
                            "stderr_contains": [],
                        },
                    ],
                },
            },
            {
                "id": "structured-command",
                "audience": "agent",
                "prompt": "Return the documented verification command as JSON.",
                "context": [".clean-docs/context/contributor.md"],
                "model": {
                    "adapter": "recorded",
                    "name": "fixture-agent",
                    "response": ".clean-docs/responses/structured.json",
                },
                "scorer": {
                    "type": "structured-output",
                    "expected": {"command": "clean-docs check"},
                },
            },
            {
                "id": "manifest-round-trip",
                "audience": "agent",
                "prompt": "Create a valid manifest binding for the fixture.",
                "context": [".clean-docs/context/contributor.md"],
                "model": {
                    "adapter": "recorded",
                    "name": "fixture-agent",
                    "response": ".clean-docs/responses/manifest.yml",
                },
                "scorer": {"type": "configuration", "repository": "fixture"},
            },
            {
                "id": "limitation-retrieval",
                "audience": "agent",
                "prompt": "Does the local process enforce network isolation?",
                "context": [".clean-docs/context/contributor.md"],
                "model": {
                    "adapter": "recorded",
                    "name": "fixture-agent",
                    "response": ".clean-docs/responses/limit.txt",
                },
                "scorer": {
                    "type": "cited-limit",
                    "answer": "Network isolation belongs to the execution environment",
                    "citation": "README.md#limits",
                    "forbidden": ["clean-docs enforces network isolation"],
                },
            },
        ],
    }
    (root / ".clean-docs/eval.yml").write_text(yaml.safe_dump(tasks, sort_keys=False))
    return root


def test_replay_scores_four_observable_task_types_and_writes_stable_history(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    report = run_evaluation(
        root,
        root / ".clean-docs.yml",
        root / ".clean-docs/eval.yml",
    )

    assert report.ok
    assert [result.id for result in report.human_tasks] == ["human-quickstart"]
    assert {result.scorer for result in report.agent_tasks} == {
        "structured-output", "configuration", "cited-limit",
    }
    assert {result.claim for result in report.agent_tasks} == {"deterministic-replay"}
    assert report.as_dict()["scores"] == {
        "human": {"passed": 1, "attempted": 1},
        "agent": {"passed": 3, "attempted": 3},
    }
    assert report.hygiene_findings == ()
    assert all(len(result.corpus_sha256) == 64 for result in report.agent_tasks)
    assert all(len(result.prompt_sha256) == 64 for result in report.agent_tasks)
    assert all(len(result.scorer_sha256) == 64 for result in report.agent_tasks)

    history = root / ".clean-docs/evaluation-history.json"
    write_evaluation_history(history, report)
    first = history.read_bytes()
    write_evaluation_history(history, report)
    assert history.read_bytes() == first
    records = json.loads(first)["records"]
    assert len(records) == 4
    assert all({
        "corpus_sha256", "model", "prompt_sha256", "scorer", "scorer_sha256",
        "ok", "record_id"
    } <= set(record) for record in records)


def test_recorded_replay_reproduces_the_same_report_without_provider_execution(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    first = run_evaluation(root, root / ".clean-docs.yml", root / ".clean-docs/eval.yml")
    second = run_evaluation(root, root / ".clean-docs.yml", root / ".clean-docs/eval.yml")
    assert first.as_dict() == second.as_dict()


def test_human_task_fails_when_the_command_is_absent_from_supplied_docs(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    readme = (root / "README.md").read_text().replace("install command", "setup step")
    (root / "README.md").write_text(readme)

    report = run_evaluation(
        root, root / ".clean-docs.yml", root / ".clean-docs/eval.yml"
    )

    assert not report.human_tasks[0].ok
    assert "absent from supplied docs" in report.human_tasks[0].detail


def test_live_provider_is_explicit_and_records_model_specific_output(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fixture_path = root / ".clean-docs/live.yml"
    fixture_path.write_text(yaml.safe_dump({
        "version": 1,
        "tasks": [{
            "id": "live-structured",
            "audience": "agent",
            "prompt": "Return the command.",
            "context": [".clean-docs/context/contributor.md"],
            "model": {
                "adapter": "command",
                "name": "local-provider",
                "argv": [sys.executable, "-c", "print('{\"command\": \"clean-docs check\"}')"],
                "timeout_seconds": 45,
            },
            "scorer": {
                "type": "structured-output",
                "expected": {"command": "clean-docs check"},
            },
        }],
    }, sort_keys=False))

    with pytest.raises(ConfigurationError, match="recorded response"):
        run_evaluation(root, root / ".clean-docs.yml", fixture_path)
    with pytest.raises(ConfigurationError, match="requires --record-dir"):
        run_evaluation(
            root, root / ".clean-docs.yml", fixture_path, mode="live"
        )

    record_dir = root / ".clean-docs/live-records"
    report = run_evaluation(
        root,
        root / ".clean-docs.yml",
        fixture_path,
        mode="live",
        record_dir=record_dir,
    )
    assert report.ok
    assert report.agent_tasks[0].claim == "model-specific-live"
    assert json.loads((record_dir / "live-structured.txt").read_text()) == {
        "command": "clean-docs check"
    }
    run_record = json.loads(
        (record_dir / "live-structured.run.json").read_text()
    )
    assert run_record["schema"] == "clean-docs.provider-run.v1"
    assert run_record["state"] == "completed"
    assert run_record["repository"]["worktree_before_sha256"] == (
        run_record["repository"]["worktree_after_sha256"]
    )
    assert run_record["response_sha256"]
    assert run_record["error"] is None
    assert run_record["inputs"]["prompt_bytes"] > 0
    assert run_record["provider"]["timeout_seconds"] == 45
    assert len(run_record["provider"]["configuration_sha256"]) == 64


def test_command_provider_deadline_changes_configuration_identity(
    tmp_path: Path,
) -> None:
    first = CommandResponseProvider(("provider",), "fixture", tmp_path, 30)
    second = CommandResponseProvider(("provider",), "fixture", tmp_path, 60)

    assert first.configuration_sha256 != second.configuration_sha256


def test_command_provider_uses_default_deadline_for_compatible_fixtures(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    tasks = load_evaluation_tasks(root / ".clean-docs/eval.yml")

    assert all(
        task.model is None
        or task.model.timeout_seconds == DEFAULT_PROVIDER_TIMEOUT_SECONDS
        for task in tasks
    )


@pytest.mark.parametrize("value", [0, -1, 3601, True, "120"])
def test_command_provider_rejects_invalid_deadline(
    tmp_path: Path, value: object
) -> None:
    path = tmp_path / "eval.yml"
    path.write_text(yaml.safe_dump({
        "version": 1,
        "tasks": [{
            "id": "invalid-timeout",
            "audience": "agent",
            "prompt": "Return a value.",
            "context": ["README.md"],
            "model": {
                "adapter": "command",
                "name": "provider",
                "argv": [sys.executable, "-c", "print('{}')"],
                "timeout_seconds": value,
            },
            "scorer": {"type": "structured-output", "expected": {}},
        }],
    }, sort_keys=False))

    with pytest.raises(
        ConfigurationError,
        match="timeout_seconds must be an integer from 1 to 3600",
    ):
        load_evaluation_tasks(path)


def test_live_provider_timeout_preserves_bounded_failed_receipt(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    fixture_path = root / ".clean-docs/live-timeout.yml"
    fixture_path.write_text(yaml.safe_dump({
        "version": 1,
        "tasks": [{
            "id": "live-timeout",
            "audience": "agent",
            "prompt": "Return the command.",
            "context": [".clean-docs/context/contributor.md"],
            "model": {
                "adapter": "command",
                "name": "slow-provider",
                "argv": [
                    sys.executable,
                    "-c",
                    "import time; time.sleep(2); print('{}')",
                ],
                "timeout_seconds": 1,
            },
            "scorer": {"type": "structured-output", "expected": {}},
        }],
    }, sort_keys=False))
    record_dir = root / ".clean-docs/live-timeout-records"

    with pytest.raises(ConfigurationError, match="timed out after 1 seconds"):
        run_evaluation(
            root,
            root / ".clean-docs.yml",
            fixture_path,
            mode="live",
            record_dir=record_dir,
        )

    run_record = json.loads(
        (record_dir / "live-timeout.run.json").read_text()
    )
    assert run_record["state"] == "failed"
    assert run_record["provider"]["timeout_seconds"] == 1
    assert run_record["inputs"]["prompt_bytes"] > 0
    assert run_record["response_sha256"] is None
    assert run_record["repository"]["worktree_before_sha256"] == (
        run_record["repository"]["worktree_after_sha256"]
    )
    assert not (record_dir / "live-timeout.txt").exists()


def test_live_provider_failure_preserves_pre_invocation_receipt(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    fixture_path = root / ".clean-docs/live-failure.yml"
    fixture_path.write_text(yaml.safe_dump({
        "version": 1,
        "tasks": [{
            "id": "live-failure",
            "audience": "agent",
            "prompt": "Return the command.",
            "context": [".clean-docs/context/contributor.md"],
            "model": {
                "adapter": "command",
                "name": "failing-provider",
                "argv": [sys.executable, "-c", "raise SystemExit(7)"],
            },
            "scorer": {
                "type": "structured-output",
                "expected": {"command": "clean-docs check"},
            },
        }],
    }, sort_keys=False))
    record_dir = root / ".clean-docs/live-failure-records"

    with pytest.raises(ConfigurationError, match="exited 7"):
        run_evaluation(
            root,
            root / ".clean-docs.yml",
            fixture_path,
            mode="live",
            record_dir=record_dir,
        )

    run_record = json.loads(
        (record_dir / "live-failure.run.json").read_text()
    )
    assert run_record["state"] == "failed"
    assert run_record["inputs"]["prompt_sha256"]
    assert run_record["repository"]["worktree_before_sha256"] == (
        run_record["repository"]["worktree_after_sha256"]
    )
    assert run_record["error"]["type"] == "ConfigurationError"
    assert "detail" not in run_record["error"]
    assert not (record_dir / "live-failure.txt").exists()


def test_live_provider_repository_write_becomes_conflict(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    fixture_path = root / ".clean-docs/live-conflict.yml"
    fixture_path.write_text(yaml.safe_dump({
        "version": 1,
        "tasks": [{
            "id": "live-conflict",
            "audience": "agent",
            "prompt": "Return the command.",
            "context": [".clean-docs/context/contributor.md"],
            "model": {
                "adapter": "command",
                "name": "writing-provider",
                "argv": [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        "Path('provider-write.txt').write_text('changed'); "
                        "print('{\"command\": \"clean-docs check\"}')"
                    ),
                ],
            },
            "scorer": {
                "type": "structured-output",
                "expected": {"command": "clean-docs check"},
            },
        }],
    }, sort_keys=False))
    record_dir = root / ".clean-docs/live-conflict-records"

    with pytest.raises(ConfigurationError, match="changed repository bytes"):
        run_evaluation(
            root,
            root / ".clean-docs.yml",
            fixture_path,
            mode="live",
            record_dir=record_dir,
        )

    run_record = json.loads(
        (record_dir / "live-conflict.run.json").read_text()
    )
    assert run_record["state"] == "conflict"
    assert run_record["repository"]["worktree_before_sha256"] != (
        run_record["repository"]["worktree_after_sha256"]
    )
    assert not (record_dir / "live-conflict.txt").exists()


def test_fixture_schema_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "eval.yml"
    path.write_text("""\
version: 1
tasks:
  - id: invalid-task
    audience: human
    prompt: Run it.
    context: [README.md]
    unknown: true
    scorer: {type: command, commands: []}
""")
    with pytest.raises(ConfigurationError, match="unknown key"):
        load_evaluation_tasks(path)
