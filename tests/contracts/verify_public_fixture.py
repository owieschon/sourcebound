from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]
EXPECTED = {
    "examples/complementary-toolchain/.sourcebound.yml",
    "examples/complementary-toolchain/.vale.ini",
    "examples/complementary-toolchain/README.md",
    "examples/complementary-toolchain/docs/guide.md",
    "examples/complementary-toolchain/src/actions.py",
    "examples/complementary-toolchain/styles/Sourcebound/NoVery.yml",
    "tests/contracts/run_toolchain_fixture.py",
    "tests/contracts/test_core_clarity_contract.py",
    "tests/contracts/test_ecosystem_boundary.py",
    "tests/contracts/test_verify_toolchain_receipt.py",
    "tests/contracts/verify_contract_commit.py",
    "tests/contracts/verify_public_fixture.py",
    "tests/contracts/verify_red_contract.py",
    "tests/contracts/verify_runtime_review_receipt.py",
    "tests/contracts/verify_toolchain_receipt.py",
}


def main() -> int:
    found = {
        path.relative_to(ROOT).as_posix()
        for root in (ROOT / "examples" / "complementary-toolchain", ROOT / "tests" / "contracts")
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if found != EXPECTED:
        raise SystemExit(f"public fixture allowlist mismatch: {sorted(found ^ EXPECTED)}")
    forbidden = "post" + "hog"
    for path in sorted(found):
        if forbidden in (ROOT / path).read_text().lower():
            raise SystemExit(f"prohibited vendor residue: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
