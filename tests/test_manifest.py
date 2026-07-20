from pathlib import Path

import pytest
import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.manifest import load_manifest
from clean_docs.review_limits import (
    MAX_REVIEW_CONTRACTS,
    MAX_REVIEW_LOCATORS,
    MAX_REVIEW_LOCATORS_PER_CONTRACT,
    MAX_REVIEW_UNIQUE_PATHS,
)


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

VALID_REVIEW_CONTRACTS = """\
review_contracts:
  - id: delivery-guidance
    mode: observe
    sources:
      - id: page-policy
        path: src/delivery.py
        extractor: python-symbol
        locator: Delivery.fetch_page
    targets:
      - id: reader-instructions
        path: docs/delivery.md
        extractor: markdown-section
        locator: "#reading-large-results"
      - id: tool-description
        path: config/delivery.yaml
        extractor: structured-data
        locator: /tools/fetch/description
"""


def test_loads_strict_region_binding(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID)
    manifest = load_manifest(path)
    assert manifest.bindings[0].source.symbol == "ACTIONS"


def test_manifest_defaults_to_no_review_contracts(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID)

    assert load_manifest(path).review_contracts == ()


def test_loads_observe_review_contract(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID + VALID_REVIEW_CONTRACTS)

    contract = load_manifest(path).review_contracts[0]

    assert contract.id == "delivery-guidance"
    assert contract.mode == "observe"
    assert contract.sources[0].id == "page-policy"
    assert contract.sources[0].path == Path("src/delivery.py")
    assert contract.sources[0].extractor == "python-symbol"
    assert contract.sources[0].locator == "Delivery.fetch_page"
    assert tuple(locator.id for locator in contract.targets) == (
        "reader-instructions",
        "tool-description",
    )


@pytest.mark.parametrize(
    ("review_contracts", "message"),
    [
        ("review_contracts: {}", "review_contracts must be a list"),
        ("review_contracts:", "review_contracts must be a list"),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "    mode: observe",
                "    mode: observe\n    unknown: true",
            ),
            "unknown key",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "  - id: delivery-guidance",
                "  - id: ''",
            ),
            r"review_contracts\[0\]\.id must be one non-empty line",
        ),
        (
            VALID_REVIEW_CONTRACTS
            + VALID_REVIEW_CONTRACTS.removeprefix("review_contracts:\n"),
            "duplicate review contract id",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace("mode: observe", "mode: enforce"),
            "mode must be observe",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "    sources:\n"
                "      - id: page-policy\n"
                "        path: src/delivery.py\n"
                "        extractor: python-symbol\n"
                    "        locator: Delivery.fetch_page\n",
                "    sources: []\n",
            ),
            "sources must be a non-empty list",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "    targets:\n"
                "      - id: reader-instructions\n"
                "        path: docs/delivery.md\n"
                "        extractor: markdown-section\n"
                '        locator: "#reading-large-results"\n'
                "      - id: tool-description\n"
                "        path: config/delivery.yaml\n"
                "        extractor: structured-data\n"
                "        locator: /tools/fetch/description\n",
                "    targets: []\n",
            ),
            "targets must be a non-empty list",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                    "        locator: Delivery.fetch_page",
                    "        locator: Delivery.fetch_page\n        unknown: true",
            ),
            "unknown key",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "      - id: reader-instructions",
                "      - id: page-policy",
            ),
            "duplicate review locator id",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "        path: src/delivery.py",
                "        path: ../delivery.py",
            ),
            "stay inside",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "        extractor: python-symbol",
                "        extractor: python-literal",
            ),
            "extractor must be one of",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "        path: src/delivery.py",
                "        path: src/delivery.ts",
            ),
            "path must end with",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                    "        locator: Delivery.fetch_page",
                    "        locator: Delivery/fetch_page",
            ),
            "dotted Python identifier",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                '        locator: "#reading-large-results"',
                "        locator: reading-large-results",
            ),
            "#fragment anchor",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                '        locator: "#reading-large-results"',
                '        locator: "##reading-large-results"',
            ),
            "#fragment anchor",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "        locator: /tools/fetch/description",
                "        locator: tools.fetch.description",
            ),
            "JSON Pointer starting with /",
        ),
        (
            VALID_REVIEW_CONTRACTS.replace(
                "        locator: /tools/fetch/description",
                "        locator: /tools/~2fetch/description",
            ),
            "JSON Pointer starting with /",
        ),
    ],
)
def test_rejects_invalid_review_contracts(
    tmp_path: Path, review_contracts: str, message: str
) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID + review_contracts)

    with pytest.raises(ConfigurationError, match=message):
        load_manifest(path)


def test_rejects_review_contract_source_target_identity_with_different_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".sourcebound.yml"
    contract = VALID_REVIEW_CONTRACTS.replace(
        "        path: docs/delivery.md\n"
        "        extractor: markdown-section\n"
        '        locator: "#reading-large-results"',
        "        path: src/delivery.py\n"
        "        extractor: python-symbol\n"
        "        locator: Delivery.fetch_page",
    )
    path.write_text(VALID + contract)

    with pytest.raises(
        ConfigurationError,
        match="source and target locators must not have the same",
    ):
        load_manifest(path)


@pytest.mark.parametrize(
    "projection",
    [
        """\
projections:
  llms_txt:
    output: docs/generated.md
""",
        """\
projections:
  bundles:
    - id: generated-context
      output: docs/generated.md
      include: [README.md]
""",
        """\
projections:
  visuals:
    - id: generated-visual
      source: docs/visuals/generated-visual.yml
      human_output: docs/generated.md
      agent_output: .sourcebound/visuals/generated-visual.md
""",
    ],
)
def test_rejects_generated_projection_as_review_target(
    tmp_path: Path,
    projection: str,
) -> None:
    path = tmp_path / ".sourcebound.yml"
    contract = """\
review_contracts:
  - id: generated-target
    mode: observe
    sources:
      - id: delivery-policy
        path: src/delivery.py
        extractor: python-symbol
        locator: Delivery.fetch_page
    targets:
      - id: generated-document
        path: docs/generated.md
        extractor: markdown-section
        locator: "#generated"
"""
    path.write_text(VALID + projection + contract)

    with pytest.raises(
        ConfigurationError,
        match="cannot be generated projection output docs/generated.md",
    ):
        load_manifest(path)


def test_allows_non_generated_python_review_target(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(
        VALID
        + """\
review_contracts:
  - id: agent-prompt
    mode: observe
    sources:
      - id: delivery-policy
        path: src/delivery.py
        extractor: python-symbol
        locator: Delivery.fetch_page
    targets:
      - id: prompt-builder
        path: src/prompt.py
        extractor: python-symbol
        locator: build_prompt
"""
    )

    target = load_manifest(path).review_contracts[0].targets[0]

    assert target.path == Path("src/prompt.py")
    assert target.locator == "build_prompt"


def _review_contract(
    contract_index: int,
    source_count: int,
    target_count: int,
    *,
    unique_paths: bool = False,
) -> dict[str, object]:
    def locator(group: str, index: int, extractor: str) -> dict[str, str]:
        extension = "py" if extractor == "python-symbol" else "md"
        path_index = f"-{contract_index}-{index}" if unique_paths else ""
        return {
            "id": f"{group}-{index}",
            "path": f"{group}{path_index}.{extension}",
            "extractor": extractor,
            "locator": (
                f"symbol_{contract_index}_{index}"
                if extractor == "python-symbol"
                else f"#section-{contract_index}-{index}"
            ),
        }

    return {
        "id": f"contract-{contract_index}",
        "mode": "observe",
        "sources": [
            locator("source", index, "python-symbol")
            for index in range(source_count)
        ],
        "targets": [
            locator("target", index, "markdown-section")
            for index in range(target_count)
        ],
    }


@pytest.mark.parametrize(
    ("contracts", "message"),
    [
        (
            [_review_contract(index, 1, 1) for index in range(MAX_REVIEW_CONTRACTS + 1)],
            f"at most {MAX_REVIEW_CONTRACTS} contracts",
        ),
        (
            [
                _review_contract(
                    0,
                    1,
                    MAX_REVIEW_LOCATORS_PER_CONTRACT,
                )
            ],
            f"at most {MAX_REVIEW_LOCATORS_PER_CONTRACT} locators",
        ),
        (
            [
                _review_contract(index, 1, 31)
                for index in range(MAX_REVIEW_LOCATORS // 32 + 1)
            ],
            f"at most {MAX_REVIEW_LOCATORS} locators",
        ),
        (
            [
                _review_contract(index, 15, 15, unique_paths=True)
                for index in range(MAX_REVIEW_UNIQUE_PATHS // 30 + 1)
            ],
            f"at most {MAX_REVIEW_UNIQUE_PATHS} unique paths",
        ),
    ],
)
def test_bounds_review_contract_manifest_work(
    tmp_path: Path,
    contracts: list[dict[str, object]],
    message: str,
) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(
        VALID + yaml.safe_dump({"review_contracts": contracts}, sort_keys=False)
    )

    with pytest.raises(ConfigurationError, match=message):
        load_manifest(path)


def test_rejects_repeated_review_locator_identity(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    contract = _review_contract(0, 1, 1)
    targets = contract["targets"]
    assert isinstance(targets, list)
    first_target = targets[0]
    assert isinstance(first_target, dict)
    repeated = dict(first_target)
    repeated["id"] = "second-id"
    targets.append(repeated)
    path.write_text(
        VALID
        + yaml.safe_dump({"review_contracts": [contract]}, sort_keys=False)
    )

    with pytest.raises(ConfigurationError, match="must not repeat"):
        load_manifest(path)


def test_loads_json_pointer_binding(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID.replace(
        "extractor: python-literal\n    source:\n      path: src/actions.py\n      symbol: ACTIONS",
        "extractor: json\n    source:\n      path: experiment/corpus.json\n      pointer: /cases",
    ))
    binding = load_manifest(path).bindings[0]
    assert binding.source.pointer == "/cases"
    assert binding.source.symbol is None


def test_python_token_is_valid_only_as_the_allowlisted_executable(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
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
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID + """\
projections:
  llms_txt:
    output: llms.txt
    title: Fixture documentation
    include: [README.md, docs/CANONICAL.md]
  bundles:
    - id: contributor
      output: .sourcebound/context/contributor.md
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
        ("bundles: []", "configure llms_txt, a bundle, a demo, or visuals"),
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
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID + f"projections:\n  {projection}\n")
    with pytest.raises(ConfigurationError, match=message):
        load_manifest(path)


def test_loads_static_demo_projection(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID + """\
projections:
  demo:
    output: docs/demo/index.html
    evidence: .sourcebound/demo/evidence.json
""")
    projections = load_manifest(path).projections
    assert projections is not None and projections.demo is not None
    assert projections.demo.output == Path("docs/demo/index.html")


def test_loads_structured_visual_projection(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID + """\
projections:
  visuals:
    - id: queue-flow
      source: docs/visuals/queue-flow.yml
      human_output: docs/generated/queue-flow.mdx
      agent_output: .sourcebound/visuals/queue-flow.md
""")

    projections = load_manifest(path).projections

    assert projections is not None
    assert projections.visuals[0].id == "queue-flow"
    assert projections.visuals[0].source == Path("docs/visuals/queue-flow.yml")


def test_visual_projection_cannot_replace_a_bound_document(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
    path.write_text(VALID + """\
projections:
  visuals:
    - id: queue-flow
      source: docs/visuals/queue-flow.yml
      human_output: README.md
      agent_output: .sourcebound/visuals/queue-flow.md
""")

    with pytest.raises(ConfigurationError, match="cannot replace a bound document"):
        load_manifest(path)


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
    path = tmp_path / ".sourcebound.yml"
    path.write_text(text)
    with pytest.raises(ConfigurationError, match=message):
        load_manifest(path)


def test_v2_rejects_deprecated_network_declaration(tmp_path: Path) -> None:
    path = tmp_path / ".sourcebound.yml"
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
    path = tmp_path / ".sourcebound.yml"
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
