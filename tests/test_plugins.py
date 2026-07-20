from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from clean_docs.engine import drive, evaluate
from clean_docs.errors import ConfigurationError, ExtractionError
from clean_docs.manifest import load_manifest
from clean_docs.plugins import scan_extended_inventory
from clean_docs.release import build_release_report


FIXTURE_PLUGIN = Path(__file__).parent / "fixtures/v05_plugin"
PROJECT = Path(__file__).parents[1]


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT / "src")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )


def _manifest(api_version: int = 1) -> str:
    return f"""\
version: 1
plugins:
  - id: fixture
    api_version: {api_version}
    interfaces: [extractor, discoverer, renderer, policy]
    argv: ["{{python}}", -m, fixture_plugin]
    timeout_seconds: 10
bindings:
  - id: fixture-facts
    type: region
    doc: README.md
    region: facts
    extractor: plugin:fixture
    source: {{path: facts.ext}}
    renderer: plugin:fixture
"""


def _commit(root: Path, message: str) -> str:
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
            message,
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(FIXTURE_PLUGIN / "fixture_plugin", root / "fixture_plugin")
    shutil.copy2(FIXTURE_PLUGIN / "pyproject.toml", root / "plugin-pyproject.toml")
    (root / "facts.ext").write_text("alpha\n")
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- sourcebound:purpose -->\n"
        "Use this fixture when testing an external evidence plugin. It gives maintainers one bounded region and one policy surface.\n"
        "<!-- sourcebound:end purpose -->\n\n<!-- sourcebound:begin facts -->\n"
        "<!-- sourcebound:end facts -->\n"
    )
    (root / ".sourcebound.yml").write_text(_manifest())
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def test_external_extractor_participates_in_drive_check_and_release(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    results, findings = drive(root, root / ".sourcebound.yml")
    assert not findings
    assert results[0].changed
    assert "- alpha" in (root / "README.md").read_text()
    assert not (root / "plugin-write-attempt.txt").exists()
    assert not any(item.changed for item in evaluate(root, root / ".sourcebound.yml"))
    before = _commit(root, "before")
    (root / "facts.ext").write_text("beta\n")
    after = _commit(root, "after")
    assert evaluate(root, root / ".sourcebound.yml")[0].changed
    (root / "fixture_plugin/__main__.py").write_text(
        "raise SystemExit('worktree-only failure')\n"
    )

    report = build_release_report(root, before, after)

    delta = next(item for item in report.deltas if item.kind == "extension-command")
    assert delta.change == "changed"
    assert delta.adapter == "plugin:fixture"
    assert delta.source == "facts.ext"
    assert not (root / "plugin-write-attempt.txt").exists()


def test_incompatible_plugin_fails_before_extraction(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / ".sourcebound.yml").write_text(_manifest(api_version=2))

    with pytest.raises(
        ConfigurationError,
        match=r"plugin fixture API version 2 is incompatible; sourcebound supports 1",
    ):
        load_manifest(root / ".sourcebound.yml")

    command = _run(root, "check")
    assert command.returncode == 2
    assert (
        "plugin fixture API version 2 is incompatible; sourcebound supports 1"
        in command.stderr
    )
    assert not (root / "plugin-write-attempt.txt").exists()


def test_static_only_check_skips_plugin_without_starting_it(tmp_path: Path) -> None:
    root = _root(tmp_path)
    marker = root / "plugin-started.txt"
    (root / "fixture_plugin/__main__.py").write_text(
        "from pathlib import Path\n"
        "Path('plugin-started.txt').write_text('started')\n"
        "raise SystemExit(9)\n"
    )

    checked = _run(root, "check", "--no-exec", "--format", "json")

    payload = json.loads(checked.stdout)
    assert checked.returncode == 0
    assert payload["complete"] is False
    assert payload["results"][0]["mechanism"] == "plugin"
    assert payload["results"][0]["status"] == "skipped-untrusted-execution"
    assert not marker.exists()


def test_static_only_inventory_discloses_skipped_discoverer_without_starting_it(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    marker = root / "plugin-started.txt"
    (root / "fixture_plugin/__main__.py").write_text(
        "from pathlib import Path\n"
        "Path('plugin-started.txt').write_text('started')\n"
        "raise SystemExit(9)\n"
    )

    inventory = _run(root, "inventory", "--no-exec", "--format", "json")

    assert inventory.returncode == 0, inventory.stderr
    payload = json.loads(inventory.stdout)
    assert payload["execution"] == {
        "mode": "static-only",
        "skipped_plugin_ids": ["fixture"],
    }
    assert not marker.exists()


def test_plugin_policy_blocks_plugin_rendered_output_before_write(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "facts.ext").write_text("FORBIDDEN\n")
    before = (root / "README.md").read_text()

    results, findings = drive(root, root / ".sourcebound.yml")

    assert results[0].changed
    assert [finding.rule for finding in findings] == ["fixture-forbidden"]
    assert (root / "README.md").read_text() == before


def test_plugin_cannot_replace_core_inventory_evidence(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "collision.ext").write_text("trigger\n")
    (root / "cli.py").write_text("parser.add_parser('fixture')\n")

    with pytest.raises(
        ExtractionError,
        match=r"plugin inventory id collides with core evidence: cli-command:cli.py:fixture",
    ):
        scan_extended_inventory(root)
