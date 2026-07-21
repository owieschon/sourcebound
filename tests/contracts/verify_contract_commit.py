from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]
EXPECTED = {
    "examples/complementary-toolchain/.doc-detective.json",
    "examples/complementary-toolchain/.sourcebound.yml",
    "examples/complementary-toolchain/.vale.ini",
    "examples/complementary-toolchain/README.md",
    "examples/complementary-toolchain/doc-detective.spec.json",
    "examples/complementary-toolchain/docs/guide.md",
    "examples/complementary-toolchain/src/actions.py",
    "examples/complementary-toolchain/styles/Sourcebound/NoVery.yml",
    "tests/contracts/run_toolchain_fixture.py",
    "tests/contracts/test_core_clarity_contract.py",
    "tests/contracts/test_ecosystem_boundary.py",
    "tests/contracts/verify_contract_commit.py",
    "tests/contracts/verify_public_fixture.py",
    "tests/contracts/verify_red_contract.py",
    "tests/contracts/verify_runtime_review_receipt.py",
    "tests/contracts/verify_toolchain_receipt.py",
}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], text=True, capture_output=True, check=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("commit")
    parser.add_argument("--runtime-receipt", type=Path, required=True)
    args = parser.parse_args()
    if git("status", "--porcelain"):
        raise SystemExit("worktree is not clean")
    if git("show", "-s", "--format=%s", args.commit) != "test: freeze core-clarity acceptance contracts":
        raise SystemExit("wrong frozen commit subject")
    parent = git("rev-parse", f"{args.commit}^")
    changed = set(filter(None, git("diff", "--name-only", parent, args.commit).splitlines()))
    if changed != EXPECTED:
        raise SystemExit(f"wrong committed file set: {sorted(changed ^ EXPECTED)}")
    receipt = json.loads(args.runtime_receipt.read_text())
    tree = git("rev-parse", f"{args.commit}^{{tree}}")
    if receipt.get("staged_tree") != tree:
        raise SystemExit("runtime receipt tree differs from committed tree")
    for path, digest in receipt.get("input_sha256", {}).items():
        blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{tree}:{path}"], capture_output=True, check=True).stdout
        if hashlib.sha256(blob).hexdigest() != digest:
            raise SystemExit(f"runtime input digest differs: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
