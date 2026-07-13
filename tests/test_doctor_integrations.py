from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

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
    steps = workflow["jobs"]["clean-docs"]["steps"]
    gate = next(step for step in steps if step.get("name") == "Evaluate documentation gate")
    assert "clean-docs audit --format json > clean-docs-audit.json" in gate["run"]
    assert "clean-docs check --format json > clean-docs-check.json" in gate["run"]
    assert "clean-docs check --changed --base \"$base\" --head \"$head\"" in gate["run"]
    assert "--format sarif > clean-docs-changed.sarif" in gate["run"]
    annotations = next(
        step for step in steps if step.get("name") == "Publish changed-surface annotations"
    )
    assert "GITHUB_STEP_SUMMARY" in annotations["run"]
    assert "command_property" in annotations["run"]
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
