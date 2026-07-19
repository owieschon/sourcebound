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
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from pathlib import Path

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]

import yaml

from clean_docs.errors import ExtractionError
from clean_docs.mdx import MdxDocument, MdxParserError, parse_mdx_documents
from clean_docs.models import ReviewContract, ReviewLocator
from clean_docs.review_limits import (
    MAX_REVIEW_FILE_BYTES,
    MAX_REVIEW_STRUCTURED_NODES,
    MAX_REVIEW_TOTAL_BYTES,
)
from clean_docs.snapshot import RepositorySnapshot


_MARKDOWN_MARKUP = re.compile(r"[`*_~]")
_HTML_TAG = re.compile(r"<[^>]*>")
_HTML_COMMENT = re.compile(br"<!--.*?-->", re.DOTALL)
_POINTER_ESCAPE = re.compile(r"~(?:0|1)")
_CHANGED_STATES = frozenset({"added", "changed", "removed"})
_SUBSTANTIVE_TARGET_STATES = frozenset({"added", "changed"})
_MASKED_MARKDOWN_NODE_TYPES = frozenset(
    {
        "code",
        "yaml",
        "mdxjsEsm",
        "mdxFlowExpression",
        "mdxTextExpression",
    }
)


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


def _path_size(root: Path, ref: str, path: Path) -> int | None:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-s", f"{ref}:{path.as_posix()}"],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _LocatorUnresolved from exc
    if process.returncode != 0:
        return None
    try:
        size = int(process.stdout.strip())
    except ValueError as exc:
        raise _LocatorUnresolved from exc
    if size < 0:
        raise _LocatorUnresolved
    return size


@dataclass(frozen=True)
class _TextSnapshot:
    resolution: str
    text: str | None = None


_ContentKey = tuple[str, str]
_DigestKey = tuple[str, str, str, str]


@dataclass
class _ReviewCache:
    total_bytes: int = 0
    texts: dict[_ContentKey, _TextSnapshot] = field(default_factory=dict)
    python_trees: dict[_ContentKey, ast.Module | None] = field(default_factory=dict)
    structured_values: dict[_ContentKey, object] = field(default_factory=dict)
    structured_failures: set[_ContentKey] = field(default_factory=set)
    digests: dict[_DigestKey, tuple[str, str | None]] = field(
        default_factory=dict
    )

    @staticmethod
    def key(snapshot: RepositorySnapshot, path: Path) -> _ContentKey:
        return (snapshot.label, path.as_posix())

    def text(self, snapshot: RepositorySnapshot, path: Path) -> str:
        _validate_path(path)
        key = self.key(snapshot, path)
        cached = self.texts.get(key)
        if cached is None:
            size = _path_size(snapshot.root, snapshot.label, path)
            if size is None:
                cached = _TextSnapshot("missing")
            elif (
                size > MAX_REVIEW_FILE_BYTES
                or self.total_bytes + size > MAX_REVIEW_TOTAL_BYTES
            ):
                cached = _TextSnapshot("unresolved")
            else:
                try:
                    text = snapshot.read_text(path)
                except (ExtractionError, UnicodeDecodeError):
                    cached = _TextSnapshot("unresolved")
                else:
                    if len(text.encode("utf-8")) != size:
                        cached = _TextSnapshot("unresolved")
                    else:
                        self.total_bytes += size
                        cached = _TextSnapshot("resolved", text)
            self.texts[key] = cached
        if cached.resolution == "missing":
            raise _LocatorMissing
        if cached.resolution != "resolved" or cached.text is None:
            raise _LocatorUnresolved
        return cached.text

    def python_tree(
        self,
        snapshot: RepositorySnapshot,
        path: Path,
        text: str,
    ) -> ast.Module:
        key = self.key(snapshot, path)
        if key not in self.python_trees:
            try:
                self.python_trees[key] = ast.parse(text)
            except SyntaxError:
                self.python_trees[key] = None
        tree = self.python_trees[key]
        if tree is None:
            raise _LocatorUnresolved
        return tree

    def structured_value(
        self,
        snapshot: RepositorySnapshot,
        path: Path,
        text: str,
    ) -> object:
        key = self.key(snapshot, path)
        if key not in self.structured_values and key not in self.structured_failures:
            try:
                self.structured_values[key] = _load_structured(path, text)
            except _LocatorUnresolved:
                self.structured_failures.add(key)
        if key in self.structured_failures:
            raise _LocatorUnresolved
        return self.structured_values[key]


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


def _python_symbol_digest(tree: ast.Module, locator: str) -> str:
    node = _find_python_symbol(tree, locator)
    return _sha256(_normalized_ast(node))


def _markdown_slug(title: str) -> str:
    plain = html.unescape(_HTML_TAG.sub("", title))
    plain = _MARKDOWN_MARKUP.sub("", plain).casefold()
    plain = re.sub(r"[^\w\s-]", "", plain)
    return re.sub(r"[\s-]+", "-", plain).strip("-")


@dataclass(frozen=True)
class _Heading:
    start_byte: int
    end_byte: int
    level: int
    slug: str


@dataclass(frozen=True)
class _MarkdownSnapshot:
    resolution: str
    text: str | None = None
    document: MdxDocument | None = None
    pre_masked_ranges: tuple[tuple[int, int], ...] = ()


_MarkdownKey = tuple[str, str]
_MarkdownSnapshots = dict[_MarkdownKey, _MarkdownSnapshot]


def _html_block(node_type: str, name: str | None) -> bool:
    return (
        node_type == "mdxJsxFlowElement"
        and name is not None
        and name[:1].islower()
    )


def _masked_ranges(
    document: MdxDocument,
    pre_masked_ranges: tuple[tuple[int, int], ...] = (),
) -> tuple[tuple[int, int], ...]:
    return pre_masked_ranges + tuple(
        (node.start_byte, node.end_byte)
        for node in document.nodes
        if (
            node.type in _MASKED_MARKDOWN_NODE_TYPES
            or _html_block(node.type, node.name)
        )
    )


def _inside_range(
    start: int,
    end: int,
    ranges: tuple[tuple[int, int], ...],
) -> bool:
    return any(
        range_start <= start and end <= range_end
        for range_start, range_end in ranges
    )


def _markdown_headings(
    document: MdxDocument,
    pre_masked_ranges: tuple[tuple[int, int], ...],
) -> tuple[_Heading, ...]:
    masked_ranges = _masked_ranges(document, pre_masked_ranges)
    headings: list[_Heading] = []
    for node in document.nodes:
        if node.type != "heading" or _inside_range(
            node.start_byte,
            node.end_byte,
            masked_ranges,
        ):
            continue
        if node.depth is None or node.text is None:
            raise _LocatorUnresolved
        headings.append(
            _Heading(
                node.start_byte,
                node.end_byte,
                node.depth,
                _markdown_slug(node.text),
            )
        )
    return tuple(sorted(headings, key=lambda item: item.start_byte))


def _visible_markdown(
    text: str,
    document: MdxDocument,
    pre_masked_ranges: tuple[tuple[int, int], ...],
) -> bytes:
    encoded = bytearray(text.encode("utf-8"))
    for start, end in _masked_ranges(document, pre_masked_ranges):
        if start < 0 or end < start or end > len(encoded):
            raise _LocatorUnresolved
        for index in range(start, end):
            if encoded[index] not in {10, 13}:
                encoded[index] = 32
    return bytes(encoded)


def _markdown_section_digest(
    text: str,
    document: MdxDocument,
    pre_masked_ranges: tuple[tuple[int, int], ...],
    locator: str,
) -> str:
    requested = locator.removeprefix("#")
    headings = _markdown_headings(document, pre_masked_ranges)
    matches = [heading for heading in headings if heading.slug == requested]
    if not matches:
        raise _LocatorMissing
    if len(matches) != 1:
        raise _LocatorUnresolved
    selected = matches[0]
    end = len(text.encode("utf-8"))
    for heading in headings:
        if (
            heading.start_byte > selected.start_byte
            and heading.level <= selected.level
        ):
            end = heading.start_byte
            break
    visible = _visible_markdown(text, document, pre_masked_ranges)
    try:
        section = visible[selected.end_byte:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _LocatorUnresolved from exc
    tokens = re.findall(r"\S+", section)
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


@dataclass
class _StructuredNodeBudget:
    remaining: int = MAX_REVIEW_STRUCTURED_NODES

    def consume(self) -> None:
        self.remaining -= 1
        if self.remaining < 0:
            raise _LocatorUnresolved


def _canonical_value(
    value: object,
    *,
    budget: _StructuredNodeBudget,
    ancestors: frozenset[int] = frozenset(),
) -> object:
    budget.consume()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _LocatorUnresolved
        return value
    if isinstance(value, (date, datetime, time)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, list):
        identity = id(value)
        if identity in ancestors:
            raise _LocatorUnresolved
        nested = ancestors | {identity}
        return [
            _canonical_value(item, budget=budget, ancestors=nested)
            for item in value
        ]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise _LocatorUnresolved
        identity = id(value)
        if identity in ancestors:
            raise _LocatorUnresolved
        nested = ancestors | {identity}
        return {
            key: _canonical_value(
                value[key],
                budget=budget,
                ancestors=nested,
            )
            for key in sorted(value)
        }
    raise _LocatorUnresolved


def _structured_data_digest(value: object, locator: str) -> str:
    selected = _resolve_pointer(value, locator)
    encoded = json.dumps(
        _canonical_value(
            selected,
            budget=_StructuredNodeBudget(),
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return _sha256(encoded)


def _markdown_key(
    snapshot: RepositorySnapshot,
    path: Path,
) -> _MarkdownKey:
    return (snapshot.label, path.as_posix())


def _mask_html_comments(
    text: str,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    encoded = bytearray(text.encode("utf-8"))
    ranges = tuple(
        (match.start(), match.end())
        for match in _HTML_COMMENT.finditer(encoded)
    )
    for start, end in ranges:
        for index in range(start, end):
            if encoded[index] not in {10, 13}:
                encoded[index] = 32
    return encoded.decode("utf-8"), ranges


def _prepare_markdown_snapshots(
    contracts: tuple[ReviewContract, ...],
    base_snapshot: RepositorySnapshot,
    head_snapshot: RepositorySnapshot,
    cache: _ReviewCache,
) -> _MarkdownSnapshots:
    paths = {
        locator.path
        for contract in contracts
        for locator in contract.sources + contract.targets
        if locator.extractor == "markdown-section"
    }
    snapshots = (base_snapshot, head_snapshot)
    prepared: _MarkdownSnapshots = {}
    documents: dict[str, str] = {}
    identifiers: dict[str, _MarkdownKey] = {}
    source_texts: dict[str, str] = {}
    pre_masked_ranges: dict[str, tuple[tuple[int, int], ...]] = {}

    for snapshot in snapshots:
        for path in sorted(paths):
            key = _markdown_key(snapshot, path)
            if key in prepared or key in identifiers.values():
                continue
            try:
                text = cache.text(snapshot, path)
            except _LocatorMissing:
                prepared[key] = _MarkdownSnapshot("missing")
                continue
            except _LocatorUnresolved:
                prepared[key] = _MarkdownSnapshot("unresolved")
                continue
            identifier = f"review-document-{len(documents)}"
            parse_text, ranges = _mask_html_comments(text)
            documents[identifier] = parse_text
            source_texts[identifier] = text
            pre_masked_ranges[identifier] = ranges
            identifiers[identifier] = key

    if not documents:
        return prepared
    try:
        parsed, errors = parse_mdx_documents(documents)
    except MdxParserError:
        for identifier, key in identifiers.items():
            prepared[key] = _MarkdownSnapshot(
                "unresolved",
                text=source_texts[identifier],
                pre_masked_ranges=pre_masked_ranges[identifier],
            )
        return prepared

    for identifier, key in identifiers.items():
        text = source_texts[identifier]
        if identifier in errors:
            prepared[key] = _MarkdownSnapshot(
                "unresolved",
                text=text,
                pre_masked_ranges=pre_masked_ranges[identifier],
            )
        else:
            prepared[key] = _MarkdownSnapshot(
                "resolved",
                text=text,
                document=parsed[identifier],
                pre_masked_ranges=pre_masked_ranges[identifier],
            )
    return prepared


def _digest_at(
    snapshot: RepositorySnapshot,
    locator: ReviewLocator,
    markdown_snapshots: _MarkdownSnapshots,
    cache: _ReviewCache,
) -> tuple[str, str | None]:
    key = (
        snapshot.label,
        locator.path.as_posix(),
        locator.extractor,
        locator.locator,
    )
    cached = cache.digests.get(key)
    if cached is not None:
        return cached
    result: tuple[str, str | None]
    try:
        if locator.extractor == "markdown-section":
            markdown = markdown_snapshots.get(
                _markdown_key(snapshot, locator.path)
            )
            if markdown is None or markdown.resolution == "unresolved":
                raise _LocatorUnresolved
            if markdown.resolution == "missing":
                raise _LocatorMissing
            if markdown.text is None or markdown.document is None:
                raise _LocatorUnresolved
            digest = _markdown_section_digest(
                markdown.text,
                markdown.document,
                markdown.pre_masked_ranges,
                locator.locator,
            )
        else:
            text = cache.text(snapshot, locator.path)
        if locator.extractor == "python-symbol":
            digest = _python_symbol_digest(
                cache.python_tree(snapshot, locator.path, text),
                locator.locator,
            )
        elif locator.extractor == "structured-data":
            digest = _structured_data_digest(
                cache.structured_value(snapshot, locator.path, text),
                locator.locator,
            )
        elif locator.extractor != "markdown-section":
            raise _LocatorUnresolved
    except _LocatorMissing:
        result = ("missing", None)
    except _LocatorUnresolved:
        result = ("unresolved", None)
    else:
        result = ("resolved", digest)
    cache.digests[key] = result
    return result


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
    markdown_snapshots: _MarkdownSnapshots,
    cache: _ReviewCache,
) -> ReviewLocatorEvidence:
    base_resolution, base_digest = _digest_at(
        base_snapshot,
        locator,
        markdown_snapshots,
        cache,
    )
    head_resolution, head_digest = _digest_at(
        head_snapshot,
        locator,
        markdown_snapshots,
        cache,
    )
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
    markdown_snapshots: _MarkdownSnapshots,
    cache: _ReviewCache,
) -> ReviewContractResult:
    sources = tuple(
        _evaluate_locator(
            locator,
            base_snapshot,
            head_snapshot,
            markdown_snapshots,
            cache,
        )
        for locator in contract.sources
    )
    targets = tuple(
        _evaluate_locator(
            locator,
            base_snapshot,
            head_snapshot,
            markdown_snapshots,
            cache,
        )
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
    cache = _ReviewCache()
    markdown_snapshots = _prepare_markdown_snapshots(
        (contract,),
        base_snapshot,
        head_snapshot,
        cache,
    )
    return _evaluate_review_contract_snapshots(
        contract,
        base_snapshot,
        head_snapshot,
        markdown_snapshots,
        cache,
    )


def evaluate_review_contracts(
    root: Path,
    contracts: tuple[ReviewContract, ...],
    *,
    base: str,
    head: str,
) -> tuple[ReviewContractResult, ...]:
    base_snapshot, head_snapshot = _snapshots(root, base, head)
    cache = _ReviewCache()
    markdown_snapshots = _prepare_markdown_snapshots(
        contracts,
        base_snapshot,
        head_snapshot,
        cache,
    )
    return tuple(
        _evaluate_review_contract_snapshots(
            contract,
            base_snapshot,
            head_snapshot,
            markdown_snapshots,
            cache,
        )
        for contract in contracts
    )
