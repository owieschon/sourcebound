"""Compile bounded, source-addressed context without a model or retrieval index."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError


REQUEST_SCHEMA = "sourcebound.context-request.v1"
BUNDLE_SCHEMA = "sourcebound.context-bundle.v1"
KINDS = {
    "example",
    "fact",
    "history",
    "hypothesis",
    "instruction",
    "policy",
    "projection",
}
AUTHORITIES = {
    "accepted-policy": 50,
    "direct-evidence": 40,
    "generated": 30,
    "repository-doc": 20,
    "hypothesis": 10,
}
SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class ContextItem:
    id: str
    kind: str
    path: str
    locator: str
    source_commit: str
    source_sha256: str
    authority: str
    relationship: str
    inclusion_reason: str
    rank: int
    instruction_allowed: bool
    bytes: int
    content: str


@dataclass(frozen=True)
class ExcludedContext:
    id: str
    path: str
    reason: str
    required: bool
    source_sha256: str
    bytes: int


@dataclass(frozen=True)
class ContextBundle:
    repository_commit: str
    budget_bytes: int
    used_bytes: int
    rejected_bytes: int
    status: str
    items: tuple[ContextItem, ...]
    excluded: tuple[ExcludedContext, ...]
    digest: str

    @property
    def ok(self) -> bool:
        return self.status == "current"

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": BUNDLE_SCHEMA,
            "repository_commit": self.repository_commit,
            "budget": {
                "bytes": self.budget_bytes,
                "used": self.used_bytes,
                "rejected": self.rejected_bytes,
            },
            "status": self.status,
            "items": [asdict(item) for item in self.items],
            "excluded": [asdict(item) for item in self.excluded],
            "digest": self.digest,
        }


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    return value


def _git_commit(root: Path) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        raise ConfigurationError("context compilation requires a git commit")
    return process.stdout.strip()


def _source_text(
    root: Path,
    *,
    commit: str,
    path: str,
    start_line: int,
    end_line: int,
) -> str:
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ConfigurationError(f"context path must stay inside the repository: {path}")
    process = subprocess.run(
        ["git", "-C", str(root), "show", f"{commit}:{relative.as_posix()}"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        raise ConfigurationError(
            f"context path does not exist at {commit}: {path}"
        )
    try:
        lines = process.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ConfigurationError(f"context path is not UTF-8: {path}") from exc
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        raise ConfigurationError(
            f"context locator is outside {path}: L{start_line}-L{end_line}"
        )
    return "\n".join(lines[start_line - 1:end_line]) + "\n"


def _canonical_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def compile_context(root: Path, request_path: Path) -> ContextBundle:
    root = root.resolve()
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read context request {request_path}: {exc}") from exc
    request = _mapping(raw, "context request")
    if set(request) != {"schema", "repository_commit", "budget_bytes", "items"}:
        raise ConfigurationError("context request has unsupported fields")
    if request.get("schema") != REQUEST_SCHEMA:
        raise ConfigurationError("context request has an unsupported schema")
    commit = request.get("repository_commit")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ConfigurationError("context request repository_commit must be a full SHA")
    observed_commit = _git_commit(root)
    if commit != observed_commit:
        raise ConfigurationError(
            f"context request commit is {commit}, but repository is {observed_commit}"
        )
    budget = request.get("budget_bytes")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 1:
        raise ConfigurationError("context request budget_bytes must be positive")
    raw_items = request.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ConfigurationError("context request items must be non-empty")

    prepared: list[tuple[dict[str, Any], str, int]] = []
    seen: set[str] = set()
    for index, value in enumerate(raw_items):
        item = _mapping(value, f"context request item {index}")
        expected = {
            "id",
            "kind",
            "path",
            "start_line",
            "end_line",
            "authority",
            "relationship",
            "reason",
            "rank",
            "required",
            "instruction",
        }
        if set(item) != expected:
            raise ConfigurationError(f"context request item {index} has unsupported fields")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ConfigurationError(f"context request item {index} needs an id")
        if identifier in seen:
            raise ConfigurationError(f"duplicate context item id: {identifier}")
        seen.add(identifier)
        if item.get("kind") not in KINDS:
            raise ConfigurationError(f"context request item {identifier} has an invalid kind")
        authority = item.get("authority")
        if authority not in AUTHORITIES:
            raise ConfigurationError(
                f"context request item {identifier} has an invalid authority"
            )
        for field in ("path", "relationship", "reason"):
            if not isinstance(item.get(field), str) or not item[field]:
                raise ConfigurationError(
                    f"context request item {identifier}.{field} must be non-empty"
                )
        for field in ("start_line", "end_line", "rank"):
            if not isinstance(item.get(field), int) or isinstance(item[field], bool):
                raise ConfigurationError(
                    f"context request item {identifier}.{field} must be an integer"
                )
        for field in ("required", "instruction"):
            if not isinstance(item.get(field), bool):
                raise ConfigurationError(
                    f"context request item {identifier}.{field} must be boolean"
                )
        content = _source_text(
            root,
            commit=commit,
            path=item["path"],
            start_line=item["start_line"],
            end_line=item["end_line"],
        )
        prepared.append((item, content, len(content.encode())))

    prepared.sort(
        key=lambda row: (
            not row[0]["required"],
            -AUTHORITIES[row[0]["authority"]],
            -row[0]["rank"],
            row[0]["id"],
        )
    )
    included: list[ContextItem] = []
    excluded: list[ExcludedContext] = []
    used = 0
    unknown = False
    for item, content, byte_count in prepared:
        if used + byte_count > budget:
            reason = "required-over-budget" if item["required"] else "budget-exhausted"
            excluded.append(
                ExcludedContext(
                    item["id"],
                    item["path"],
                    reason,
                    item["required"],
                    hashlib.sha256(content.encode()).hexdigest(),
                    byte_count,
                )
            )
            unknown = unknown or item["required"]
            continue
        instruction_allowed = (
            item["instruction"]
            and item["kind"] in {"instruction", "policy"}
            and item["authority"] == "accepted-policy"
        )
        included.append(
            ContextItem(
                item["id"],
                item["kind"],
                item["path"],
                f"L{item['start_line']}-L{item['end_line']}",
                commit,
                hashlib.sha256(content.encode()).hexdigest(),
                item["authority"],
                item["relationship"],
                item["reason"],
                item["rank"],
                instruction_allowed,
                byte_count,
                content,
            )
        )
        used += byte_count
    status = "unknown" if unknown or not included else "current"
    unsigned: dict[str, object] = {
        "schema": BUNDLE_SCHEMA,
        "repository_commit": commit,
        "budget": {"bytes": budget, "used": used},
        "status": status,
        "items": [asdict(item) for item in included],
        "excluded": [asdict(item) for item in excluded],
    }
    return ContextBundle(
        commit,
        budget,
        used,
        sum(item.bytes for item in excluded),
        status,
        tuple(included),
        tuple(excluded),
        _canonical_digest(unsigned),
    )
