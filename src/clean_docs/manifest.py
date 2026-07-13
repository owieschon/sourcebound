from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.models import (
    Assertion,
    Binding,
    ClaimBinding,
    CommandSpec,
    Manifest,
    RegionBinding,
    Source,
    SymbolBinding,
)

ROOT_KEYS = {"version", "bindings", "execution"}
BINDING_KEYS = {
    "id", "type", "doc", "region", "anchor", "extractor", "source", "renderer",
    "columns", "command", "assertion",
}
SOURCE_KEYS = {"path", "symbol", "pointer"}
EXTRACTORS = {"json", "python-literal"}
EXECUTION_KEYS = {"commands", "allowed_commands"}
COMMAND_KEYS = {"argv", "timeout_seconds", "network"}
ASSERTION_KEYS = {"json_path", "operator", "expected"}


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

    commands: list[CommandSpec] = []
    execution = root.get("execution")
    if execution is not None:
        execution_data = _mapping(execution, "execution")
        _reject_unknown(execution_data, EXECUTION_KEYS, "execution")
        if execution_data.get("commands", "deny") != "deny":
            raise ConfigurationError("execution.commands must be deny")
        allowed = _mapping(execution_data.get("allowed_commands", {}), "execution.allowed_commands")
        for command_id, raw_command in allowed.items():
            command = _mapping(raw_command, f"execution.allowed_commands.{command_id}")
            _reject_unknown(command, COMMAND_KEYS, f"execution.allowed_commands.{command_id}")
            argv = command.get("argv")
            timeout = command.get("timeout_seconds", 30)
            network = command.get("network", False)
            if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
                raise ConfigurationError(f"execution.allowed_commands.{command_id}.argv must be a non-empty string list")
            if not isinstance(timeout, int) or not 1 <= timeout <= 300:
                raise ConfigurationError(f"execution.allowed_commands.{command_id}.timeout_seconds must be 1..300")
            if network is not False:
                raise ConfigurationError(f"execution.allowed_commands.{command_id}.network must be false")
            commands.append(CommandSpec(command_id, tuple(argv), timeout, network))

    bindings: list[Binding] = []
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
        binding_type = data.get("type")
        if binding_type not in {"region", "claim", "symbol"}:
            raise ConfigurationError(f"{where}.type must be region, claim, or symbol")
        if binding_type == "claim":
            if data.get("extractor") != "command":
                raise ConfigurationError(f"{where}.extractor must be command for a claim")
            command_ref = data.get("command")
            if not isinstance(command_ref, str) or command_ref not in {item.id for item in commands}:
                raise ConfigurationError(f"{where}.command must name an allowed command")
            assertion_data = _mapping(data.get("assertion"), f"{where}.assertion")
            _reject_unknown(assertion_data, ASSERTION_KEYS, f"{where}.assertion")
            json_path = assertion_data.get("json_path")
            if not isinstance(json_path, str) or not json_path.startswith("$."):
                raise ConfigurationError(f"{where}.assertion.json_path must start with $.")
            if assertion_data.get("operator") != "equals":
                raise ConfigurationError(f"{where}.assertion.operator must be equals")
            anchor = data.get("anchor")
            if not isinstance(anchor, str) or not anchor:
                raise ConfigurationError(f"{where}.anchor must be non-empty")
            bindings.append(ClaimBinding(
                id=binding_id,
                doc=_relative_path(data.get("doc"), f"{where}.doc"),
                anchor=anchor,
                extractor="command",
                command=command_ref,
                assertion=Assertion(json_path, "equals", assertion_data.get("expected")),
            ))
            continue

        source_data = _mapping(data.get("source"), f"{where}.source")
        _reject_unknown(source_data, SOURCE_KEYS, f"{where}.source")
        if binding_type == "symbol":
            symbol = source_data.get("symbol")
            if symbol is not None and (not isinstance(symbol, str) or not symbol.isidentifier()):
                raise ConfigurationError(f"{where}.source.symbol must be a Python identifier")
            anchor = data.get("anchor")
            if not isinstance(anchor, str) or not anchor:
                raise ConfigurationError(f"{where}.anchor must be non-empty")
            bindings.append(SymbolBinding(
                id=binding_id,
                doc=_relative_path(data.get("doc"), f"{where}.doc"),
                anchor=anchor,
                source=Source(
                    path=_relative_path(source_data.get("path"), f"{where}.source.path"),
                    symbol=symbol,
                ),
            ))
            continue

        extractor = data.get("extractor")
        if extractor not in EXTRACTORS:
            raise ConfigurationError(
                f"{where}.extractor must be one of: {', '.join(sorted(EXTRACTORS))}"
            )
        if data.get("renderer") != "markdown-table":
            raise ConfigurationError(f"{where}.renderer must be markdown-table in this release")

        symbol = source_data.get("symbol")
        pointer = source_data.get("pointer")
        if extractor == "python-literal":
            if not isinstance(symbol, str) or not symbol.isidentifier():
                raise ConfigurationError(f"{where}.source.symbol must be a Python identifier")
            if pointer is not None:
                raise ConfigurationError(f"{where}.source.pointer is only valid for json")
        else:
            if symbol is not None:
                raise ConfigurationError(f"{where}.source.symbol is only valid for python-literal")
            if not isinstance(pointer, str) or not pointer.startswith("/"):
                raise ConfigurationError(
                    f"{where}.source.pointer must be a JSON Pointer starting with /"
                )
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
            extractor=extractor,
            source=Source(
                path=_relative_path(source_data.get("path"), f"{where}.source.path"),
                symbol=symbol,
                pointer=pointer,
            ),
            renderer=data["renderer"],
            columns=tuple(columns),
        ))
    return Manifest(path=path, version=1, bindings=tuple(bindings), commands=tuple(commands))
