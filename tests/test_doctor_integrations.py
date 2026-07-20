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
    checks = diagnose(ROOT, ROOT / ".sourcebound.yml")
    assert all(check.ok for check in checks), checks


def test_doctor_reports_missing_command_executable(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "README.md").write_text("# Repo\n\n1 command.\n")
    manifest = root / ".sourcebound.yml"
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
    assertion: {json_path: $.count, operator: equals, expected: 1, prose: 1 command.}
""")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    checks = diagnose(root, manifest)

    assert next(check for check in checks if check.name == "command:missing").ok is False


def test_distribution_integrations_are_strict() -> None:
    hooks = yaml.safe_load((ROOT / ".pre-commit-hooks.yaml").read_text())
    assert {hook["entry"] for hook in hooks} == {"sourcebound audit", "sourcebound check"}
    assert all(hook["pass_filenames"] is False for hook in hooks)
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-sourcebound.yml").read_text())
    trigger = workflow[True]["workflow_call"]
    assert trigger["inputs"]["package-ref"]["required"] is True
    assert "40-character" in trigger["inputs"]["package-ref"]["description"]
    steps = workflow["jobs"]["sourcebound"]["steps"]
    checkout = next(step for step in steps if step["uses"].startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["fetch-depth"] == 0
    setup_python = next(
        step for step in steps if step["uses"].startswith("actions/setup-python@")
    )
    assert setup_python["with"] == {"python-version": "3.12"}
    setup_node = next(
        step for step in steps if step["uses"].startswith("actions/setup-node@")
    )
    assert setup_node["with"] == {"node-version": "24"}
    install = next(step for step in steps if step.get("name") == "Install pinned sourcebound")
    assert install["env"]["SOURCEBOUND_PACKAGE_REF"] == "${{ inputs.package-ref }}"
    assert "full 40-character commit" in install["run"]
    assert "${{ inputs.package-ref }}" not in install["run"]
    comparison = next(
        step for step in steps if step.get("name") == "Resolve immutable comparison"
    )
    assert "checked-out commit" in comparison["run"]
    gate = next(step for step in steps if step.get("name") == "Evaluate one static verdict")
    assert gate["run"].count(
        'python3 -I -m clean_docs --root "$GITHUB_WORKSPACE" verdict'
    ) == 1
    assert "sourcebound check" not in gate["run"]
    assert "sourcebound audit" not in gate["run"]
    assert "sourcebound-verdict.exit" in gate["run"]
    render = next(
        step for step in steps if step.get("name") == "Render SARIF from the recorded verdict"
    )
    assert "render_verdict_payload_sarif" in render["run"]
    annotations = next(
        step for step in steps if step.get("name") == "Publish verdict annotations"
    )
    for step in (gate, render, annotations):
        assert step["env"]["SOURCEBOUND_EVIDENCE_DIR"] == (
            "${{ runner.temp }}/sourcebound-evidence"
        )
    assert "GITHUB_STEP_SUMMARY" in annotations["run"]
    assert "command_property" in annotations["run"]
    action_receipt = next(step for step in steps if step.get("name") == "Write action receipt")
    assert action_receipt["if"] == "always()"
    assert "sourcebound.action-run.v2" in action_receipt["run"]
    assert '"bindings_complete"' in action_receipt["run"]
    assert '"authoritative_evidence": "sourcebound-verdict.json"' in action_receipt["run"]
    assert action_receipt["env"]["SOURCEBOUND_REPOSITORY_SHA"] == (
        "${{ steps.comparison.outputs.head }}"
    )
    assert action_receipt["env"]["SOURCEBOUND_EVIDENCE_DIR"] == (
        "${{ runner.temp }}/sourcebound-evidence"
    )
    upload = next(step for step in steps if step.get("name") == "Upload sourcebound evidence")
    assert upload["if"] == "always()"
    assert upload["uses"] == (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["path"] == "${{ runner.temp }}/sourcebound-evidence"
    enforcement = next(
        step for step in steps if step.get("name") == "Enforce the recorded verdict"
    )
    assert enforcement["if"] == "always()"
    assert enforcement["env"]["SOURCEBOUND_EVIDENCE_DIR"] == (
        "${{ runner.temp }}/sourcebound-evidence"
    )
    assert "validate_verdict_payload" in enforcement["run"]
    assert "receipt digest differs" in enforcement["run"]
    assert workflow[True]["workflow_call"]["inputs"]["base-ref"]["required"] is False
    assert workflow["permissions"] == {"contents": "read"}
    workflow_text = (ROOT / ".github/workflows/reusable-sourcebound.yml").read_text()
    assert "pull_request_target" not in workflow_text
    assert "drive" not in workflow_text
    assert "python3 - <<" not in workflow_text
    assert "python3 -m pip" not in workflow_text

    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    reusable_gate = ci["jobs"]["reusable-gate"]
    assert reusable_gate["uses"] == "./.github/workflows/reusable-sourcebound.yml"
    assert reusable_gate["with"] == {
        "package-ref": "${{ github.event.pull_request.head.sha || github.sha }}",
        "base-ref": (
            "${{ github.event.pull_request.base.sha || "
            "github.event.before || github.sha }}"
        ),
        "head-ref": "${{ github.event.pull_request.head.sha || github.sha }}",
    }
    assert "repository-declared execution" not in workflow_text
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
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-sourcebound.yml").read_text())
    receipt_step = next(
        step
        for step in workflow["jobs"]["sourcebound"]["steps"]
        if step.get("name") == "Write action receipt"
    )
    verdict = tmp_path / "sourcebound-verdict.json"
    sarif = tmp_path / "sourcebound-verdict.sarif"
    exit_receipt = tmp_path / "sourcebound-verdict.exit"
    verdict.write_text(
        json.dumps(
            {
                "schema": "sourcebound.pr-verdict.v1",
                "state": "ready",
                "digest": "d" * 64,
                "audit": {"ok": True},
                "mechanisms": {
                    "region": {"drifted": 0, "skipped": 0},
                    "projection": {"stale": 0},
                },
                "execution": {"mode": "static-only"},
            }
        )
        + "\n"
    )
    sarif.write_text('{"version":"2.1.0","runs":[]}\n')
    exit_receipt.write_text("0\n")
    package_ref = "a" * 40
    source_sha = "b" * 40
    workflow_sha = "c" * 40
    environment = os.environ | {
        "SOURCEBOUND_EVIDENCE_DIR": str(tmp_path),
        "SOURCEBOUND_PACKAGE_REF": package_ref,
        "SOURCEBOUND_REPOSITORY": "example/repository",
        "SOURCEBOUND_REPOSITORY_REF": "refs/heads/main",
        "SOURCEBOUND_REPOSITORY_SHA": source_sha,
        "SOURCEBOUND_BASE_REF": "",
        "SOURCEBOUND_HEAD_REF": "",
        "SOURCEBOUND_EVENT": "workflow_dispatch",
        "SOURCEBOUND_RUN_ID": "1234",
        "SOURCEBOUND_RUN_ATTEMPT": "2",
        "SOURCEBOUND_WORKFLOW_REF": "example/repository/.github/workflows/docs.yml@refs/heads/main",
        "SOURCEBOUND_WORKFLOW_SHA": workflow_sha,
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
    receipt = json.loads((tmp_path / "sourcebound-run.json").read_text())
    assert receipt["schema"] == "sourcebound.action-run.v2"
    assert receipt["package"]["ref"] == package_ref
    assert receipt["package"]["version"]
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
        "changed": True,
        "ok": True,
        "verdict": "ready",
        "verdict_digest": "d" * 64,
    }
    assert [item["path"] for item in receipt["evidence"]] == [
        "sourcebound-verdict.exit",
        "sourcebound-verdict.json",
        "sourcebound-verdict.sarif",
    ]
    assert receipt["authoritative_evidence"] == "sourcebound-verdict.json"
    assert receipt["evidence"][1]["sha256"] == hashlib.sha256(verdict.read_bytes()).hexdigest()

    environment["SOURCEBOUND_BASE_REF"] = "1" * 40
    environment["SOURCEBOUND_HEAD_REF"] = "2" * 40
    repeated = subprocess.run(
        ["sh", "-c", receipt_step["run"]],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert repeated.returncode == 0, repeated.stderr
    changed_receipt = json.loads((tmp_path / "sourcebound-run.json").read_text())
    assert changed_receipt["source"]["comparison"] == {
        "base": "1" * 40,
        "head": "2" * 40,
    }
    assert changed_receipt["results"]["ok"] is True


def test_reusable_action_rejects_non_commit_pin_before_install(tmp_path: Path) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-sourcebound.yml").read_text())
    install = next(
        step
        for step in workflow["jobs"]["sourcebound"]["steps"]
        if step.get("name") == "Install pinned sourcebound"
    )
    environment = os.environ | {"SOURCEBOUND_PACKAGE_REF": "$(touch escaped)"}

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


def test_reusable_action_fails_closed_and_isolates_fork_files(
    tmp_path: Path,
) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-sourcebound.yml").read_text())
    gate = next(
        step
        for step in workflow["jobs"]["sourcebound"]["steps"]
        if step.get("name") == "Evaluate one static verdict"
    )
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
    (repository / ".sourcebound.yml").write_text("version: 1\nbindings: []\n")
    (repository / "README.md").write_text(
        "# Orbit\n\n"
        "<!-- sourcebound:purpose -->\n"
        "Orbit maintainers use this page to locate the repository entry point.\n"
        "<!-- sourcebound:end purpose -->\n"
    )
    marker = tmp_path / "sitecustomize-started"
    (repository / "sitecustomize.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['HOSTILE_MARKER']).write_text('started')\n"
    )
    symlink_target = tmp_path / "fork-controlled-target"
    symlink_target.write_text("unchanged\n")
    (repository / "sourcebound-verdict.sarif").symlink_to(symlink_target)
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "hostile fork fixture",
        ],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    evidence_dir = tmp_path / "trusted-evidence"
    github_output = tmp_path / "github-output"
    environment = os.environ | {
        "SOURCEBOUND_BASE": head,
        "SOURCEBOUND_HEAD": head,
        "SOURCEBOUND_EVIDENCE_DIR": str(evidence_dir),
        "GITHUB_OUTPUT": str(github_output),
        "GITHUB_WORKSPACE": str(repository),
        "HOSTILE_MARKER": str(marker),
    }

    completed = subprocess.run(
        ["bash", "-c", gate["run"]],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (evidence_dir / "sourcebound-verdict.exit").read_text() == "3\n"
    payload = json.loads((evidence_dir / "sourcebound-verdict.json").read_text())
    assert payload["state"] == "invalid"
    assert payload["error"]["class"] == "extraction"
    assert "unsafe path" in payload["error"]["detail"]
    assert not marker.exists()
    assert symlink_target.read_text() == "unchanged\n"
    assert (repository / "sourcebound-verdict.sarif").is_symlink()


def test_reusable_action_enforces_the_recorded_verdict_bytes(tmp_path: Path) -> None:
    from clean_docs.verdict import render_verdict_payload_sarif

    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-sourcebound.yml").read_text())
    enforcement = next(
        step
        for step in workflow["jobs"]["sourcebound"]["steps"]
        if step.get("name") == "Enforce the recorded verdict"
    )
    payload: dict[str, object] = {
        "schema": "sourcebound.pr-verdict.v1",
        "state": "ready",
        "ready": True,
            "producer": {"name": "sourcebound", "version": __version__},
        "findings": [],
    }
    payload["digest"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    verdict = tmp_path / "sourcebound-verdict.json"
    sarif = tmp_path / "sourcebound-verdict.sarif"
    exit_receipt = tmp_path / "sourcebound-verdict.exit"
    verdict.write_text(json.dumps(payload, sort_keys=True) + "\n")
    sarif.write_text(render_verdict_payload_sarif(payload))
    exit_receipt.write_text("0\n")
    evidence = []
    for path in (exit_receipt, verdict, sarif):
        evidence.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    receipt = tmp_path / "sourcebound-run.json"
    receipt.write_text(
        json.dumps(
            {
                "authoritative_evidence": verdict.name,
                "package": {"version": __version__},
                "results": {
                    "ok": True,
                    "verdict": "ready",
                    "verdict_digest": payload["digest"],
                },
                "evidence": evidence,
            }
        )
        + "\n"
    )
    environment = os.environ | {
        "SOURCEBOUND_EVIDENCE_DIR": str(tmp_path),
        "PYTHONPATH": str(ROOT / "src"),
    }

    completed = subprocess.run(
        ["sh", "-c", enforcement["run"]],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr

    verdict.write_text(verdict.read_text().replace('"ready": true', '"ready": false'))
    tampered = subprocess.run(
        ["sh", "-c", enforcement["run"]],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert tampered.returncode != 0
    assert "digest does not match" in tampered.stderr

    verdict.unlink()
    missing = subprocess.run(
        ["sh", "-c", enforcement["run"]],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing.returncode != 0
    assert "missing or empty" in missing.stderr
