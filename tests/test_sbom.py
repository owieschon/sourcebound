from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from scripts.build_sbom import render_sbom


def test_sbom_is_deterministic_and_describes_wheel_dependencies(tmp_path: Path) -> None:
    wheel = tmp_path / "clean_docs-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "clean_docs-1.0.0.dist-info/METADATA",
            "Metadata-Version: 2.4\n"
            "Name: clean-docs\n"
            "Version: 1.0.0\n"
            "Requires-Dist: PyYAML>=6.0\n",
        )
        archive.writestr(
            "clean_docs/adapters/mdx_dependencies.json",
            json.dumps(
                {
                    "schema": "clean-docs.mdx-dependencies.v1",
                    "lock_sha256": "0" * 64,
                    "packages": [
                        {
                            "integrity": "sha512-fixture",
                            "license": "MIT",
                            "name": "@mdx-js/mdx",
                            "version": "3.1.1",
                        }
                    ],
                }
            ),
        )

    first = render_sbom(wheel, 1_700_000_000)
    second = render_sbom(wheel, 1_700_000_000)
    payload = json.loads(first)

    assert first == second
    assert payload["spdxVersion"] == "SPDX-2.3"
    assert payload["packages"][0]["checksums"] == [
        {
            "algorithm": "SHA256",
            "checksumValue": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        }
    ]
    assert {item["name"] for item in payload["packages"]} == {
        "clean-docs",
        "PyYAML",
        "@mdx-js/mdx",
    }
    assert any(
        item["relationshipType"] == "DEPENDS_ON"
        for item in payload["relationships"]
    )
