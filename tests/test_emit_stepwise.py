from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import yaml


MANIFEST = """\
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: python-literal
    source:
      path: src/actions.py
      symbol: ACTIONS
    renderer: markdown-table
    columns: [name, tier]
"""
SOURCE = 'ACTIONS = {"a": {"name": "a", "tier": 1}}\n'
README = """\
# Fixture

<!-- clean-docs:purpose -->
Use this fixture when testing a stepwise projection. It gives maintainers one bound document to audit and repair.
<!-- clean-docs:end purpose -->

<!-- clean-docs:begin actions -->
| name | tier |
| --- | --- |
| a | 1 |
<!-- clean-docs:end actions -->
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    source = Path(__file__).parents[1] / "src"
    environment["PYTHONPATH"] = str(source) + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / ".clean-docs.yml").write_text(MANIFEST)
    (root / "src/actions.py").write_text(SOURCE)
    (root / "README.md").write_text(README)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


def _digests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_emits_schema_valid_manifest_derived_package(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = _run(root, "emit", "stepwise-skill", "--out", "dist/stepwise")
    assert result.returncode == 0, result.stderr

    output = root / "dist/stepwise"
    config = yaml.safe_load((output / "config.yaml").read_text())
    assert set(config) == {
        "type", "template", "description", "tags", "cli", "references", "variants",
    }
    assert config["type"] == "skill"
    assert config["template"] == "description.md"
    assert config["cli"] == {"role": "skill"}
    assert config["references"]["preamble"] == (
        "**Read ONLY this file.** Do not read any other reference file until this one tells you to."
    )
    assert config["variants"] == [{
        "id": "all",
        "display_name": "Keep documentation true",
        "tags": ["documentation"],
        "docs_urls": [],
    }]
    assert sorted(path.name for path in (output / "references").iterdir()) == [
        "1-audit.md", "2-repair.md", "3-verify.md",
    ]
    expected_chain = {
        "1-audit.md": "2-repair.md",
        "2-repair.md": "3-verify.md",
        "3-verify.md": None,
    }
    for name, next_step in expected_chain.items():
        content = (output / "references" / name).read_text()
        frontmatter = yaml.safe_load(content.split("---", 2)[1])
        assert frontmatter == {"next_step": next_step}
        if next_step:
            assert f"read `{next_step}`" in content
    assert "`README.md`" in (output / "description.md").read_text()


def test_stepwise_projection_is_idempotent_and_its_commands_pass(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    arguments = ("emit", "stepwise-skill", "--out", "dist/stepwise")
    assert _run(root, *arguments).returncode == 0
    first = _digests(root / "dist/stepwise")
    assert _run(root, *arguments).returncode == 0
    assert _digests(root / "dist/stepwise") == first

    output = root / "dist/stepwise"
    subprocess.run(["git", "init", "-q", str(output)], check=True)
    subprocess.run(["git", "-C", str(output), "add", "."], check=True)
    assert _run(output, "audit").returncode == 0
    assert _run(root, "audit").returncode == 0
    assert _run(root, "drive").returncode == 0
    assert _run(root, "check").returncode == 0


def test_large_stepwise_projection_does_not_repeat_the_bound_document_index(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    manifest = MANIFEST + "\n".join(
        (
            f"  - id: extra-{index}\n"
            "    type: symbol\n"
            f"    doc: docs/guide-{index}.md\n"
            "    anchor: guide\n"
            "    source: {path: src/actions.py, symbol: ACTIONS}\n"
        )
        for index in range(12)
    )
    (root / ".clean-docs.yml").write_text(manifest)

    assert _run(root, "emit", "stepwise-skill", "--out", "dist/stepwise").returncode == 0
    output = root / "dist/stepwise"
    repair = (output / "references/2-repair.md").read_text()
    assert "docs/guide-0.md" not in repair
    assert _run(output, "audit").returncode == 0


def test_command_role_is_strict_and_serializes_cli_block(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    missing = _run(root, "emit", "stepwise-skill", "--role", "command")
    assert missing.returncode == 2
    assert "command name is required" in missing.stderr

    written = _run(
        root,
        "emit", "stepwise-skill", "--out", "dist/stepwise", "--role", "command",
        "--parent-command", "audit", "--command", "docs",
    )
    assert written.returncode == 0, written.stderr
    config = yaml.safe_load((root / "dist/stepwise/config.yaml").read_text())
    assert config["cli"] == {
        "role": "command",
        "command": "docs",
        "parentCommand": "audit",
    }


def test_skill_role_rejects_command_only_options(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = _run(root, "emit", "stepwise-skill", "--command", "docs")
    assert result.returncode == 2
    assert "command options require role command" in result.stderr
