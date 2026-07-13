from scripts.benchmark_fixtures import CASES


def test_performance_suite_covers_each_supported_repository_shape() -> None:
    assert {case.name for case in CASES} == {"small", "medium", "monorepo"}
    assert all(case.files > 0 for case in CASES)
