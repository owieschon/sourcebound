from pathlib import Path

from scripts.run_acceptance import load_registry


ROOT = Path(__file__).parents[1]


def test_version_12a_registry_names_every_scenario() -> None:
    release, cases = load_registry(ROOT / "tests/v12-acceptance.yml")

    assert release == "1.2A"
    assert [case.id for case in cases] == [
        "coverage-complete-no-impact",
        "implementation-is-not-interface",
        "typescript-interface-fingerprint",
        "line-move-not-public-impact",
        "unknown-cannot-become-no-impact",
        "public-default-obligations",
        "affected-contract-traversal",
        "generated-output-non-recursion",
        "merge-base-history",
        "scope-tension",
        "legacy-overview-compatibility",
        "cross-runtime-receipt-portability",
        "bounded-context-authority",
        "required-context-overflow",
        "provider-failure-receipt",
        "provider-deadline-receipt",
        "provider-write-conflict",
        "effective-mapping-key-semantics",
        "bounded-candidate-ranking",
        "independent-fact-sensitivity",
        "wrong-fact-red-boundary",
        "ambiguous-mutation-unsupported",
        "shared-evaluation-primitive",
    ]
