from pathlib import Path

from clean_docs.engine import evaluate


PROJECT = Path(__file__).parents[1]


def test_current_product_contract_excludes_historical_and_future_state() -> None:
    specification = (PROJECT / "SOURCEBOUND_SPEC.md").read_text()

    assert "# Current sourcebound product contract" in specification
    assert (
        'An outcome with `"ok": true` means the configured contract passed'
        in specification
    )
    assert "`drive --changed`" not in specification
    assert "### Version 0.3" not in specification
    assert "complete example" not in specification.lower()
    assert "infer or authorize product goals" in specification


def test_current_assurance_table_is_bound_to_the_capability_registry() -> None:
    specification = (PROJECT / "SOURCEBOUND_SPEC.md").read_text()
    results = {
        result.binding_id: result
        for result in evaluate(PROJECT, PROJECT / ".sourcebound.yml")
    }

    assert "assurance-boundaries" in results
    assert not results["assurance-boundaries"].changed
    assert "Cataloged surfaces check prose" not in specification
    assert (
        "Every cataloged item needs or has a reader-facing explanation" in specification
    )
