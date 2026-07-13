"""Resolve explicit runtime tokens in allowlisted command arrays."""

from __future__ import annotations

import sys


PYTHON_EXECUTABLE_TOKEN = "{python}"


def resolve_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    if argv and argv[0] == PYTHON_EXECUTABLE_TOKEN:
        return (sys.executable, *argv[1:])
    return argv
