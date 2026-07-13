from pathlib import Path

from scripts.run_acceptance import EXPECTED_IDS_BY_RELEASE, load_registry


ROOT = Path(__file__).parents[1]


def test_version_zero_three_registry_names_all_six_scenarios() -> None:
    release, cases = load_registry(ROOT / "tests/v03-acceptance.yml")

    assert release == "0.3"
    assert len(cases) == 6
    assert {case.id for case in cases} == EXPECTED_IDS_BY_RELEASE["0.3"]
