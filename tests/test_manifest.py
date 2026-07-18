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


def test_loads_json_pointer_binding(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(VALID.replace(
        "extractor: python-literal\n    source:\n      path: src/actions.py\n      symbol: ACTIONS",
        "extractor: json\n    source:\n      path: experiment/corpus.json\n      pointer: /cases",
    ))
    binding = load_manifest(path).bindings[0]
    assert binding.source.pointer == "/cases"
    assert binding.source.symbol is None


def test_python_token_is_valid_only_as_the_allowlisted_executable(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(
        VALID.replace(
            "bindings:",
            "execution:\n"
            "  commands: deny\n"
            "  allowed_commands:\n"
            "    invalid:\n"
            "      argv: [python, \"{python}\"]\n"
            "      network: false\n"
            "bindings:",
        )
    )

    with pytest.raises(ConfigurationError, match="only as its executable"):
        load_manifest(path)


def test_loads_strict_projection_contract(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(VALID + """\
projections:
  llms_txt:
    output: llms.txt
    title: Fixture documentation
    include: [README.md, docs/CANONICAL.md]
  bundles:
    - id: contributor
      output: .clean-docs/context/contributor.md
      include: [README.md]
""")

    projections = load_manifest(path).projections

    assert projections is not None
    assert projections.llms_txt is not None
    assert projections.llms_txt.output == Path("llms.txt")
    assert projections.llms_txt.include == (
        Path("README.md"),
        Path("docs/CANONICAL.md"),
    )
    assert projections.bundles[0].include == (Path("README.md"),)


@pytest.mark.parametrize(
    ("projection", "message"),
    [
        ("bundles: []", "configure llms_txt, a bundle, or a demo"),
        (
            "bundles:\n    - id: contributor\n      output: context.md\n"
            "      include: [docs/UNBOUND.md]",
            "unbound document",
        ),
        (
            "llms_txt: {output: llms.txt}\n  unknown: true",
            "unknown key",
        ),
    ],
)
def test_rejects_invalid_projection_contract(
    tmp_path: Path, projection: str, message: str
) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(VALID + f"projections:\n  {projection}\n")
    with pytest.raises(ConfigurationError, match=message):
        load_manifest(path)


def test_loads_static_demo_projection(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(VALID + """\
projections:
  demo:
    output: docs/demo/index.html
    evidence: .clean-docs/demo/evidence.json
""")
    projections = load_manifest(path).projections
    assert projections is not None and projections.demo is not None
    assert projections.demo.output == Path("docs/demo/index.html")


@pytest.mark.parametrize(
    "replacement, message",
    [
        ("version: 1", "unknown key"),
        ("version: 3", "version must be 1 or 2"),
        ("doc: ../README.md", "stay inside"),
        ("type: coverage", "must be region, claim, or symbol"),
        ("docs: {}", "unknown key"),
    ],
)
def test_rejects_invalid_contract(tmp_path: Path, replacement: str, message: str) -> None:
    text = VALID
    if replacement == "version: 1":
        text = text.replace("version: 1", "version: 1\nunknown: true")
    elif replacement == "version: 3":
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


def test_v2_rejects_deprecated_network_declaration(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(
        VALID.replace("version: 1", "version: 2").replace(
            "bindings:",
            "execution:\n"
            "  commands: deny\n"
            "  allowed_commands:\n"
            "    summary:\n"
            "      argv: [summary]\n"
            "      timeout_seconds: 10\n"
            "      network: false\n"
            "bindings:",
        )
    )

    with pytest.raises(ConfigurationError, match="unknown key.*network"):
        load_manifest(path)


def test_v1_reports_deprecated_network_declaration(tmp_path: Path) -> None:
    path = tmp_path / ".clean-docs.yml"
    path.write_text(
        VALID.replace(
            "bindings:",
            "execution:\n"
            "  commands: deny\n"
            "  allowed_commands:\n"
            "    summary:\n"
            "      argv: [summary]\n"
            "      timeout_seconds: 10\n"
            "      network: false\n"
            "bindings:",
        )
    )

    manifest = load_manifest(path)

    assert manifest.deprecations == (
        "execution.allowed_commands.summary.network",
    )
