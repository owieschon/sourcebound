from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.publish_release import (
    PROVENANCE_PREDICATE,
    SBOM_PREDICATE,
    LocalAsset,
    PublicationError,
    ReleaseState,
    RemoteAsset,
    publish_release,
    resolve_tag_target,
)


class FakeReleaseClient:
    def __init__(
        self,
        state: ReleaseState | None,
        remote_bytes: dict[str, bytes],
        *,
        create_result: bool = True,
    ) -> None:
        self.state = state
        self.remote_bytes = remote_bytes
        self.create_result = create_result
        self.created = 0
        self.downloaded: list[str] = []
        self.attestations: list[tuple[str, str]] = []

    def view(self, tag: str) -> ReleaseState | None:
        return self.state

    def create(
        self,
        tag: str,
        assets: tuple[LocalAsset, ...],
        prerelease: bool,
    ) -> bool:
        self.created += 1
        self.state = ReleaseState(
            tag=tag,
            draft=False,
            prerelease=prerelease,
            assets=tuple(RemoteAsset(asset.name, asset.size) for asset in assets),
        )
        self.remote_bytes = {asset.name: asset.path.read_bytes() for asset in assets}
        return self.create_result

    def download(self, tag: str, asset: str, destination: Path) -> Path:
        self.downloaded.append(asset)
        output = destination / asset
        output.write_bytes(self.remote_bytes[asset])
        return output

    def verify_attestation(
        self,
        artifact: Path,
        *,
        source_digest: str,
        predicate_type: str,
    ) -> None:
        self.attestations.append((source_digest, predicate_type))


def _assets(tmp_path: Path) -> tuple[LocalAsset, ...]:
    files = {
        "sourcebound-1.2.0-py3-none-any.whl": b"wheel",
        "sourcebound-1.2.0-py3-none-any.spdx.json": b"sbom",
        "SHA256SUMS": b"checksums",
        "release.json": b"release receipt",
    }
    assets = []
    for name, content in files.items():
        path = tmp_path / name
        path.write_bytes(content)
        assets.append(
            LocalAsset(
                path=path,
                name=name,
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    return tuple(sorted(assets, key=lambda asset: asset.name))


def _state(
    assets: tuple[LocalAsset, ...],
    *,
    prerelease: bool = True,
) -> ReleaseState:
    return ReleaseState(
        tag="v1.2.0rc3",
        draft=False,
        prerelease=prerelease,
        assets=tuple(RemoteAsset(asset.name, asset.size) for asset in assets),
    )


def test_absent_release_is_created_then_verified(tmp_path: Path) -> None:
    assets = _assets(tmp_path)
    client = FakeReleaseClient(None, {})

    receipt = publish_release(
        client,
        repo="owner/repo",
        tag="v1.2.0rc3",
        source_digest="a" * 40,
        prerelease=True,
        assets=assets,
    )

    assert receipt["status"] == "created"
    assert client.created == 1
    assert sorted(client.downloaded) == sorted(asset.name for asset in assets)
    assert client.attestations == [
        ("a" * 40, PROVENANCE_PREDICATE),
        ("a" * 40, SBOM_PREDICATE),
    ]


def test_tag_target_is_resolved_from_git() -> None:
    target = resolve_tag_target("HEAD")

    assert len(target) == 40
    assert all(character in "0123456789abcdef" for character in target)


def test_identical_release_is_verified_without_mutation(tmp_path: Path) -> None:
    assets = _assets(tmp_path)
    client = FakeReleaseClient(
        _state(assets),
        {asset.name: asset.path.read_bytes() for asset in assets},
    )

    receipt = publish_release(
        client,
        repo="owner/repo",
        tag="v1.2.0rc3",
        source_digest="b" * 40,
        prerelease=True,
        assets=assets,
    )

    assert receipt["status"] == "verified-existing"
    assert client.created == 0


def test_create_race_verifies_identical_winner(tmp_path: Path) -> None:
    assets = _assets(tmp_path)
    client = FakeReleaseClient(None, {}, create_result=False)

    receipt = publish_release(
        client,
        repo="owner/repo",
        tag="v1.2.0rc3",
        source_digest="c" * 40,
        prerelease=True,
        assets=assets,
    )

    assert receipt["status"] == "verified-race"
    assert client.created == 1


@pytest.mark.parametrize("conflict", ["asset-name", "asset-bytes", "prerelease"])
def test_conflicting_release_fails_without_remote_mutation(
    tmp_path: Path,
    conflict: str,
) -> None:
    assets = _assets(tmp_path)
    remote_bytes = {asset.name: asset.path.read_bytes() for asset in assets}
    state = _state(assets)
    if conflict == "asset-name":
        state = ReleaseState(
            tag=state.tag,
            draft=False,
            prerelease=True,
            assets=state.assets[:-1],
        )
    elif conflict == "asset-bytes":
        remote_bytes[assets[0].name] = b"x" * assets[0].size
    else:
        state = _state(assets, prerelease=False)
    client = FakeReleaseClient(state, remote_bytes)

    with pytest.raises(PublicationError, match="release conflict"):
        publish_release(
            client,
            repo="owner/repo",
            tag="v1.2.0rc3",
            source_digest="d" * 40,
            prerelease=True,
            assets=assets,
        )

    assert client.created == 0
