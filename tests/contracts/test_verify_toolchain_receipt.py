from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
VERIFIER = ROOT / "tests/contracts/verify_toolchain_receipt.py"
INPUTS = {
    "tests/contracts/run_toolchain_fixture.py",
    "examples/complementary-toolchain/src/actions.py",
    "examples/complementary-toolchain/README.md",
}


def _receipt(root: Path) -> dict[str, object]:
    digest = "a" * 64
    runs = {
        "sourcebound_baseline": 0,
        "sourcebound_mutation": 1,
        "vale_baseline": 0,
        "vale_mutation": 0,
    }
    return {
        "schema": "sourcebound.toolchain-fixture.v1",
        "staged_tree": "b" * 40,
        "input_sha256": {name: digest for name in INPUTS},
        "private_paths": {
            "private_root": str(root),
            "home": str(root / "home"),
            "vale_binary": str(root / "vale/vale"),
        },
        "vale": {
            "version": "3.15.1",
            "archive_sha256": "968c6d8bf2052bc97aa24274234cc466dbcc249b55ace33dd382c2cdfa93b08c",
            "binary_sha256": digest,
        },
        "sourcebound_runtime": {"installation": "source-tree"},
        "containment": {
            "profile_sha256": digest,
            "allowed_read_roots": [
                str(root),
                "/System",
                "/usr",
                "/dev",
                str(Path(sys.executable).resolve().parents[3]),
            ],
            "private_probe": {"exit_code": 0},
            "egress_reached": True,
            "egress_probe": {"exit_code": 1},
            "host_read_reached": True,
            "host_read_probe": {"exit_code": 1},
        },
        "runs": {
            name: {
                "exit_code": status,
                "argv": ["sandbox-exec", "-f", "profile", "tool" if "vale" not in name else "vale"],
            }
            for name, status in runs.items()
        },
    }


def _verify(path: Path, *, wheel: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER), str(path), *(["--require-wheel"] if wheel else [])],
        text=True,
        capture_output=True,
        check=False,
    )


def test_toolchain_receipt_rejects_empty_relative_sibling_and_traversal_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"
    root.mkdir()
    receipt = _receipt(root)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    assert _verify(path).returncode == 0

    invalid_values = ["", "relative/home", str(tmp_path / "private-other"), str(root / ".." / "outside")]
    for value in invalid_values:
        receipt["private_paths"]["home"] = value  # type: ignore[index]
        path.write_text(json.dumps(receipt))
        assert _verify(path).returncode != 0

    receipt = _receipt(root)
    receipt["private_paths"]["private_root"] = "/"
    path.write_text(json.dumps(receipt))
    assert _verify(path).returncode != 0

    receipt = _receipt(root)
    receipt["private_paths"]["home"] = str(root)
    path.write_text(json.dumps(receipt))
    assert _verify(path).returncode != 0

    receipt = _receipt(root)
    receipt["containment"]["allowed_read_roots"] = ["/Users"]  # type: ignore[index]
    path.write_text(json.dumps(receipt))
    assert _verify(path).returncode != 0


def test_toolchain_receipt_requires_strict_wheel_identity_paths(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir()
    receipt = _receipt(root)
    site_packages = root / "venv/lib/python/site-packages"
    receipt["sourcebound_runtime"] = {
        "installation": "wheel",
        "wheel_sha256": "c" * 64,
        "system_site_packages": False,
        "module_path": str(site_packages / "sourcebound/__init__.py"),
        "site_packages": str(site_packages),
        "distribution_path": str(site_packages / "sourcebound-1.2.1.dist-info"),
        "direct_url_sha256": "d" * 64,
        "direct_url_archive_hash": "sha256=" + "c" * 64,
    }
    receipt["containment"]["allowed_read_roots"] = [  # type: ignore[index]
        str(root),
        "/System",
        "/usr",
        "/dev",
        str(Path(sys.executable).resolve().parents[3]),
    ]
    path = tmp_path / "wheel-receipt.json"
    path.write_text(json.dumps(receipt))
    assert _verify(path, wheel=True).returncode == 0

    receipt["containment"]["allowed_read_roots"] = [str(root)]  # type: ignore[index]
    path.write_text(json.dumps(receipt))
    assert _verify(path, wheel=True).returncode != 0

    receipt = _receipt(root)
    receipt["containment"]["allowed_read_roots"] = [  # type: ignore[index]
        str(root),
        "/System",
        "/usr",
        "/dev",
        str(Path(sys.executable).resolve().parents[3]),
        str(root),
    ]
    path.write_text(json.dumps(receipt))
    assert _verify(path).returncode != 0

    receipt = _receipt(root)
    receipt["containment"]["allowed_read_roots"] = [  # type: ignore[index]
        str(root),
        "/System",
        "/usr",
        "/dev",
        str(Path(sys.executable).resolve().parents[3]),
        "/Library",
    ]
    path.write_text(json.dumps(receipt))
    assert _verify(path).returncode != 0

    receipt["sourcebound_runtime"]["module_path"] = str(site_packages)  # type: ignore[index]
    path.write_text(json.dumps(receipt))
    assert _verify(path, wheel=True).returncode != 0

    receipt = _receipt(root)
    receipt["staged_tree"] = "not-a-commit"
    path.write_text(json.dumps(receipt))
    assert _verify(path).returncode != 0
