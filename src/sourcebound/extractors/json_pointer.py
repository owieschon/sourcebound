from __future__ import annotations

import hashlib
import json
from typing import Any

from sourcebound.errors import ExtractionError
from sourcebound.models import EvidenceValue, Provenance, RegionBinding
from sourcebound.snapshot import RepositorySnapshot


def _decode(token: str) -> str:
    decoded = []
    index = 0
    while index < len(token):
        if token[index] != "~":
            decoded.append(token[index])
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
            raise ExtractionError(f"invalid JSON Pointer token: {token!r}")
        decoded.append("~" if token[index + 1] == "0" else "/")
        index += 2
    return "".join(decoded)


def _resolve(value: Any, pointer: str) -> Any:
    current = value
    for raw_token in pointer.removeprefix("/").split("/"):
        token = _decode(raw_token)
        if isinstance(current, dict):
            if token not in current:
                raise ExtractionError(f"JSON Pointer {pointer!r} does not resolve")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                raise ExtractionError(f"JSON Pointer {pointer!r} does not resolve")
            try:
                index = int(token)
                current = current[index]
            except (ValueError, IndexError) as exc:
                raise ExtractionError(f"JSON Pointer {pointer!r} does not resolve") from exc
        else:
            raise ExtractionError(f"JSON Pointer {pointer!r} traverses a scalar value")
    return current


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    if isinstance(value, dict) and all(isinstance(item, dict) for item in value.values()):
        rows = []
        for key, item in value.items():
            row = dict(item)
            row.setdefault("key", key)
            rows.append(row)
        return rows
    raise ExtractionError("markdown-table evidence must be a list or mapping of records")


def extract_json_pointer(
    snapshot: RepositorySnapshot, binding: RegionBinding
) -> EvidenceValue:
    if binding.source.pointer is None:
        raise ExtractionError("json source requires a pointer")
    text = snapshot.read_text(binding.source.path)
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"cannot parse {binding.source.path}: {exc}") from exc
    value = _rows(_resolve(document, binding.source.pointer))
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return EvidenceValue(
        kind="table",
        value=value,
        provenance=Provenance(
            ref=snapshot.label,
            path=binding.source.path.as_posix(),
            locator=binding.source.pointer,
            extractor="json@1",
            digest=digest,
        ),
    )
