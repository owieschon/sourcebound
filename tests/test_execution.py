from __future__ import annotations

import sys

from clean_docs.execution import resolve_argv


def test_python_token_resolves_to_running_interpreter() -> None:
    assert resolve_argv(("{python}", "-m", "clean_docs")) == (
        sys.executable,
        "-m",
        "clean_docs",
    )


def test_literal_executable_is_unchanged() -> None:
    assert resolve_argv(("git", "status")) == ("git", "status")
