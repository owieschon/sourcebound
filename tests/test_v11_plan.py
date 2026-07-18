from pathlib import Path

from clean_docs.engine import evaluate


PROJECT = Path(__file__).parents[1]


def test_current_product_contract_excludes_historical_and_future_state() -> None:
    specification = (PROJECT / "CLEAN_DOCS_SPEC.md").read_text()

    assert "# Current clean-docs product contract" in specification
    assert "An outcome with `\"ok\": true` means the configured contract passed" in specification
    assert "`drive --changed`" not in specification
    assert "### Version 0.3" not in specification
    assert "complete example" not in specification.lower()
    assert "infer or authorize product goals" in specification


def test_current_assurance_table_is_bound_to_the_capability_registry() -> None:
    specification = (PROJECT / "CLEAN_DOCS_SPEC.md").read_text()
    results = {
        result.binding_id: result
        for result in evaluate(PROJECT, PROJECT / ".clean-docs.yml")
    }

    assert "assurance-boundaries" in results
    assert not results["assurance-boundaries"].changed
    assert "Cataloged surfaces check prose" not in specification
    assert "Every cataloged item needs or has a reader-facing explanation" in specification


def test_historical_build_plan_is_archived_and_labels_its_authority() -> None:
    archived = (PROJECT / "docs/archive/v1/BUILD_PLAN.md").read_text()

    assert archived.startswith("# Archived clean-docs build plan through Version 1.1")
    assert "not a current product contract" in " ".join(archived.split())
    assert "### Version 1.1: Governed learning layer" in archived
