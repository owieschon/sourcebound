from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml

from clean_docs import __version__
from clean_docs.doctor import diagnose


ROOT = Path(__file__).parents[1]


def test_doctor_accepts_self_hosted_repository() -> None:
    checks = diagnose(ROOT, ROOT / ".clean-docs.yml")
    assert all(check.ok for check in checks), checks


def test_doctor_reports_missing_command_executable(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "README.md").write_text("# Repo\n")
    manifest = root / ".clean-docs.yml"
    manifest.write_text("""\
version: 1
execution:
  commands: deny
  allowed_commands:
    missing:
      argv: [definitely-not-a-real-command]
      network: false
bindings:
  - id: count
    type: claim
    doc: README.md
    anchor: repo
    extractor: command
    command: missing
    assertion: {json_path: $.count, operator: equals, expected: 1}
""")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    checks = diagnose(root, manifest)

    assert next(check for check in checks if check.name == "command:missing").ok is False


def test_distribution_integrations_are_strict() -> None:
    hooks = yaml.safe_load((ROOT / ".pre-commit-hooks.yaml").read_text())
    assert {hook["entry"] for hook in hooks} == {"clean-docs audit", "clean-docs check"}
    assert all(hook["pass_filenames"] is False for hook in hooks)
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-clean-docs.yml").read_text())
    trigger = workflow[True]["workflow_call"]
    assert trigger["inputs"]["package-ref"]["required"] is True
    assert "40-character" in trigger["inputs"]["package-ref"]["description"]
    steps = workflow["jobs"]["clean-docs"]["steps"]
    setup_python = next(
        step for step in steps if step["uses"].startswith("actions/setup-python@")
    )
    assert setup_python["with"] == {"python-version": "3.12"}
    install = next(step for step in steps if step.get("name") == "Install pinned clean-docs")
    assert install["env"]["CLEAN_DOCS_PACKAGE_REF"] == "${{ inputs.package-ref }}"
    assert "full 40-character commit" in install["run"]
    assert "${{ inputs.package-ref }}" not in install["run"]
    gate = next(step for step in steps if step.get("name") == "Evaluate documentation gate")
    assert "clean-docs audit --format json > clean-docs-audit.json" in gate["run"]
    assert 'execution_args+=(--no-exec)' in gate["run"]
    assert 'if [ "$GITHUB_EVENT_NAME" = "pull_request" ]' in gate["run"]
    assert "clean-docs check \"${execution_args[@]}\"" in gate["run"]
    assert "clean-docs check --changed --base \"$base\" --head \"$head\"" in gate["run"]
    assert "--format sarif > clean-docs-changed.sarif" in gate["run"]
    annotations = next(
        step for step in steps if step.get("name") == "Publish changed-surface annotations"
    )
    assert "GITHUB_STEP_SUMMARY" in annotations["run"]
    assert "command_property" in annotations["run"]
    action_receipt = next(step for step in steps if step.get("name") == "Write action receipt")
    assert action_receipt["if"] == "always()"
    assert "clean-docs.action-run.v2" in action_receipt["run"]
    assert '"bindings_complete"' in action_receipt["run"]
    assert action_receipt["env"]["CLEAN_DOCS_REPOSITORY_SHA"] == "${{ github.sha }}"
    upload = next(step for step in steps if step.get("name") == "Upload clean-docs evidence")
    assert upload["if"] == "always()"
    assert upload["uses"] == (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert upload["with"]["if-no-files-found"] == "error"
    assert "clean-docs-*.sarif" in upload["with"]["path"]
    assert workflow[True]["workflow_call"]["inputs"]["base-ref"]["required"] is False
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-latest", "macos-latest"]
    assert matrix["python-version"] == ["3.10", "3.12", "3.14"]
    dogfood = ci["jobs"]["public-dogfood"]
    assert dogfood["needs"] == "test"
    assert dogfood["steps"][-2]["run"] == "python scripts/dogfood_public_repos.py"
    assert dogfood["steps"][-1]["run"] == "python scripts/dogfood_bootstrap_repos.py"
    acceptance = ci["jobs"]["acceptance-v0-1"]
    assert acceptance["needs"] == "test"
    receipt = acceptance["steps"][-1]
    assert receipt["if"] == "always()"
    assert receipt["with"]["if-no-files-found"] == "error"
    acceptance_v02 = ci["jobs"]["acceptance-v0-2"]
    assert acceptance_v02["needs"] == "test"
    run = acceptance_v02["steps"][-2]["run"]
    assert "--registry tests/v02-acceptance.yml" in run
    v02_receipt = acceptance_v02["steps"][-1]
    assert v02_receipt["if"] == "always()"
    assert v02_receipt["with"]["if-no-files-found"] == "error"
    acceptance_v03 = ci["jobs"]["acceptance-v0-3"]
    assert acceptance_v03["needs"] == "test"
    assert "--registry tests/v03-acceptance.yml" in acceptance_v03["steps"][-2]["run"]
    assert acceptance_v03["steps"][-1]["with"]["if-no-files-found"] == "error"


def test_reusable_action_writes_self_contained_evidence_receipt(tmp_path: Path) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-clean-docs.yml").read_text())
    receipt_step = next(
        step
        for step in workflow["jobs"]["clean-docs"]["steps"]
        if step.get("name") == "Write action receipt"
    )
    audit = tmp_path / "clean-docs-audit.json"
    check = tmp_path / "clean-docs-check.json"
    distribution = tmp_path / f"clean_docs-{__version__}.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: clean-docs\nVersion: {__version__}\n"
    )
    audit.write_text('{"ok":true,"findings":[]}\n')
    check.write_text('{"ok":true,"complete":true,"results":[]}\n')
    package_ref = "a" * 40
    source_sha = "b" * 40
    workflow_sha = "c" * 40
    environment = os.environ | {
        "CLEAN_DOCS_PACKAGE_REF": package_ref,
        "CLEAN_DOCS_REPOSITORY": "example/repository",
        "CLEAN_DOCS_REPOSITORY_REF": "refs/heads/main",
        "CLEAN_DOCS_REPOSITORY_SHA": source_sha,
        "CLEAN_DOCS_BASE_REF": "",
        "CLEAN_DOCS_HEAD_REF": "",
        "CLEAN_DOCS_EVENT": "workflow_dispatch",
        "CLEAN_DOCS_RUN_ID": "1234",
        "CLEAN_DOCS_RUN_ATTEMPT": "2",
        "CLEAN_DOCS_WORKFLOW_REF": "example/repository/.github/workflows/docs.yml@refs/heads/main",
        "CLEAN_DOCS_WORKFLOW_SHA": workflow_sha,
    }

    completed = subprocess.run(
        ["sh", "-c", receipt_step["run"]],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    receipt = json.loads((tmp_path / "clean-docs-run.json").read_text())
    assert receipt["schema"] == "clean-docs.action-run.v2"
    assert receipt["package"]["ref"] == package_ref
    assert receipt["package"]["version"] == __version__
    assert receipt["source"] == {
        "comparison": None,
        "repository": "example/repository",
        "ref": "refs/heads/main",
        "sha": source_sha,
    }
    assert receipt["run"] == {
        "attempt": 2,
        "event": "workflow_dispatch",
        "id": 1234,
        "workflow_ref": "example/repository/.github/workflows/docs.yml@refs/heads/main",
        "workflow_sha": workflow_sha,
    }
    assert receipt["results"] == {
        "audit": True,
        "bindings": True,
        "bindings_complete": True,
        "changed": None,
        "ok": True,
    }
    assert [item["path"] for item in receipt["evidence"]] == [
        "clean-docs-audit.json",
        "clean-docs-check.json",
    ]
    assert receipt["evidence"][0]["sha256"] == hashlib.sha256(audit.read_bytes()).hexdigest()

    environment["CLEAN_DOCS_BASE_REF"] = "1" * 40
    environment["CLEAN_DOCS_HEAD_REF"] = "2" * 40
    repeated = subprocess.run(
        ["sh", "-c", receipt_step["run"]],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert repeated.returncode == 0, repeated.stderr
    changed_receipt = json.loads((tmp_path / "clean-docs-run.json").read_text())
    assert changed_receipt["source"]["comparison"] == {
        "base": "1" * 40,
        "head": "2" * 40,
    }
    assert changed_receipt["results"]["ok"] is False


def test_reusable_action_rejects_non_commit_pin_before_install(tmp_path: Path) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-clean-docs.yml").read_text())
    install = next(
        step
        for step in workflow["jobs"]["clean-docs"]["steps"]
        if step.get("name") == "Install pinned clean-docs"
    )
    environment = os.environ | {"CLEAN_DOCS_PACKAGE_REF": "$(touch escaped)"}

    completed = subprocess.run(
        ["sh", "-c", install["run"]],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "full 40-character commit" in completed.stderr
    assert not (tmp_path / "escaped").exists()
