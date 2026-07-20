#!/usr/bin/env python3
"""Create one GitHub release or verify that the exact release already exists."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


PUBLICATION_SCHEMA = "sourcebound.release-publication.v1"
PROVENANCE_PREDICATE = "https://slsa.dev/provenance/v1"
SBOM_PREDICATE = "https://spdx.dev/Document/v2.3"


class PublicationError(RuntimeError):
    """Release state cannot be created or verified without mutation."""


@dataclass(frozen=True)
class LocalAsset:
    path: Path
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class RemoteAsset:
    name: str
    size: int


@dataclass(frozen=True)
class ReleaseState:
    tag: str
    draft: bool
    prerelease: bool
    assets: tuple[RemoteAsset, ...]


class ReleaseClient(Protocol):
    def view(self, tag: str) -> ReleaseState | None: ...

    def create(self, tag: str, assets: tuple[LocalAsset, ...], prerelease: bool) -> bool: ...

    def download(self, tag: str, asset: str, destination: Path) -> Path: ...

    def verify_attestation(
        self,
        artifact: Path,
        *,
        source_digest: str,
        predicate_type: str,
    ) -> None: ...


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        list(args),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if check and process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise PublicationError(f"{' '.join(args)} failed: {detail}")
    return process


class GitHubReleaseClient:
    def __init__(self, repo: str) -> None:
        self.repo = repo

    def view(self, tag: str) -> ReleaseState | None:
        process = _run(
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            self.repo,
            "--json",
            "tagName,isDraft,isPrerelease,assets",
            check=False,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip()
            if "release not found" in detail.lower() or "not found" in detail.lower():
                return None
            raise PublicationError(f"cannot inspect release {tag}: {detail}")
        payload = json.loads(process.stdout)
        return ReleaseState(
            tag=str(payload["tagName"]),
            draft=bool(payload["isDraft"]),
            prerelease=bool(payload["isPrerelease"]),
            assets=tuple(
                RemoteAsset(name=str(asset["name"]), size=int(asset["size"]))
                for asset in payload["assets"]
            ),
        )

    def create(self, tag: str, assets: tuple[LocalAsset, ...], prerelease: bool) -> bool:
        args = [
            "gh",
            "release",
            "create",
            tag,
            *(str(asset.path) for asset in assets),
            "--repo",
            self.repo,
            "--verify-tag",
            "--generate-notes",
        ]
        if prerelease:
            args.append("--prerelease")
        return _run(*args, check=False).returncode == 0

    def download(self, tag: str, asset: str, destination: Path) -> Path:
        _run(
            "gh",
            "release",
            "download",
            tag,
            "--repo",
            self.repo,
            "--pattern",
            asset,
            "--dir",
            str(destination),
            "--clobber",
        )
        return destination / asset

    def verify_attestation(
        self,
        artifact: Path,
        *,
        source_digest: str,
        predicate_type: str,
    ) -> None:
        _run(
            "gh",
            "attestation",
            "verify",
            str(artifact),
            "--repo",
            self.repo,
            "--signer-workflow",
            f"{self.repo}/.github/workflows/release.yml",
            "--source-digest",
            source_digest,
            "--predicate-type",
            predicate_type,
        )


def collect_assets(directory: Path) -> tuple[LocalAsset, ...]:
    paths = sorted(path for path in directory.iterdir() if path.is_file())
    if not paths:
        raise PublicationError(f"release directory is empty: {directory}")
    return tuple(
        LocalAsset(
            path=path,
            name=path.name,
            size=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in paths
    )


def resolve_tag_target(tag: str) -> str:
    process = _run("git", "rev-parse", f"{tag}^{{}}")
    target = process.stdout.strip()
    if len(target) != 40:
        raise PublicationError(f"tag {tag} did not resolve to a full commit")
    return target


def _verify_state(
    state: ReleaseState,
    *,
    tag: str,
    prerelease: bool,
    assets: tuple[LocalAsset, ...],
) -> None:
    conflicts: list[str] = []
    if state.tag != tag:
        conflicts.append(f"tag is {state.tag!r}, expected {tag!r}")
    if state.draft:
        conflicts.append("release is a draft")
    if state.prerelease != prerelease:
        conflicts.append(
            f"prerelease is {state.prerelease}, expected {prerelease}"
        )
    expected = {asset.name: asset.size for asset in assets}
    observed = {asset.name: asset.size for asset in state.assets}
    if observed != expected:
        conflicts.append(
            "assets differ: "
            f"observed={json.dumps(observed, sort_keys=True)} "
            f"expected={json.dumps(expected, sort_keys=True)}"
        )
    if conflicts:
        raise PublicationError("release conflict; " + "; ".join(conflicts))


def publish_release(
    client: ReleaseClient,
    *,
    repo: str,
    tag: str,
    source_digest: str,
    prerelease: bool,
    assets: tuple[LocalAsset, ...],
) -> dict[str, object]:
    state = client.view(tag)
    publication = "verified-existing"
    if state is None:
        publication = "created"
        created = client.create(tag, assets, prerelease)
        state = client.view(tag)
        if state is None:
            raise PublicationError("release remains absent after create attempt")
        if not created:
            publication = "verified-race"

    _verify_state(state, tag=tag, prerelease=prerelease, assets=assets)
    with tempfile.TemporaryDirectory(prefix="sourcebound-publication-") as temporary:
        downloaded_root = Path(temporary)
        for expected in assets:
            downloaded = client.download(tag, expected.name, downloaded_root)
            if not downloaded.is_file():
                raise PublicationError(f"release download missing: {expected.name}")
            actual_digest = hashlib.sha256(downloaded.read_bytes()).hexdigest()
            if actual_digest != expected.sha256:
                raise PublicationError(
                    f"release conflict; {expected.name} sha256 is {actual_digest}, "
                    f"expected {expected.sha256}"
                )

    wheels = tuple(asset for asset in assets if asset.name.endswith(".whl"))
    if len(wheels) != 1:
        raise PublicationError(f"expected one wheel for attestation, found {len(wheels)}")
    client.verify_attestation(
        wheels[0].path,
        source_digest=source_digest,
        predicate_type=PROVENANCE_PREDICATE,
    )
    client.verify_attestation(
        wheels[0].path,
        source_digest=source_digest,
        predicate_type=SBOM_PREDICATE,
    )
    return {
        "schema": PUBLICATION_SCHEMA,
        "status": publication,
        "repository": repo,
        "tag": tag,
        "tag_target": source_digest,
        "prerelease": prerelease,
        "assets": [
            {"name": asset.name, "bytes": asset.size, "sha256": asset.sha256}
            for asset in assets
        ],
        "attestations": {
            "artifact": wheels[0].name,
            "predicate_types": [PROVENANCE_PREDICATE, SBOM_PREDICATE],
            "verified": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source-digest", required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prerelease", action="store_true")
    args = parser.parse_args()
    try:
        resolved_target = resolve_tag_target(args.tag)
        if resolved_target != args.source_digest:
            raise PublicationError(
                f"tag {args.tag} targets {resolved_target}, "
                f"expected {args.source_digest}"
            )
        assets = collect_assets(args.dist.resolve())
        receipt = publish_release(
            GitHubReleaseClient(args.repo),
            repo=args.repo,
            tag=args.tag,
            source_digest=args.source_digest,
            prerelease=args.prerelease,
            assets=assets,
        )
        args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    except (
        json.JSONDecodeError,
        OSError,
        PublicationError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"publish release: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
