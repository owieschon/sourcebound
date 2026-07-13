from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from clean_docs.capabilities import PRODUCT_OVERVIEW
from clean_docs.errors import ConfigurationError
from clean_docs.manifest import load_manifest
from clean_docs.policy import (
    PURPOSE_BEGIN,
    PURPOSE_END,
    check_document,
    check_prose,
    ensure_purpose_contract,
)
from clean_docs.standard import compile_standard, load_default_pack, load_pack, pack_matches_standard


ROOT = Path(__file__).parents[1]


def test_bundled_pack_matches_canonical_standard() -> None:
    standard = ROOT / "STANDARD.md"
    pack = ROOT / "src/clean_docs/standards/default.json"
    assert pack_matches_standard(standard, pack)
    compiled = compile_standard(standard)
    assert compiled["source"]["sha256"]
    assert set(compiled["tiers"]) == {"voice", "document", "corpus", "grounding"}
    assert len(compiled["checklist"]) >= 18


def test_default_pack_is_available_as_package_data() -> None:
    pack = load_default_pack()
    assert pack["profile"] == "clean-docs-default"
    assert pack["policy"]["require_grounded_facts"] is True
    assert pack["policy"]["require_definition_first"] is True
    assert pack["policy"]["require_purpose_contract"] is True
    assert pack["style"]["voice"]["register"] == "helpful senior colleague"
    assert pack["style"]["purpose_contract"]["judgment"] == [
        "names who the page is for and when it applies",
        "states the reader problem rather than listing features",
        "states a falsifiable resulting capability",
        "matches the implementation and cited sources",
    ]


def test_standard_change_makes_pack_stale(tmp_path: Path) -> None:
    standard = tmp_path / "STANDARD.md"
    standard.write_text((ROOT / "STANDARD.md").read_text() + "\nA new rule.\n")
    pack = ROOT / "src/clean_docs/standards/default.json"
    assert not pack_matches_standard(standard, pack)


def test_policy_uses_compiled_booster_registry() -> None:
    pack = load_default_pack()
    findings = check_document(
        "README.md",
        "# Product\n\n"
        "<!-- clean-docs:purpose -->\n"
        "Use this page when product behavior changes without an obvious reference. "
        "It gives maintainers one checked path to the current behavior.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "A powerful tool.\n",
        pack,
    )
    assert [(finding.rule, finding.line) for finding in findings] == [
        ("prohibited-booster", 7)
    ]
    assert json.dumps(pack, sort_keys=True)


def test_rejects_modified_policy_pack(tmp_path: Path) -> None:
    pack = load_default_pack()
    pack["policy"]["doc_max_lines"] = 999
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(pack))
    with pytest.raises(ConfigurationError, match="integrity"):
        load_pack(path)


def test_first_screen_capability_summary_is_self_derived() -> None:
    manifest = load_manifest(ROOT / ".clean-docs.yml")

    assert {binding.id for binding in manifest.bindings} >= {
        "product-overview",
        "supported-bindings",
    }


def test_product_overview_does_not_duplicate_release_version() -> None:
    assert re.search(r"\bVersion \d+\.\d+", PRODUCT_OVERVIEW) is None


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        (
            "# Project\n\nBody content.\n",
            "add exactly one complete marked BLUF purpose contract",
        ),
        (
            "# Project\n\nBody first.\n\n<!-- clean-docs:purpose -->\n"
            "Use this page when the project changes. It gives maintainers a checked path.\n"
            "<!-- clean-docs:end purpose -->\n",
            "move the purpose contract before all body content",
        ),
        (
            "# Project guide\n\n<!-- clean-docs:purpose -->\n"
            "This is the project guide.\n<!-- clean-docs:end purpose -->\n",
            "replace the title restatement",
        ),
    ],
)
def test_purpose_contract_enforces_presence_position_and_non_restatement(
    content: str,
    detail: str,
) -> None:
    findings = check_document("README.md", content, load_default_pack())

    assert len(findings) == 1
    assert findings[0].rule == "purpose-contract"
    assert detail in findings[0].detail


def test_purpose_contract_ignores_headings_and_markers_inside_code_fences() -> None:
    content = (
        "# Project\n\n<!-- clean-docs:purpose -->\n"
        "Use this page when source claims can drift. It gives maintainers a checked repair path.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "```markdown\n# Example\n<!-- clean-docs:purpose -->\n"
        "<!-- clean-docs:end purpose -->\n```\n"
    )

    assert check_document("README.md", content, load_default_pack()) == []


def test_prohibited_boosters_do_not_treat_headings_as_prose() -> None:
    content = (
        "# Project\n\n<!-- clean-docs:purpose -->\n"
        "Use this page when source claims can drift. It gives maintainers a checked repair path.\n"
        "<!-- clean-docs:end purpose -->\n\n## Work simply\n"
    )

    assert check_document("README.md", content, load_default_pack()) == []


def test_bootstrap_marks_author_prose_and_replaces_a_title_restatement() -> None:
    authored = "# Project\n\nMaintainers use this guide before changing the API.\n\n## Next\n"
    marked = ensure_purpose_contract(authored)

    contract = marked.split(PURPOSE_BEGIN, 1)[1].split(PURPOSE_END, 1)[0]
    assert "Maintainers use this guide before changing the API." in contract
    assert ensure_purpose_contract(marked) == marked

    replaced = ensure_purpose_contract("# Project guide\n\nThis is the project guide.\n")
    assert "This is the project guide." not in replaced
    assert "Use this page when you need to understand Project guide" in replaced


def test_bootstrap_moves_authored_prose_ahead_of_logos_and_badges() -> None:
    content = (
        "# Queue\n\n"
        "![Queue logo](media/logo.png)\n\n"
        "[![Build](https://example.test/badge.svg)](https://example.test/build)\n\n"
        "A tiny queue data structure with a promise-based API.\n\n"
        "## Install\n"
    )

    marked = ensure_purpose_contract(content)

    assert marked.index(PURPOSE_BEGIN) < marked.index("![Queue logo]")
    contract = marked.split(PURPOSE_BEGIN, 1)[1].split(PURPOSE_END, 1)[0]
    assert "A tiny queue data structure with a promise-based API." in contract
    assert "![" not in contract


def test_fragment_policy_does_not_require_a_document_contract() -> None:
    assert check_prose("<fragment>", "The command reports the current facts.", load_default_pack()) == []
