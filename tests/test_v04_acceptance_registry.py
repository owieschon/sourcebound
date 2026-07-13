from pathlib import Path

from scripts.run_acceptance import EXPECTED_IDS_BY_RELEASE, load_registry


ROOT = Path(__file__).parents[1]


def test_version_zero_four_registry_names_all_eight_scenarios() -> None:
    release, cases = load_registry(ROOT / "tests/v04-acceptance.yml")

    assert release == "0.4"
    assert len(cases) == 8
    assert {case.id for case in cases} == EXPECTED_IDS_BY_RELEASE["0.4"]
