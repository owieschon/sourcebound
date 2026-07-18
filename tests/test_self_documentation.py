from __future__ import annotations

import argparse
import shlex
from pathlib import Path

import pytest

from clean_docs.capabilities import CLI_REFERENCE
from clean_docs.cli import _parser, _validate_arguments
from clean_docs.engine import evaluate
from clean_docs.manifest import MANIFEST_REFERENCE, load_manifest


ROOT = Path(__file__).parents[1]


def _parser_commands(parser: argparse.ArgumentParser, prefix: str = "") -> set[str]:
    commands = set()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, child in action.choices.items():
            command = f"{prefix} {name}".strip()
            commands.add(command)
            commands.update(_parser_commands(child, command))
    return commands


def test_cli_and_manifest_registries_drive_the_parser_and_self_manifest() -> None:
    assert _parser_commands(_parser()) == {item["command"] for item in CLI_REFERENCE}
    assert {item["binding"] for item in MANIFEST_REFERENCE} == {
        "region",
        "claim",
        "symbol",
    }
    manifest = load_manifest(ROOT / ".clean-docs.yml")
    assert {binding.id for binding in manifest.bindings} >= {
        "cli-reference",
        "manifest-reference",
    }


def test_cli_reference_examples_parse() -> None:
    for item in CLI_REFERENCE:
        argv = shlex.split(item["example"])[1:]
        if argv[-1:] == ["--help"]:
            with pytest.raises(SystemExit) as exc:
                _parser().parse_args(argv)
            assert exc.value.code == 0
        else:
            _validate_arguments(_parser().parse_args(argv))


@pytest.mark.parametrize(
    ("source", "old", "new", "binding"),
    [
        (
            "capabilities.py",
            "Assess documentation and enforce adopted scopes",
            "Assess repository documentation",
            "cli-reference",
        ),
        (
            "manifest.py",
            "Generated content matches source evidence",
            "Generated content matches extracted evidence",
            "manifest-reference",
        ),
    ],
)
def test_self_check_detects_reference_source_drift(
    tmp_path: Path, source: str, old: str, new: str, binding: str
) -> None:
    root = tmp_path / "repo"
    package = root / "src/clean_docs"
    package.mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "README.md").write_text((ROOT / "README.md").read_text())
    (root / "docs/CLI.md").write_text((ROOT / "docs/CLI.md").read_text())
    (root / "docs/REFERENCE.md").write_text((ROOT / "docs/REFERENCE.md").read_text())
    for name in ("capabilities.py", "manifest.py"):
        (package / name).write_text((ROOT / "src/clean_docs" / name).read_text())
    (root / ".clean-docs.yml").write_text("""\
version: 1
bindings:
  - id: cli-reference
    type: region
    doc: docs/CLI.md
    region: cli-reference
    extractor: python-literal
    source: {path: src/clean_docs/capabilities.py, symbol: CLI_REFERENCE}
    renderer: markdown-table
    columns: [command, job, writes, example]
  - id: manifest-reference
    type: region
    doc: docs/REFERENCE.md
    region: manifest-reference
    extractor: python-literal
    source: {path: src/clean_docs/manifest.py, symbol: MANIFEST_REFERENCE}
    renderer: markdown-table
    columns: [binding, required, verifies]
""")
    target = package / source
    content = target.read_text()
    assert content.count(old) == 1
    target.write_text(content.replace(old, new))

    results = evaluate(root, root / ".clean-docs.yml")

    changed = [result.binding_id for result in results if result.changed]
    assert changed == [binding]
