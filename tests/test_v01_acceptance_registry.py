from pathlib import Path

from scripts.run_acceptance import EXPECTED_IDS, load_cases


ROOT = Path(__file__).parents[1]


def test_version_zero_one_registry_names_all_nine_scenarios() -> None:
    cases = load_cases(ROOT / "tests/v01-acceptance.yml")

    assert len(cases) == 9
    assert {case.id for case in cases} == EXPECTED_IDS
