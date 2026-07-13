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
    assert any("clean-docs audit" == step.get("run") for step in steps)
    assert any("clean-docs check" == step.get("run") for step in steps)
