"""Evaluate review-only source-to-document contracts at immutable Git refs."""

from __future__ import annotations

import ast
import copy
import hashlib
import html
import json
import math
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from pathlib import Path

import yaml

from clean_docs.errors import ExtractionError
from clean_docs.models import ReviewContract, ReviewLocator
from clean_docs.snapshot import RepositorySnapshot


_ATX_HEADING = re.compile(
    r"^ {0,3}(?P<marks>#{1,6})[ \t]+(?P<title>.*?)[ \t]*#*[ \t]*$"
)
_SETEXT_HEADING = re.compile(r"^ {0,3}(?P<marks>=+|-+)[ \t]*$")
_MARKDOWN_MARKUP = re.compile(r"[`*_~]")
_HTML_TAG = re.compile(r"<[^>]*>")
_POINTER_ESCAPE = re.compile(r"~(?:0|1)")
_CHANGED_STATES = frozenset({"added", "changed", "removed"})
_SUBSTANTIVE_TARGET_STATES = frozenset({"added", "changed"})


class _LocatorMissing(Exception):
    pass


class _LocatorUnresolved(Exception):
    pass


@dataclass(frozen=True)
class ReviewLocatorEvidence:
    id: str
    path: str
    extractor: str
    locator: str
    base_digest: str | None
    head_digest: str | None
    state: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewContractResult:
    contract_id: str
    mode: str
    state: str
    sources: tuple[ReviewLocatorEvidence, ...]
    targets: tuple[ReviewLocatorEvidence, ...]
    semantic_correctness_checked: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.contract_id,
            "mode": self.mode,
            "state": self.state,
            "sources": [item.as_dict() for item in self.sources],
            "targets": [item.as_dict() for item in self.targets],
            "semantic_correctness_checked": self.semantic_correctness_checked,
        }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_path(path: Path) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise _LocatorUnresolved


def _path_exists(root: Path, ref: str, path: Path) -> bool:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{ref}:{path.as_posix()}"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _LocatorUnresolved from exc
    return process.returncode == 0


def _snapshot_text(snapshot: RepositorySnapshot, path: Path) -> str:
    _validate_path(path)
    ref = snapshot.label
    if not _path_exists(snapshot.root, ref, path):
        raise _LocatorMissing
    try:
        return snapshot.read_text(path)
    except (ExtractionError, UnicodeDecodeError) as exc:
        raise _LocatorUnresolved from exc


def _assignment_names(node: ast.AST) -> set[str]:
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)

    names: set[str] = set()

    def collect(target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                collect(item)

    for target in targets:
        collect(target)
    return names


def _scope_body(node: ast.AST) -> list[ast.stmt] | None:
    if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.body
    return None


def _find_python_symbol(tree: ast.Module, locator: str) -> ast.AST:
    current: ast.AST = tree
    for part in locator.split("."):
        body = _scope_body(current)
        if body is None:
            raise _LocatorMissing
        matches = [
            node
            for node in body
            if (
                isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == part
            )
            or part in _assignment_names(node)
        ]
        if not matches:
            raise _LocatorMissing
        if len(matches) != 1:
            raise _LocatorUnresolved
        current = matches[0]
    return current


def _is_docstring_statement(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


class _DocstringStripper(ast.NodeTransformer):
    @staticmethod
    def _strip(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
        if node.body and _is_docstring_statement(node.body[0]):
            node.body = node.body[1:]
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        return self._strip(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        return self._strip(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        return self._strip(node)


def _normalized_ast(node: ast.AST) -> str:
    normalized = _DocstringStripper().visit(copy.deepcopy(node))
    assert normalized is not None
    return ast.dump(normalized, annotate_fields=True, include_attributes=False)


def _python_symbol_digest(text: str, locator: str) -> str:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise _LocatorUnresolved from exc
    node = _find_python_symbol(tree, locator)
    return _sha256(_normalized_ast(node))


def _markdown_slug(title: str) -> str:
    plain = html.unescape(_HTML_TAG.sub("", title))
    plain = _MARKDOWN_MARKUP.sub("", plain).casefold()
    plain = re.sub(r"[^\w\s-]", "", plain)
    return re.sub(r"[\s-]+", "-", plain).strip("-")


@dataclass(frozen=True)
class _Heading:
    start: int
    content_start: int
    level: int
    slug: str


def _markdown_headings(lines: list[str]) -> list[_Heading]:
    raw: list[tuple[int, int, int, str]] = []
    for index, line in enumerate(lines):
        match = _ATX_HEADING.match(line)
        if match:
            raw.append(
                (
                    index,
                    index + 1,
                    len(match.group("marks")),
                    _markdown_slug(match.group("title")),
                )
            )
            continue
        setext = _SETEXT_HEADING.match(line)
        if (
            setext
            and index > 0
            and lines[index - 1].strip()
            and not _ATX_HEADING.match(lines[index - 1])
        ):
            raw.append(
                (
                    index - 1,
                    index + 1,
                    1 if setext.group("marks").startswith("=") else 2,
                    _markdown_slug(lines[index - 1].strip()),
                )
            )

    occurrences: dict[str, int] = {}
    headings = []
    for start, content_start, level, base_slug in sorted(raw):
        occurrence = occurrences.get(base_slug, 0)
        occurrences[base_slug] = occurrence + 1
        slug = base_slug if occurrence == 0 else f"{base_slug}-{occurrence}"
        headings.append(_Heading(start, content_start, level, slug))
    return headings


def _markdown_section_digest(text: str, locator: str) -> str:
    requested = locator.removeprefix("#")
    lines = text.splitlines()
    headings = _markdown_headings(lines)
    matches = [heading for heading in headings if heading.slug == requested]
    if not matches:
        raise _LocatorMissing
    if len(matches) != 1:
        raise _LocatorUnresolved
    selected = matches[0]
    end = len(lines)
    for heading in headings:
        if heading.start > selected.start and heading.level <= selected.level:
            end = heading.start
            break
    tokens = re.findall(r"\S+", "\n".join(lines[selected.content_start:end]))
    return _sha256(" ".join(tokens))


def _load_structured(path: Path, text: str) -> object:
    try:
        if path.suffix.lower() == ".json":
            return json.loads(text)
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(text)
        if path.suffix.lower() == ".toml":
            return tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError) as exc:
        raise _LocatorUnresolved from exc
    raise _LocatorUnresolved


def _decode_pointer(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise _LocatorUnresolved
    tokens = pointer[1:].split("/")
    decoded = []
    for token in tokens:
        if "~" in _POINTER_ESCAPE.sub("", token):
            raise _LocatorUnresolved
        decoded.append(token.replace("~1", "/").replace("~0", "~"))
    return decoded


def _resolve_pointer(value: object, pointer: str) -> object:
    current = value
    for token in _decode_pointer(pointer):
        if isinstance(current, dict):
            if token not in current:
                raise _LocatorMissing
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                raise _LocatorMissing
            index = int(token)
            if index >= len(current):
                raise _LocatorMissing
            current = current[index]
            continue
        raise _LocatorMissing
    return current


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _LocatorUnresolved
        return value
    if isinstance(value, (date, datetime, time)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise _LocatorUnresolved
        return {
            key: _canonical_value(value[key])
            for key in sorted(value)
        }
    raise _LocatorUnresolved


def _structured_data_digest(path: Path, text: str, locator: str) -> str:
    value = _resolve_pointer(_load_structured(path, text), locator)
    encoded = json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return _sha256(encoded)


def _digest_at(snapshot: RepositorySnapshot, locator: ReviewLocator) -> tuple[str, str | None]:
    try:
        text = _snapshot_text(snapshot, locator.path)
        if locator.extractor == "python-symbol":
            digest = _python_symbol_digest(text, locator.locator)
        elif locator.extractor == "markdown-section":
            digest = _markdown_section_digest(text, locator.locator)
        elif locator.extractor == "structured-data":
            digest = _structured_data_digest(locator.path, text, locator.locator)
        else:
            raise _LocatorUnresolved
    except _LocatorMissing:
        return "missing", None
    except _LocatorUnresolved:
        return "unresolved", None
    return "resolved", digest


def _locator_state(
    base_resolution: str,
    base_digest: str | None,
    head_resolution: str,
    head_digest: str | None,
) -> str:
    if "unresolved" in {base_resolution, head_resolution}:
        return "unknown"
    if base_resolution == "missing" and head_resolution == "missing":
        return "unknown"
    if base_resolution == "missing":
        return "added"
    if head_resolution == "missing":
        return "removed"
    return "unchanged" if base_digest == head_digest else "changed"


def _evaluate_locator(
    locator: ReviewLocator,
    base_snapshot: RepositorySnapshot,
    head_snapshot: RepositorySnapshot,
) -> ReviewLocatorEvidence:
    base_resolution, base_digest = _digest_at(base_snapshot, locator)
    head_resolution, head_digest = _digest_at(head_snapshot, locator)
    return ReviewLocatorEvidence(
        id=locator.id,
        path=locator.path.as_posix(),
        extractor=locator.extractor,
        locator=locator.locator,
        base_digest=base_digest,
        head_digest=head_digest,
        state=_locator_state(
            base_resolution,
            base_digest,
            head_resolution,
            head_digest,
        ),
    )


def _evaluate_review_contract_snapshots(
    contract: ReviewContract,
    base_snapshot: RepositorySnapshot,
    head_snapshot: RepositorySnapshot,
) -> ReviewContractResult:
    sources = tuple(
        _evaluate_locator(locator, base_snapshot, head_snapshot)
        for locator in contract.sources
    )
    targets = tuple(
        _evaluate_locator(locator, base_snapshot, head_snapshot)
        for locator in contract.targets
    )

    if (
        not sources
        or not targets
        or any(item.state == "unknown" for item in sources + targets)
        or any(item.head_digest is None for item in targets)
    ):
        state = "unknown"
    elif not any(item.state in _CHANGED_STATES for item in sources):
        state = "unaffected"
    elif all(item.state in _SUBSTANTIVE_TARGET_STATES for item in targets):
        state = "cochanged"
    else:
        state = "review-recommended"

    return ReviewContractResult(
        contract_id=contract.id,
        mode=contract.mode,
        state=state,
        sources=sources,
        targets=targets,
    )


def _snapshots(
    root: Path,
    base: str,
    head: str,
) -> tuple[RepositorySnapshot, RepositorySnapshot]:
    resolved_root = root.resolve()
    base_ref = RepositorySnapshot(resolved_root, base).label
    head_ref = RepositorySnapshot(resolved_root, head).label
    return (
        RepositorySnapshot(resolved_root, base_ref),
        RepositorySnapshot(resolved_root, head_ref),
    )


def evaluate_review_contract(
    root: Path,
    contract: ReviewContract,
    *,
    base: str,
    head: str,
) -> ReviewContractResult:
    base_snapshot, head_snapshot = _snapshots(root, base, head)
    return _evaluate_review_contract_snapshots(
        contract,
        base_snapshot,
        head_snapshot,
    )


def evaluate_review_contracts(
    root: Path,
    contracts: tuple[ReviewContract, ...],
    *,
    base: str,
    head: str,
) -> tuple[ReviewContractResult, ...]:
    base_snapshot, head_snapshot = _snapshots(root, base, head)
    return tuple(
        _evaluate_review_contract_snapshots(
            contract,
            base_snapshot,
            head_snapshot,
        )
        for contract in contracts
    )
