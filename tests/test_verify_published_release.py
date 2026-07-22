from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import scripts.verify_published_release as publication


def _pypi_payload(wheel_name: str, digest: str) -> dict[str, Any]:
    return {
        "urls": [
            {
                "filename": wheel_name,
                "packagetype": "bdist_wheel",
                "url": f"https://files.pythonhosted.org/packages/{wheel_name}",
                "digests": {"sha256": digest},
            }
        ]
    }


def test_pypi_wheel_requires_one_file_on_the_expected_host() -> None:
    wheel_name = "sourcebound-1.2.2-py3-none-any.whl"
    digest = "a" * 64

    assert publication._pypi_wheel(_pypi_payload(wheel_name, digest), wheel_name) == (
        f"https://files.pythonhosted.org/packages/{wheel_name}",
        digest,
    )

    payload = _pypi_payload(wheel_name, digest)
    payload["urls"][0]["url"] = f"https://example.test/{wheel_name}"
    with pytest.raises(RuntimeError, match="outside files.pythonhosted.org"):
        publication._pypi_wheel(payload, wheel_name)


def test_checksum_digest_requires_one_exact_wheel_entry(tmp_path: Path) -> None:
    wheel_name = "sourcebound-1.2.2-py3-none-any.whl"
    digest = "b" * 64
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_text(f"{digest}  {wheel_name}\n")

    assert publication._checksum_digest(checksums, wheel_name) == digest

    checksums.write_text(f"{digest}  {wheel_name}\n{digest}  {wheel_name}\n")
    with pytest.raises(RuntimeError, match="exactly one digest"):
        publication._checksum_digest(checksums, wheel_name)


def test_smoke_installers_names_the_missing_pipx_prerequisite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(publication.importlib.util, "find_spec", lambda name: None)

    with pytest.raises(RuntimeError, match="pinned pipx version"):
        publication._smoke_installers("1.2.2", tmp_path, tmp_path / "temporary")


def test_smoke_installers_retries_package_index_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def fake_run(args: list[str], **_: object) -> str:
        nonlocal attempts
        if args[:4] == [sys.executable, "-m", "pipx", "install"]:
            attempts += 1
            if attempts == 1:
                raise RuntimeError("package index has not caught up")
            return ""
        if args[:3] == ["uv", "tool", "install"]:
            return ""
        if args[1:] == ["--version"]:
            return "1.2.2"
        if args[1:] == ["--root", str(tmp_path), "doctor"]:
            return ""
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(publication, "_run", fake_run)
    monkeypatch.setattr(publication.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(publication.shutil, "which", lambda name: "uv")
    monkeypatch.setattr(publication, "_installed_binary", lambda directory: Path("/bin/sourcebound"))
    sleeps: list[float] = []
    monkeypatch.setattr(publication.time, "sleep", sleeps.append)

    assert publication._smoke_installers(
        "1.2.2", tmp_path, tmp_path / "temporary", attempts=2, delay=0.25
    ) == {"pipx": "1.2.2", "uv": "1.2.2"}
    assert attempts == 2
    assert sleeps == [0.25]


def test_verify_published_release_matches_bytes_and_smokes_installers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "sourcebound-1.2.2-py3-none-any.whl"
    wheel.write_bytes(b"one canonical wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (dist / "SHA256SUMS").write_text(f"{digest}  {wheel.name}\n")

    def fake_run(args: list[str], **_: object) -> str:
        if args[:3] == ["gh", "release", "download"]:
            github = Path(args[args.index("--dir") + 1])
            (github / wheel.name).write_bytes(wheel.read_bytes())
            (github / "SHA256SUMS").write_text(f"{digest}  {wheel.name}\n")
        elif args[:3] != ["gh", "attestation", "verify"]:
            raise AssertionError(f"unexpected command: {args}")
        return ""

    monkeypatch.setattr(publication, "_run", fake_run)
    monkeypatch.setattr(
        publication,
        "_wait_for_pypi",
        lambda *args, **kwargs: _pypi_payload(wheel.name, digest),
    )
    monkeypatch.setattr(
        publication,
        "_download",
        lambda url, destination: destination.write_bytes(wheel.read_bytes()),
    )
    monkeypatch.setattr(
        publication,
        "_smoke_installers",
        lambda version, root, temporary, **_: {"pipx": version, "uv": version},
    )

    receipt = publication.verify_published_release(
        repo="owieschon/sourcebound",
        tag="v1.2.2",
        version="1.2.2",
        dist=dist,
        root=tmp_path,
    )

    assert receipt["schema"] == "sourcebound.publication-verification.v1"
    assert receipt["ok"] is True
    assert receipt["wheel"] == {"file": wheel.name, "sha256": digest}
    assert set(receipt["digests"].values()) == {digest}
    assert receipt["attestation"] == "verified"
    assert receipt["installers"] == {"pipx": "1.2.2", "uv": "1.2.2"}


def test_verify_published_release_rejects_a_pypi_digest_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "sourcebound-1.2.2-py3-none-any.whl"
    wheel.write_bytes(b"local wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (dist / "SHA256SUMS").write_text(f"{digest}  {wheel.name}\n")

    def fake_run(args: list[str], **_: object) -> str:
        if args[:3] == ["gh", "release", "download"]:
            github = Path(args[args.index("--dir") + 1])
            (github / wheel.name).write_bytes(wheel.read_bytes())
            (github / "SHA256SUMS").write_text(f"{digest}  {wheel.name}\n")
        return ""

    monkeypatch.setattr(publication, "_run", fake_run)
    monkeypatch.setattr(
        publication,
        "_wait_for_pypi",
        lambda *args, **kwargs: _pypi_payload(wheel.name, "0" * 64),
    )
    monkeypatch.setattr(
        publication,
        "_download",
        lambda url, destination: destination.write_bytes(b"different wheel"),
    )

    with pytest.raises(RuntimeError, match="published wheel digests differ"):
        publication.verify_published_release(
            repo="owieschon/sourcebound",
            tag="v1.2.2",
            version="1.2.2",
            dist=dist,
            root=tmp_path,
        )


def test_main_writes_a_failure_receipt_before_returning_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "receipts/publication.json"

    def fail_verification(**_: object) -> dict[str, Any]:
        raise RuntimeError("published bytes differ")

    monkeypatch.setattr(
        publication,
        "verify_published_release",
        fail_verification,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_published_release.py",
            "--repo",
            "owieschon/sourcebound",
            "--tag",
            "v1.2.2",
            "--version",
            "1.2.2",
            "--dist",
            str(tmp_path),
            "--out",
            str(output),
        ],
    )

    assert publication.main() == 1
    assert json.loads(output.read_text()) == {
        "schema": "sourcebound.publication-verification.v1",
        "ok": False,
        "repo": "owieschon/sourcebound",
        "tag": "v1.2.2",
        "version": "1.2.2",
        "error": {
            "type": "RuntimeError",
            "message": "published bytes differ",
        },
    }
