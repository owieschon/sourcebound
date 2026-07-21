from __future__ import annotations

import hashlib
import json
from typing import Any

from sourcebound.errors import ExtractionError
from sourcebound.execution import resolve_argv
from sourcebound.isolation import run_isolated_process
from sourcebound.models import CommandSpec, EvidenceValue, Provenance
from sourcebound.snapshot import RepositorySnapshot


def _select(value: Any, path: str) -> Any:
    current = value
    for token in path.removeprefix("$.").split("."):
        if not isinstance(current, dict) or token not in current:
            raise ExtractionError(f"command JSON path does not resolve: {path}")
        current = current[token]
    return current


def extract_command(
    snapshot: RepositorySnapshot, command: CommandSpec, json_path: str
) -> EvidenceValue:
    proc = run_isolated_process(
        snapshot,
        resolve_argv(command.argv),
        label=f"command {command.id}",
        timeout_seconds=command.timeout_seconds,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise ExtractionError(f"command {command.id} exited {proc.returncode}: {detail[:500]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"command {command.id} did not return JSON: {exc}") from exc
    value = _select(payload, json_path)
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return EvidenceValue(
        kind="scalar",
        value=value,
        provenance=Provenance(
            ref=snapshot.label,
            path="<command>",
            locator=command.id,
            extractor="command@1",
            digest=hashlib.sha256(normalized.encode()).hexdigest(),
        ),
    )
