from pathlib import Path

from scripts.run_acceptance import load_registry


ROOT = Path(__file__).parents[1]


def test_version_11_registry_names_every_scenario() -> None:
    release, cases = load_registry(ROOT / "tests/v11-acceptance.yml")

    assert release == "1.1"
    assert [case.id for case in cases] == [
        "public-repository-legibility",
        "tutorial-from-a-clean-room",
        "postmortem-facts-cannot-drift",
        "deterministic-seam-boundary",
        "additive-learning-corpus",
        "fresh-reader-learning-path",
    ]
