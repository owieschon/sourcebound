from __future__ import annotations

import argparse
import json
from pathlib import Path


VALE_SHA256 = "968c6d8bf2052bc97aa24274234cc466dbcc249b55ace33dd382c2cdfa93b08c"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def private_root(value: object) -> Path:
    require(isinstance(value, str) and value, "private root is missing")
    raw = Path(value)
    require(raw.is_absolute(), "private root is not absolute")
    require(".." not in raw.parts, "private root contains parent traversal")
    canonical = raw.resolve(strict=False)
    private = Path("/private")
    require(
        canonical != private and canonical.is_relative_to(private),
        "private root is not an isolated private directory",
    )
    return canonical


def private_path(value: object, root: Path, name: str) -> Path:
    require(isinstance(value, str) and value, f"{name} is missing")
    raw = Path(value)
    require(raw.is_absolute(), f"{name} is not absolute")
    require(".." not in raw.parts, f"{name} contains parent traversal")
    canonical = raw.resolve(strict=False)
    require(canonical != root and canonical.is_relative_to(root), f"{name} escapes private root")
    return canonical


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--require-wheel", action="store_true")
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    require(receipt.get("schema") == "sourcebound.toolchain-fixture.v1", "wrong receipt schema")
    require(len(receipt.get("staged_tree", "")) == 40, "missing staged tree")
    inputs = receipt.get("input_sha256", {})
    require(set(inputs) == {
        "tests/contracts/run_toolchain_fixture.py",
        "examples/complementary-toolchain/src/actions.py",
        "examples/complementary-toolchain/README.md",
    }, "wrong tree-bound input set")
    require(all(len(digest) == 64 for digest in inputs.values()), "invalid input digest")
    paths = receipt.get("private_paths", {})
    root = private_root(paths.get("private_root"))
    for name, value in paths.items():
        if name == "private_root":
            continue
        private_path(value, root, name)
    vale = receipt.get("vale", {})
    require(vale.get("version") == "3.15.1" and vale.get("archive_sha256") == VALE_SHA256, "wrong Vale identity")
    require(len(vale.get("binary_sha256", "")) == 64, "missing Vale binary digest")
    runtime = receipt.get("sourcebound_runtime", {})
    require(
        runtime.get("installation") in {"source-tree", "wheel"},
        "missing Sourcebound runtime identity",
    )
    if args.require_wheel:
        require(runtime.get("installation") == "wheel", "fixture did not use a wheel")
        require(
            len(runtime.get("wheel_sha256", "")) == 64,
            "missing wheel digest",
        )
        require(
            runtime.get("system_site_packages") is False,
            "wheel fixture inherited system site-packages",
        )
        require(
            private_path(
                runtime.get("module_path"),
                root,
                "wheel module path",
            ).is_relative_to(
                private_path(
                    runtime.get("site_packages"),
                    root,
                    "wheel site-packages path",
                )
            ),
            "wheel module escaped its isolated site-packages",
        )
        require(
            private_path(
                runtime.get("distribution_path"),
                root,
                "wheel distribution path",
            ).is_relative_to(
                private_path(
                    runtime.get("site_packages"),
                    root,
                    "wheel site-packages path",
                )
            ),
            "wheel distribution escaped its isolated site-packages",
        )
        require(
            runtime.get("direct_url_archive_hash")
            == f"sha256={runtime.get('wheel_sha256')}",
            "wheel provenance digest mismatch",
        )
        require(
            len(runtime.get("direct_url_sha256", "")) == 64,
            "missing wheel provenance receipt",
        )
    containment = receipt.get("containment", receipt.get("network", {}))
    require(len(containment.get("profile_sha256", "")) == 64, "missing sandbox profile")
    allowed_read_roots = containment.get("allowed_read_roots", [])
    require(isinstance(allowed_read_roots, list), "containment allowlist is invalid")
    for path in allowed_read_roots:
        require(isinstance(path, str) and path, "containment allowlist is invalid")
        raw = Path(path)
        require(raw.is_absolute() and ".." not in raw.parts, "containment allowlist is invalid")
        canonical = raw.resolve(strict=False)
        require(
            canonical in {root, Path("/System"), Path("/usr"), Path("/dev")}
            or canonical.is_relative_to(Path("/Library/Frameworks/Python.framework")),
            "containment allowlist exposes an unapproved host root",
        )
    if args.require_wheel:
        require(
            bool(containment.get("allowed_read_roots")),
            "wheel fixture lacks a containment allowlist",
        )
        require(
            containment.get("private_probe", {}).get("exit_code") == 0,
            "contained private-root probe failed",
        )
    require(
        containment.get("egress_probe", {}).get("exit_code") != 0,
        "egress probe succeeded",
    )
    if args.require_wheel:
        require(containment.get("egress_reached") is True, "egress probe did not reach the socket call")
    if "host_read_probe" in containment:
        require(
            containment["host_read_probe"].get("exit_code") != 0,
            "host-read probe succeeded",
        )
        if args.require_wheel:
            require(
                containment.get("host_read_reached") is True,
                "host-read probe did not reach the denied file read",
            )
    elif args.require_wheel:
        raise SystemExit("wheel fixture lacks a host-read containment probe")
    runs = receipt.get("runs", {})
    expected = {
        "sourcebound_baseline": 0,
        "sourcebound_mutation": 1,
        "vale_baseline": 0,
        "vale_mutation": 0,
    }
    require(set(runs) == set(expected), "wrong execution set")
    for name, status in expected.items():
        run = runs[name]
        require(run.get("exit_code") == status, f"{name} status mismatch")
        require(run.get("argv"), f"{name} missing argv")
    require("vale" in Path(runs["vale_baseline"]["argv"][3]).name, "Vale binary was not invoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
