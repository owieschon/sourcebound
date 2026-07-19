from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from clean_docs.errors import ExtractionError
from clean_docs.models import EvidenceValue, Provenance, RegionBinding
from clean_docs.snapshot import RepositorySnapshot


def _digest(value: Any) -> str:
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode()).hexdigest()


def _decode(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _resolve(value: Any, pointer: str | None) -> Any:
    if pointer is None:
        return value
    current = value
    for raw_token in pointer.removeprefix("/").split("/"):
        token = _decode(raw_token)
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ExtractionError(f"structured-data pointer does not resolve: {pointer}")
    return current


def extract_file(snapshot: RepositorySnapshot, binding: RegionBinding) -> EvidenceValue:
    text = snapshot.read_text(binding.source.path)
    return EvidenceValue(
        kind="text",
        value=text,
        provenance=Provenance(
            snapshot.label,
            binding.source.path.as_posix(),
            binding.source.path.as_posix(),
            "file@1",
            hashlib.sha256(text.encode()).hexdigest(),
        ),
    )


def extract_paths(snapshot: RepositorySnapshot, binding: RegionBinding) -> EvidenceValue:
    if binding.source.glob is None:
        raise ExtractionError("path extractor requires a glob")
    paths = [path.as_posix() for path in snapshot.matching_files(binding.source.glob)]
    if not paths:
        raise ExtractionError(
            f"binding {binding.id} path glob matched zero files: "
            f"{binding.source.glob}"
        )
    return EvidenceValue(
        kind="list",
        value=paths,
        provenance=Provenance(
            snapshot.label,
            "<paths>",
            binding.source.glob,
            "path@1",
            _digest(paths),
        ),
    )


def extract_structured(snapshot: RepositorySnapshot, binding: RegionBinding) -> EvidenceValue:
    text = snapshot.read_text(binding.source.path)
    suffix = binding.source.path.suffix.lower()
    try:
        if suffix == ".json":
            value = json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            value = yaml.safe_load(text)
        elif suffix == ".toml":
            value = tomllib.loads(text)
        else:
            raise ExtractionError(f"unsupported structured-data format: {suffix or '<none>'}")
    except (json.JSONDecodeError, yaml.YAMLError, tomllib.TOMLDecodeError) as exc:
        raise ExtractionError(f"cannot parse {binding.source.path}: {exc}") from exc
    selected = _resolve(value, binding.source.pointer)
    kind = "table" if isinstance(selected, list) and all(
        isinstance(item, dict) for item in selected
    ) else "list" if isinstance(selected, list) else "scalar" if not isinstance(
        selected, dict
    ) else "mapping"
    return EvidenceValue(
        kind=kind,
        value=selected,
        provenance=Provenance(
            snapshot.label,
            binding.source.path.as_posix(),
            binding.source.pointer or "/",
            "structured-data@1",
            _digest(selected),
        ),
    )
