from pathlib import Path

import pytest

from clean_docs.errors import ConfigurationError
from clean_docs.manifest import load_manifest


VALID = """\
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


def test_loads_strict_region_binding(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(VALID)
    manifest = load_manifest(path)
    assert manifest.bindings[0].source.symbol == "ACTIONS"


@pytest.mark.parametrize(
    "replacement, message",
    [
        ("version: 1", "unknown key"),
        ("version: 2", "version must be 1"),
        ("doc: ../README.md", "stay inside"),
        ("type: claim", "must be region"),
        ("docs: {}", "unknown key"),
    ],
)
def test_rejects_invalid_contract(tmp_path: Path, replacement: str, message: str) -> None:
    text = VALID
    if replacement == "version: 1":
        text = text.replace("version: 1", "version: 1\nunknown: true")
    elif replacement == "version: 2":
        text = text.replace("version: 1", replacement)
    elif replacement.startswith("doc:"):
        text = text.replace("doc: README.md", replacement)
    elif replacement == "docs: {}":
        text = text.replace("version: 1", "version: 1\ndocs: {}")
    else:
        text = text.replace("type: region", replacement)
    path = tmp_path / ".clean-docs.yml"
    path.write_text(text)
    with pytest.raises(ConfigurationError, match=message):
        load_manifest(path)
