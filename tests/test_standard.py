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
    REGISTER_PROFILE,
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
    assert pack["style"]["precedence"] == [
        "truth and honesty",
        "grounding",
        "reader budget",
        "register",
        "warmth",
    ]
    assert "A stale README keeps a straight face." in pack["generation"]["exemplars"]
    assert pack["generation"]["exemplars_sha256"]
    assert pack["style"]["purpose_contract"]["judgment"] == [
        "defines the project-specific subject and intended operator",
        "names the consequential failure or decision the page addresses",
        "states the authority boundary and a falsifiable resulting capability",
        "uses authored language grounded in the implementation and cited sources",
    ]
    assert any(
        "subject-derived memorable element" in check for check in pack["checklist"]
    )
    assert any(
        "whimsy never carries a required fact or action" in check
        for check in pack["checklist"]
    )


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
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates booster policy" -->\n'
        "<!-- clean-docs:purpose -->\n"
        "Use this page when product behavior changes without an obvious reference. "
        "It gives maintainers one checked path to the current behavior.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "A powerful tool.\n",
        pack,
    )
    assert [(finding.rule, finding.line) for finding in findings] == [
        ("prohibited-booster", 8)
    ]
    assert json.dumps(pack, sort_keys=True)


def test_policy_rejects_stock_purpose_language() -> None:
    content = (
        "# Queue\n\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates purpose policy" -->\n'
        "<!-- clean-docs:purpose -->\n"
        "Read this page before changing or relying on Queue so you can preserve its contract.\n"
        "<!-- clean-docs:end purpose -->\n"
    )
    findings = check_document("README.md", content, load_default_pack())
    assert [(finding.rule, finding.line) for finding in findings] == [
        ("purpose-contract", 5)
    ]
    assert "stock purpose language" in findings[0].detail


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


def test_readme_and_standard_define_themselves_before_describing_value() -> None:
    readme = (ROOT / "README.md").read_text()
    standard = (ROOT / "STANDARD.md").read_text()

    readme_opening = readme.split(PURPOSE_BEGIN, 1)[1].split(PURPOSE_END, 1)[0].strip()
    standard_opening = standard.split(PURPOSE_BEGIN, 1)[1].split(PURPOSE_END, 1)[0].strip()
    assert readme_opening.startswith(
        "clean-docs is a source-bound documentation engine and CLI"
    )
    assert standard_opening.startswith(
        "STANDARD.md is the canonical writing and documentation policy"
    )


def test_product_overview_does_not_duplicate_release_version() -> None:
    assert re.search(r"\bVersion \d+\.\d+", PRODUCT_OVERVIEW) is None


def test_product_overview_explains_why_source_binding_is_needed() -> None:
    assert PRODUCT_OVERVIEW.startswith("A stale sentence does not fail loudly.")
    assert "keeps a straight face after the code has moved on" in PRODUCT_OVERVIEW
    assert "no mechanical way to identify the false claim" in PRODUCT_OVERVIEW
    assert "gives each protected fact a source" in PRODUCT_OVERVIEW
    assert "checks that relationship again in CI" in PRODUCT_OVERVIEW


def test_reader_facing_concept_pages_apply_bounded_personality() -> None:
    evaluation = (ROOT / "docs/EVALUATION.md").read_text()
    demo = (ROOT / "docs/demo/index.html").read_text()

    assert "a receipt for one task, not a halo around the whole corpus" in evaluation
    assert "Make stale prose fail loudly." in demo


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
    content = content.replace(
        "\n",
        '\n<!-- clean-docs:allow preamble-contract '
        'reason="Fixture isolates purpose policy" -->\n',
        1,
    )
    findings = check_document("README.md", content, load_default_pack())

    assert len(findings) == 1
    assert findings[0].rule == "purpose-contract"
    assert detail in findings[0].detail


def test_purpose_contract_ignores_headings_and_markers_inside_code_fences() -> None:
    content = (
        "# Project\n\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates fence parsing" -->\n'
        "<!-- clean-docs:purpose -->\n"
        "Use this page when source claims can drift. It gives maintainers a checked repair path.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "```markdown\n# Example\n<!-- clean-docs:purpose -->\n"
        "<!-- clean-docs:end purpose -->\n```\n"
    )

    assert check_document("README.md", content, load_default_pack()) == []


def test_prohibited_boosters_do_not_treat_headings_as_prose() -> None:
    content = (
        "# Project\n\n"
        '<!-- clean-docs:allow preamble-contract reason="Fixture isolates heading policy" -->\n'
        "<!-- clean-docs:purpose -->\n"
        "Use this page when source claims can drift. It gives maintainers a checked repair path.\n"
        "<!-- clean-docs:end purpose -->\n\n## Work simply\n"
    )

    assert check_document("README.md", content, load_default_pack()) == []


def test_bootstrap_marks_author_prose_and_refuses_a_title_restatement() -> None:
    authored = "# Project\n\nMaintainers use this guide before changing the API.\n\n## Next\n"
    marked = ensure_purpose_contract(authored)

    contract = marked.split(PURPOSE_BEGIN, 1)[1].split(PURPOSE_END, 1)[0]
    assert "Maintainers use this guide before changing the API." in contract
    assert ensure_purpose_contract(marked) == marked

    replaced = ensure_purpose_contract("# Project guide\n\nThis is the project guide.\n")
    assert replaced == "# Project guide\n\nThis is the project guide.\n"

    replaced = ensure_purpose_contract(
        "# Project guide\n\nThis is the project guide.\n", fallback=True
    )
    assert replaced == "# Project guide\n\nThis is the project guide.\n"


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


def test_preamble_contract_requires_point_action_and_proof_in_first_fifteen_lines() -> None:
    missing = (
        f"# Queue\n\n{REGISTER_PROFILE}\n<!-- clean-docs:purpose -->\n"
        "Queue is a task runner for maintainers who need source-bound operating facts.\n"
        "<!-- clean-docs:end purpose -->\n"
    )
    assert [
        finding.rule for finding in check_document("README.md", missing, load_default_pack())
    ] == ["preamble-contract"]

    decorative = (
        missing
        + "\n![Decorative diagram](docs/diagram.svg)\n\n"
        + "```yaml\nmode: preview\n```\n"
    )
    assert [
        finding.rule for finding in check_document("README.md", decorative, load_default_pack())
    ] == ["preamble-contract"]

    complete = (
        missing
        + "\n**[Run the first task](docs/start.md)**\n\n"
        + "[Verification result](docs/result.md)\n"
    )
    assert check_document("README.md", complete, load_default_pack()) == []


@pytest.mark.parametrize(
    ("sentence", "rule"),
    [
        (
            "Coordination, implementation, and validation obscure who does the work.",
            "nominalization-density",
        ),
        (
            "This demonstrates the boundary instead of naming its consequence.",
            "significance-narration",
        ),
        (
            "The model may phrase only supplied facts unless a reviewer intervenes except in references.",
            "qualifier-density",
        ),
    ],
)
def test_register_rules_fire_on_known_bad_shapes(sentence: str, rule: str) -> None:
    content = (
        f"# Queue\n\n{REGISTER_PROFILE}\n<!-- clean-docs:purpose -->\n"
        "Queue is a task runner for maintainers who need source-bound operating facts.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "**[Run the first task](docs/start.md)**\n\n"
        "[Verification result](docs/result.md)\n\n"
        f"{sentence}\n"
    )

    assert rule in {
        finding.rule for finding in check_document("README.md", content, load_default_pack())
    }


def test_register_rules_accept_concrete_varied_prose() -> None:
    content = (
        f"# Queue\n\n{REGISTER_PROFILE}\n<!-- clean-docs:purpose -->\n"
        "Queue is a task runner for maintainers who need source-bound operating facts.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "**[Run the first task](docs/start.md)**\n\n"
        "[Verification result](docs/result.md)\n\n"
        "The source owns the command. Bind it once. The gate names the stale row after the "
        "source changes, so the maintainer knows what to repair.\n"
    )

    assert check_document("README.md", content, load_default_pack()) == []


def test_truth_yield_preserves_an_honest_qualifier_collision() -> None:
    content = (
        f"# Queue\n\n{REGISTER_PROFILE}\n<!-- clean-docs:purpose -->\n"
        "Queue is a task runner for maintainers who need source-bound operating facts.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "**[Run the first task](docs/start.md)**\n\n"
        "[Verification result](docs/result.md)\n\n"
        '<!-- clean-docs:yield rule="qualifier-density" to="truth-honesty" '
        'reason="Three independent safety boundaries must remain attached" -->\n'
        "The model may phrase only supplied facts unless the provider fails, except in replay.\n"
    )

    assert check_document("README.md", content, load_default_pack()) == []


def test_truth_yield_does_not_disable_the_rule_for_later_prose() -> None:
    content = (
        f"# Queue\n\n{REGISTER_PROFILE}\n<!-- clean-docs:purpose -->\n"
        "Queue is a task runner for maintainers who need source-bound operating facts.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "**[Run the first task](docs/start.md)**\n\n"
        "[Verification result](docs/result.md)\n\n"
        '<!-- clean-docs:yield rule="qualifier-density" to="truth-honesty" '
        'reason="Three independent safety boundaries must remain attached" -->\n'
        "The model may phrase only supplied facts unless the provider fails, except in replay.\n\n"
        "The runner may write only one file unless the plan expands, except in migration.\n"
    )

    findings = [
        finding
        for finding in check_document("README.md", content, load_default_pack())
        if finding.rule == "qualifier-density"
    ]

    assert len(findings) == 1
    assert findings[0].line == 15


def test_sentence_variance_tension_keeps_required_presence_but_changes_rhythm() -> None:
    content = (
        f"# Queue\n\n{REGISTER_PROFILE}\n<!-- clean-docs:purpose -->\n"
        "Queue is a task runner for maintainers who need source-bound operating facts.\n"
        "<!-- clean-docs:end purpose -->\n\n"
        "**[Run the first task](docs/start.md)**\n\n"
        "[Verification result](docs/result.md)\n\n"
        "The source records each public command before the renderer builds the page for repository maintainers today. "
        "The binding compares that source with the declared table during every repository check made by maintainers. "
        "The gate then names the stale binding before the change can merge into the repository's protected branch.\n"
    )
    assert "sentence-variance" in {
        finding.rule for finding in check_document("README.md", content, load_default_pack())
    }

    repaired = content.replace(
        "The binding compares that source with the declared table during every repository check made by maintainers. ",
        "The binding is the tripwire. ",
    )
    assert "sentence-variance" not in {
        finding.rule for finding in check_document("README.md", repaired, load_default_pack())
    }
