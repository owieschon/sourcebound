from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from clean_docs.capabilities import PRODUCT_OVERVIEW
from clean_docs.errors import ConfigurationError
from clean_docs.manifest import load_manifest
from clean_docs.policy import check_document
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


def test_standard_change_makes_pack_stale(tmp_path: Path) -> None:
    standard = tmp_path / "STANDARD.md"
    standard.write_text((ROOT / "STANDARD.md").read_text() + "\nA new rule.\n")
    pack = ROOT / "src/clean_docs/standards/default.json"
    assert not pack_matches_standard(standard, pack)


def test_policy_uses_compiled_booster_registry() -> None:
    pack = load_default_pack()
    findings = check_document("README.md", "# Product\n\nA powerful tool.\n", pack)
    assert [(finding.rule, finding.line) for finding in findings] == [
        ("prohibited-booster", 3)
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
