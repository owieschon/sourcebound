from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.models import Manifest, RegionBinding, Source

ROOT_KEYS = {"version", "bindings"}
BINDING_KEYS = {
    "id", "type", "doc", "region", "extractor", "source", "renderer", "columns"
}
SOURCE_KEYS = {"path", "symbol"}


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be a mapping")
    return value


def _reject_unknown(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")


def _relative_path(raw: Any, where: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigurationError(f"{where} must be a non-empty path")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{where} must stay inside the repository: {raw}")
    return path


def load_manifest(path: Path) -> Manifest:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read manifest {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc

    root = _mapping(raw, "manifest")
    _reject_unknown(root, ROOT_KEYS, "manifest")
    if root.get("version") != 1:
        raise ConfigurationError("manifest version must be 1")
    raw_bindings = root.get("bindings")
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise ConfigurationError("manifest bindings must be a non-empty list")

    bindings: list[RegionBinding] = []
    ids: set[str] = set()
    for index, item in enumerate(raw_bindings):
        where = f"bindings[{index}]"
        data = _mapping(item, where)
        _reject_unknown(data, BINDING_KEYS, where)
        binding_id = data.get("id")
        if not isinstance(binding_id, str) or not binding_id.strip():
            raise ConfigurationError(f"{where}.id must be a non-empty string")
        if binding_id in ids:
            raise ConfigurationError(f"duplicate binding id: {binding_id}")
        ids.add(binding_id)
        if data.get("type") != "region":
            raise ConfigurationError(f"{where}.type must be region in manifest version 1")
        if data.get("extractor") != "python-literal":
            raise ConfigurationError(f"{where}.extractor must be python-literal in this release")
        if data.get("renderer") != "markdown-table":
            raise ConfigurationError(f"{where}.renderer must be markdown-table in this release")

        source_data = _mapping(data.get("source"), f"{where}.source")
        _reject_unknown(source_data, SOURCE_KEYS, f"{where}.source")
        symbol = source_data.get("symbol")
        if not isinstance(symbol, str) or not symbol.isidentifier():
            raise ConfigurationError(f"{where}.source.symbol must be a Python identifier")
        region = data.get("region")
        if not isinstance(region, str) or not region.strip():
            raise ConfigurationError(f"{where}.region must be a non-empty string")
        columns = data.get("columns")
        if (
            not isinstance(columns, list)
            or not columns
            or not all(isinstance(column, str) and column for column in columns)
            or len(set(columns)) != len(columns)
        ):
            raise ConfigurationError(f"{where}.columns must be unique non-empty strings")
        bindings.append(RegionBinding(
            id=binding_id,
            doc=_relative_path(data.get("doc"), f"{where}.doc"),
            region=region,
            extractor=data["extractor"],
            source=Source(
                path=_relative_path(source_data.get("path"), f"{where}.source.path"),
                symbol=symbol,
            ),
            renderer=data["renderer"],
            columns=tuple(columns),
        ))
    return Manifest(path=path, version=1, bindings=tuple(bindings))
