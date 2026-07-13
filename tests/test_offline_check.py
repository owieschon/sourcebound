from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from clean_docs.cli import main


def _block_network(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError(f"network access attempted with {args!r} {kwargs!r}")


def test_static_check_makes_no_network_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "facts.txt").write_text("current\n")
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- clean-docs:begin fact -->\ncurrent\n<!-- clean-docs:end fact -->\n"
    )
    (root / ".clean-docs.yml").write_text("""\
version: 1
bindings:
  - id: fact
    type: region
    doc: README.md
    region: fact
    extractor: file
    source: {path: facts.txt}
    renderer: scalar
""")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    monkeypatch.setattr(socket, "create_connection", _block_network)
    monkeypatch.setattr(socket.socket, "connect", _block_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _block_network)

    assert main(["--root", str(root), "check"]) == 0
