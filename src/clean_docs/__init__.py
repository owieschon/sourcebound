"""Bind repository documentation to deterministic sources."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


def _package_version() -> str:
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if project.is_file():
        try:
            return str(tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"])
        except (OSError, KeyError, tomllib.TOMLDecodeError):
            pass
    try:
        return version("clean-docs")
    except PackageNotFoundError:
        return "0+unknown"


__version__ = _package_version()
