from __future__ import annotations

import json
import sys
from pathlib import Path


VALE_SHA256 = "968c6d8bf2052bc97aa24274234cc466dbcc249b55ace33dd382c2cdfa93b08c"
DOC_INTEGRITY = "sha512-i+Ffu32WBMRnvzxhNwxTy6zpJODO2YLlDaqRNgXcbFaQGhFqATBOjZqkhvOMQvlzzikCfKhlWXWSyAg/HP2gzw=="


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    receipt = json.loads(Path(sys.argv[1]).read_text())
    require(receipt.get("schema") == "sourcebound.toolchain-fixture.v1", "wrong receipt schema")
    require(len(receipt.get("staged_tree", "")) == 40, "missing staged tree")
    inputs = receipt.get("input_sha256", {})
    require(set(inputs) == {
        "tests/contracts/run_toolchain_fixture.py",
        "examples/complementary-toolchain/.doc-detective.json",
        "examples/complementary-toolchain/doc-detective.spec.json",
        "examples/complementary-toolchain/src/actions.py",
        "examples/complementary-toolchain/README.md",
    }, "wrong tree-bound input set")
    require(all(len(digest) == 64 for digest in inputs.values()), "invalid input digest")
    paths = receipt.get("private_paths", {})
    root = Path(paths.get("private_root", ""))
    require(root.is_absolute(), "missing private root")
    for name, value in paths.items():
        try:
            Path(value).relative_to(root)
        except ValueError:
            raise SystemExit(f"{name} escapes private root")
    vale = receipt.get("vale", {})
    doc = receipt.get("doc_detective", {})
    require(vale.get("version") == "3.15.1" and vale.get("archive_sha256") == VALE_SHA256, "wrong Vale identity")
    require(len(vale.get("binary_sha256", "")) == 64, "missing Vale binary digest")
    require(doc.get("version") == "4.36.0" and doc.get("tarball_integrity") == DOC_INTEGRITY, "wrong Doc Detective identity")
    require(len(doc.get("binary_sha256", "")) == 64 and len(doc.get("package_lock_sha256", "")) == 64, "missing private install digest")
    require(doc.get("telemetry_send") is False, "telemetry is not disabled")
    network = receipt.get("network", {})
    require(len(network.get("profile_sha256", "")) == 64, "missing sandbox profile")
    require(network.get("egress_probe", {}).get("exit_code") != 0, "egress probe succeeded")
    runs = receipt.get("runs", {})
    expected = {
        "sourcebound_baseline": 0,
        "sourcebound_mutation": 1,
        "vale_baseline": 0,
        "vale_mutation": 0,
        "doc_detective_baseline": 0,
        "doc_detective_mutation": 0,
    }
    require(set(runs) == set(expected), "wrong execution set")
    for name, status in expected.items():
        run = runs[name]
        require(run.get("exit_code") == status, f"{name} status mismatch")
        require(run.get("argv"), f"{name} missing argv")
    require("vale" in Path(runs["vale_baseline"]["argv"][3]).name, "Vale binary was not invoked")
    require("doc-detective" in runs["doc_detective_baseline"]["argv"][3], "Doc Detective binary was not invoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
