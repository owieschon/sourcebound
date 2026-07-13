from pathlib import Path

from scripts.run_acceptance import load_registry


ROOT = Path(__file__).parents[1]


def test_version_10_registry_names_every_scenario() -> None:
    release, cases = load_registry(ROOT / "tests/v10-acceptance.yml")

    assert release == "1.0"
    assert len(cases) == 6
