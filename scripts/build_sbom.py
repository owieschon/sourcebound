#!/usr/bin/env python3
"""Build a deterministic SPDX 2.3 SBOM for one clean-docs wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9.-]", "-", value)
    return f"SPDXRef-Package-{normalized}"


def render_sbom(wheel: Path, source_date_epoch: int) -> str:
    wheel_bytes = wheel.read_bytes()
    wheel_digest = hashlib.sha256(wheel_bytes).hexdigest()
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError("wheel must contain one dist-info/METADATA file")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
        mdx_manifest_names = [
            name
            for name in archive.namelist()
            if name.endswith("clean_docs/adapters/mdx_dependencies.json")
        ]
        if len(mdx_manifest_names) != 1:
            raise ValueError("wheel must contain one MDX dependency manifest")
        mdx_manifest = json.loads(
            archive.read(mdx_manifest_names[0]).decode("utf-8")
        )
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise ValueError("wheel metadata must contain Name and Version")
    root_id = _identifier(name)
    packages: list[dict[str, object]] = [
        {
            "SPDXID": root_id,
            "name": name,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "copyrightText": "NOASSERTION",
            "checksums": [
                {"algorithm": "SHA256", "checksumValue": wheel_digest}
            ],
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:pypi/{name}@{version}",
                }
            ],
        }
    ]
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_id,
        }
    ]
    requirements = sorted(set(metadata.get_all("Requires-Dist", [])))
    for requirement in requirements:
        dependency_name = re.split(r"[ ;(<>=!~]", requirement, maxsplit=1)[0]
        dependency_id = _identifier(dependency_name)
        packages.append(
            {
                "SPDXID": dependency_id,
                "name": dependency_name,
                "versionInfo": requirement,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": root_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency_id,
            }
        )
    if (
        not isinstance(mdx_manifest, dict)
        or mdx_manifest.get("schema") != "clean-docs.mdx-dependencies.v1"
        or not isinstance(mdx_manifest.get("packages"), list)
    ):
        raise ValueError("wheel MDX dependency manifest has an unsupported schema")
    seen_mdx: set[tuple[str, str, str]] = set()
    for package in mdx_manifest["packages"]:
        if not isinstance(package, dict) or not all(
            isinstance(package.get(field), str)
            for field in ("name", "version", "integrity", "license")
        ):
            raise ValueError("wheel MDX dependency manifest has an invalid package")
        identity = (
            package["name"],
            package["version"],
            package["integrity"],
        )
        if identity in seen_mdx:
            continue
        seen_mdx.add(identity)
        dependency_id = _identifier(
            f"npm-{package['name']}-{package['version']}"
        )
        packages.append(
            {
                "SPDXID": dependency_id,
                "name": package["name"],
                "versionInfo": package["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": package["license"],
                "licenseDeclared": package["license"],
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": (
                            f"pkg:npm/{package['name']}@{package['version']}"
                        ),
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": root_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency_id,
            }
        )
    created = datetime.fromtimestamp(source_date_epoch, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    payload = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{name}-{version}",
        "documentNamespace": (
            "https://github.com/owieschon/clean-docs/sbom/" + wheel_digest
        ),
        "creationInfo": {
            "created": created,
            "creators": ["Tool: clean-docs-build-sbom"],
            "licenseListVersion": "3.26",
        },
        "packages": packages,
        "relationships": relationships,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        rendered = render_sbom(args.wheel, args.source_date_epoch)
        args.out.write_text(rendered)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"sbom: {exc}")
        return 2
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
