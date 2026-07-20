from __future__ import annotations

import sys
from pathlib import Path

import pytest

from clean_docs.errors import ExtractionError
from clean_docs.isolation import (
    MAX_PROCESS_IO_BYTES,
    _sandbox_environment,
    run_isolated_process,
)
from clean_docs.snapshot import RepositorySnapshot


def _script(root: Path, body: str) -> Path:
    path = root / "fixture.py"
    path.write_text(body)
    return path


def test_declared_process_uses_literal_argv_in_disposable_copy(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _script(
        root,
        "import json, pathlib, sys\n"
        "pathlib.Path('../escaped.txt').write_text('discarded')\n"
        "print(json.dumps(sys.argv[1]))\n",
    )
    argument = "$(touch shell-expanded)"

    result = run_isolated_process(
        RepositorySnapshot(root),
        (sys.executable, "fixture.py", argument),
        label="fixture",
        timeout_seconds=5,
    )

    assert result.stdout.strip() == f'"{argument}"'
    assert not (tmp_path / "escaped.txt").exists()
    assert not (root / "shell-expanded").exists()


def test_declared_process_rejects_secret_output_without_echoing_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    secret = "ghp_" + "A" * 24
    _script(root, f"print({secret!r})\n")

    with pytest.raises(ExtractionError) as raised:
        run_isolated_process(
            RepositorySnapshot(root),
            (sys.executable, "fixture.py"),
            label="fixture",
            timeout_seconds=5,
        )

    assert "secret-like data" in str(raised.value)
    assert secret not in str(raised.value)


def test_declared_process_stops_at_combined_output_limit(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _script(
        root,
        f"import sys\nsys.stdout.write('x' * {MAX_PROCESS_IO_BYTES + 1})\n",
    )

    with pytest.raises(
        ExtractionError,
        match=rf"fixture output exceeds {MAX_PROCESS_IO_BYTES} bytes",
    ):
        run_isolated_process(
            RepositorySnapshot(root),
            (sys.executable, "fixture.py"),
            label="fixture",
            timeout_seconds=5,
        )


def test_declared_process_stops_at_timeout(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _script(root, "import time\ntime.sleep(10)\n")

    with pytest.raises(
        ExtractionError,
        match=r"fixture timed out after 1 seconds",
    ):
        run_isolated_process(
            RepositorySnapshot(root),
            (sys.executable, "fixture.py"),
            label="fixture",
            timeout_seconds=1,
        )


def test_declared_process_rejects_repository_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _script(root, "print('{}')\n")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    (root / "escape").symlink_to(outside)

    with pytest.raises(
        ExtractionError,
        match=r"process snapshot contains a symbolic link: escape",
    ):
        run_isolated_process(
            RepositorySnapshot(root),
            (sys.executable, "fixture.py"),
            label="fixture",
            timeout_seconds=5,
        )


def test_sandbox_environment_has_only_declared_keys(tmp_path: Path) -> None:
    environment = _sandbox_environment(tmp_path / "home", tmp_path / "tmp")

    assert set(environment) == {"HOME", "TMPDIR", "PATH", "NO_COLOR"}
