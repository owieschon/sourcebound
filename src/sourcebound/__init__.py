"""Bind repository documentation to deterministic sources."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10
    import tomli as tomllib


def _package_version() -> str:
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if project.is_file():
        try:
            return str(tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"])
        except (OSError, KeyError, tomllib.TOMLDecodeError):
            pass
    try:
        return version("sourcebound")
    except PackageNotFoundError:
        return "0+unknown"


__version__ = _package_version()
