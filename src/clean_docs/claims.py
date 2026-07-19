"""Discover and verify bounded source-to-prose claim relationships."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from clean_docs.applicability import classify_document
from clean_docs.models import BindingResult, Provenance, SourceClaimCheck


CLAIM_REPORT_SCHEMA = "clean-docs.source-claims.v1"
MAX_RANKED_CANDIDATES = 100
SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBER = re.compile(r"(?<![\w.])(\d[\d,]*)(?![\w.])")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
TABLE_KEY = re.compile(r"^\s*\|?\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\|")
STOP_SUBJECTS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
OWNERSHIP_STOP = STOP_SUBJECTS | {
    "api",
    "backend",
    "catalog",
    "config",
    "configuration",
    "data",
    "doc",
    "docs",
    "guide",
    "index",
    "readme",
    "reference",
    "script",
    "scripts",
    "service",
    "settings",
    "skill",
    "test",
    "tests",
    "util",
    "utils",
}


@dataclass(frozen=True)
class SourceFact:
    kind: str
    source: str
    locator: str
    line: int
    subjects: tuple[str, ...]
    value: int | tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class DocumentClaim:
    kind: str
    doc: str
    anchor: str
    line: int
    subject: str
    value: int | tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class SourceClaimResult:
    id: str
    kind: str
    doc: str
    anchor: str
    line: int
    subject: str
    source: str
    locator: str
    source_line: int
    document_value: int | tuple[str, ...]
    source_value: int | tuple[str, ...]
    status: str
    authority: str
    rank: int
    document_digest: str
    source_digest: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ("document_value", "source_value"):
            value = payload[key]
            if isinstance(value, tuple):
                payload[key] = list(value)
        return payload


@dataclass(frozen=True)
class MissingSourceClaim:
    id: str
    kind: str
    doc: str
    anchor: str
    subject: str
    source: str
    locator: str
    detail: str


@dataclass(frozen=True)
class SourceClaimReport:
    authority: str
    results: tuple[SourceClaimResult, ...]
    candidates: tuple[SourceClaimResult, ...]
    missing: tuple[MissingSourceClaim, ...]
    candidate_totals: tuple[tuple[str, int], ...]

    @property
    def ok(self) -> bool:
        return not self.missing and not any(
            result.status == "drift" for result in self.results
        )

    def as_dict(self) -> dict[str, object]:
        candidate_population = sum(count for _status, count in self.candidate_totals)
        return {
            "schema": CLAIM_REPORT_SCHEMA,
            "ok": self.ok,
            "authority": self.authority,
            "results": [result.as_dict() for result in self.results],
            "candidates": [result.as_dict() for result in self.candidates],
            "missing": [asdict(item) for item in self.missing],
            "candidate_totals": dict(self.candidate_totals),
            "candidate_population": candidate_population,
            "candidate_shown": len(self.candidates),
            "candidate_truncated": max(
                0, candidate_population - len(self.candidates)
            ),
        }


def _digest(value: Any) -> str:
    normalized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _subject(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if normalized.endswith("ies") and len(normalized) > 4:
        return normalized[:-3] + "y"
    if normalized.endswith(("sses", "xes", "zes", "ches", "shes")):
        return normalized[:-2]
    if normalized.endswith("s") and not normalized.endswith("ss") and len(normalized) > 3:
        return normalized[:-1]
    return normalized


def _tokens(value: str) -> tuple[str, ...]:
    parts = (
        re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
        .replace("_", " ")
        .replace("-", " ")
    )
    return tuple(
        sorted(
            {
                normalized
                for token in WORD.findall(parts)
                if (normalized := _subject(token)) and normalized not in STOP_SUBJECTS
            }
        )
    )


def _slug(value: str) -> str:
    visible = re.sub(r"[`*_]", "", value)
    return re.sub(r"[^a-z0-9 -]", "", visible.lower()).replace(" ", "-").strip("-")


def _repository_files(root: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        proc = None
    if proc is not None and proc.returncode == 0:
        candidates = [
            root / item for item in proc.stdout.decode(errors="surrogateescape").split("\0")
            if item
        ]
    else:
        candidates = list(root.rglob("*"))
    return sorted(
        path
        for path in candidates
        if _inside_regular_file(root, path)
        and not set(path.relative_to(root).parts) & SKIP_PARTS
        and "docs/archive" not in path.relative_to(root).as_posix()
    )


def _inside_regular_file(root: Path, path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _assignment(node: ast.AST) -> tuple[str, ast.AST] | None:
    if isinstance(node, ast.Assign):
        target = next(
            (
                item.id
                for item in node.targets
                if isinstance(item, ast.Name)
            ),
            None,
        )
        return (target, node.value) if target is not None else None
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    ):
        return node.target.id, node.value
    return None


def _sequence_length(node: ast.AST) -> int | None:
    if isinstance(node, (ast.List, ast.Tuple)):
        return len(node.elts)
    candidates: list[ast.AST | None]
    if isinstance(node, ast.Set):
        candidates = list(node.elts)
    elif isinstance(node, ast.Dict):
        candidates = list(node.keys)
    else:
        return None
    if candidates:
        keys: set[object] = set()
        for key in candidates:
            if key is None:
                return None
            try:
                value = ast.literal_eval(key)
                hash(value)
            except (TypeError, ValueError):
                return None
            keys.add(value)
        return len(keys)
    return 0


def _mapping_keys(node: ast.AST) -> tuple[str, ...] | None:
    if not isinstance(node, ast.Dict):
        return None
    keys: list[str] = []
    for key in node.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return None
        if not key.value.startswith("_"):
            keys.append(key.value)
    return tuple(sorted(set(keys)))


def _keyword(node: ast.Call, name: str) -> ast.AST | None:
    return next(
        (
            item.value
            for item in node.keywords
            if item.arg == name
        ),
        None,
    )


def _source_facts(path: str, text: str) -> list[SourceFact]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError:
        return []
    facts: list[SourceFact] = []
    for node in tree.body:
        assigned = _assignment(node)
        if assigned is None:
            continue
        symbol, value = assigned
        symbol_subjects = set(_tokens(symbol))
        if isinstance(value, ast.Call):
            name_value = _keyword(value, "name")
            if (
                isinstance(name_value, ast.Constant)
                and isinstance(name_value.value, str)
            ):
                symbol_subjects.update(_tokens(name_value.value))
        count = _sequence_length(value)
        if count is not None:
            facts.append(
                SourceFact(
                    "count",
                    path,
                    f"{symbol}#count",
                    node.lineno,
                    tuple(sorted(symbol_subjects)),
                    count,
                    _digest(count),
                )
            )
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            totals: dict[str, int] = {}
            seen: dict[str, int] = {}
            for item in value.elts:
                if not isinstance(item, ast.Call):
                    continue
                for keyword in item.keywords:
                    if keyword.arg is None:
                        continue
                    length = _sequence_length(keyword.value)
                    if length is None:
                        continue
                    totals[keyword.arg] = totals.get(keyword.arg, 0) + length
                    seen[keyword.arg] = seen.get(keyword.arg, 0) + 1
            for keyword_name, total in sorted(totals.items()):
                if seen[keyword_name] != len(value.elts):
                    continue
                facts.append(
                    SourceFact(
                        "count",
                        path,
                        f"{symbol}.{keyword_name}#count",
                        node.lineno,
                        tuple(sorted(set(_tokens(keyword_name)) | symbol_subjects)),
                        total,
                        _digest(total),
                    )
                )
        direct_keys = _mapping_keys(value)
        if direct_keys is not None:
            facts.append(
                SourceFact(
                    "identifier-set",
                    path,
                    f"{symbol}#keys",
                    node.lineno,
                    tuple(sorted(symbol_subjects)),
                    direct_keys,
                    _digest(direct_keys),
                )
            )
        if isinstance(value, ast.Call):
            for keyword in value.keywords:
                if keyword.arg is None:
                    continue
                keys = _mapping_keys(keyword.value)
                if keys is None:
                    continue
                facts.append(
                    SourceFact(
                        "identifier-set",
                        path,
                        f"{symbol}.{keyword.arg}#keys",
                        node.lineno,
                        tuple(sorted(symbol_subjects)),
                        keys,
                        _digest(keys),
                    )
                )
    return facts


def _count_claims(path: str, lines: list[str]) -> list[DocumentClaim]:
    claims: list[DocumentClaim] = []
    anchor = ""
    in_fence = False
    for line_number, line in enumerate(lines, start=1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if match := HEADING.match(line):
            anchor = _slug(match.group(2))
            continue
        if in_fence:
            continue
        for number in NUMBER.finditer(line):
            value = int(number.group(1).replace(",", ""))
            tail = line[number.end():]
            boundary = re.search(r"[().,;:]", tail)
            if boundary:
                tail = tail[:boundary.start()]
            words = WORD.findall(tail)[:3]
            if not words or not words[-1].lower().endswith("s"):
                continue
            subject = words[-1].lower()
            if not _subject(subject) or _subject(subject) in STOP_SUBJECTS:
                continue
            claims.append(
                DocumentClaim(
                    "count",
                    path,
                    anchor,
                    line_number,
                    subject,
                    value,
                    _digest(line),
                )
            )
    return claims


def _table_subject(title: str) -> str:
    inline = re.findall(r"`([^`]+)`", title)
    if inline:
        return _subject(inline[-1].split(".")[-1])
    words = WORD.findall(title)
    return _subject(words[0]) if words else ""


def _table_claims(path: str, lines: list[str]) -> list[DocumentClaim]:
    claims: list[DocumentClaim] = []
    parent_title = ""
    parent_anchor = ""
    collecting = False
    table_subject = ""
    table_anchor = ""
    table_line = 0
    keys: list[str] = []

    def flush() -> None:
        if table_subject and keys:
            value = tuple(sorted(set(keys)))
            claims.append(
                DocumentClaim(
                    "identifier-set",
                    path,
                    table_anchor,
                    table_line,
                    table_subject,
                    value,
                    _digest(value),
                )
            )

    for line_number, line in enumerate([*lines, "# end"], start=1):
        heading = HEADING.match(line)
        if heading:
            title = heading.group(2)
            if collecting:
                flush()
                collecting = False
                keys = []
            if _subject(title) == "column":
                collecting = True
                table_subject = _table_subject(parent_title)
                table_anchor = parent_anchor
                table_line = line_number + 1
            else:
                parent_title = title
                parent_anchor = _slug(title)
            continue
        if not collecting:
            continue
        match = TABLE_KEY.match(line)
        if match and match.group(1).lower() not in {"column", "type", "nullable"}:
            keys.append(match.group(1))
    return claims


def _relationship_rank(claim: DocumentClaim, fact: SourceFact) -> int:
    doc = claim.doc
    source = fact.source
    anchor = claim.anchor
    doc_parts = Path(doc).parent.parts
    source_parts = Path(source).parent.parts
    common = 0
    for left, right in zip(doc_parts, source_parts):
        if left != right:
            break
        common += 1
    doc_stem = set(_tokens(Path(doc).stem)) - OWNERSHIP_STOP
    anchor_context = set(_tokens(anchor))
    source_context = set(_tokens(Path(source).stem)) - OWNERSHIP_STOP
    locator_parts = fact.locator.rsplit("#", 1)[0].split(".")
    root_subject = _subject(locator_parts[0])
    claim_subject = _subject(claim.subject)
    exact_root = claim_subject == root_subject
    exact_nested = (
        len(locator_parts) > 1
        and claim_subject == _subject(locator_parts[-1])
    )
    same_parent = Path(doc).parent == Path(source).parent
    stem_overlap = bool(doc_stem & source_context)
    anchor_match = claim_subject in anchor_context
    exact_locator = exact_root or exact_nested
    if claim.kind == "identifier-set":
        ownership = same_parent or stem_overlap or (exact_locator and anchor_match)
    else:
        ownership = same_parent or stem_overlap
    if not ownership:
        return 0
    if not exact_locator and not (
        same_parent and (stem_overlap or anchor_match)
    ):
        return 0

    rank = min(common, 2) * 10
    rank += 100 if same_parent else 0
    rank += 300 if stem_overlap else 0
    rank += 100 if anchor_match else 0
    if exact_locator:
        rank += 200
    elif claim_subject in _tokens(locator_parts[0]):
        rank += 50 if len(locator_parts) == 1 else 25
    return rank


def _result(
    *,
    identifier: str,
    claim: DocumentClaim,
    fact: SourceFact,
    authority: str,
    rank: int,
) -> SourceClaimResult:
    status = "current" if claim.value == fact.value else "drift"
    if claim.kind == "count":
        detail = (
            f"document says {claim.value} {claim.subject}; "
            f"{fact.source}#{fact.locator} contains {fact.value}"
        )
    else:
        assert isinstance(claim.value, tuple)
        assert isinstance(fact.value, tuple)
        document_keys = set(claim.value)
        source_keys = set(fact.value)
        missing = sorted(source_keys - document_keys)
        extra = sorted(document_keys - source_keys)
        detail = (
            f"document/source identifier sets differ; missing from document: {missing}; "
            f"not in source: {extra}"
        )
    return SourceClaimResult(
        identifier,
        claim.kind,
        claim.doc,
        claim.anchor,
        claim.line,
        claim.subject,
        fact.source,
        fact.locator,
        fact.line,
        claim.value,
        fact.value,
        status,
        authority,
        rank,
        claim.digest,
        fact.digest,
        detail,
    )


def _candidate_id(claim: DocumentClaim, fact: SourceFact) -> str:
    payload = [
        claim.kind,
        claim.doc,
        claim.anchor,
        claim.subject,
        fact.source,
        fact.locator,
    ]
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode()
    ).hexdigest()


def _totals(results: list[SourceClaimResult]) -> tuple[tuple[str, int], ...]:
    totals: dict[str, int] = {}
    for result in results:
        totals[result.status] = totals.get(result.status, 0) + 1
    return tuple(sorted(totals.items()))


def scan_source_claims(
    root: Path,
    checks: tuple[SourceClaimCheck, ...] = (),
    *,
    discover: bool = True,
) -> SourceClaimReport:
    root = root.resolve()
    facts: list[SourceFact] = []
    claims: list[DocumentClaim] = []
    accepted_docs = {check.doc.as_posix() for check in checks}
    accepted_sources = {check.source.as_posix() for check in checks}
    scoped_paths = accepted_docs | accepted_sources
    paths = (
        _repository_files(root)
        if discover
        else [
            root / relative
            for relative in sorted(scoped_paths)
            if _inside_regular_file(root, root / relative)
        ]
    )
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if path.suffix == ".py":
            facts.extend(_source_facts(relative, text))
        elif path.suffix.lower() in {".md", ".mdx"}:
            lines = text.splitlines()
            profile = classify_document(Path(relative), text)
            discoverable = discover and profile.role not in {
                "architecture",
                "evidence",
                "plan",
                "template",
            }
            if not discoverable and relative not in accepted_docs:
                continue
            claims.extend(_count_claims(relative, lines))
            claims.extend(_table_claims(relative, lines))

    fact_index = {
        (fact.kind, fact.source, fact.locator): fact
        for fact in facts
    }
    results: list[SourceClaimResult] = []
    missing: list[MissingSourceClaim] = []
    accepted_relationships: set[tuple[str, str, str, str, str, str]] = set()
    for check in checks:
        relationship = (
            check.kind,
            check.doc.as_posix(),
            check.anchor,
            _subject(check.subject),
            check.source.as_posix(),
            check.locator,
        )
        accepted_relationships.add(relationship)
        fact = fact_index.get((check.kind, check.source.as_posix(), check.locator))
        accepted_claims = [
            claim
            for claim in claims
            if claim.kind == check.kind
            and claim.doc == check.doc.as_posix()
            and claim.anchor == check.anchor
            and _subject(claim.subject) == _subject(check.subject)
        ]
        if fact is None or len(accepted_claims) != 1:
            reason = (
                "source locator was not found"
                if fact is None
                else f"document relationship resolved to {len(accepted_claims)} claims"
            )
            missing.append(
                MissingSourceClaim(
                    check.id,
                    check.kind,
                    check.doc.as_posix(),
                    check.anchor,
                    check.subject,
                    check.source.as_posix(),
                    check.locator,
                    reason,
                )
            )
            continue
        results.append(
            _result(
                identifier=check.id,
                claim=accepted_claims[0],
                fact=fact,
                authority="enforced",
                rank=10_000,
            )
        )

    candidates: list[SourceClaimResult] = []
    for claim in claims if discover else ():
        fact_matches = [
            fact
            for fact in facts
            if fact.kind == claim.kind and _subject(claim.subject) in fact.subjects
        ]
        if not fact_matches:
            continue
        ranked = sorted(
            (
                (_relationship_rank(claim, fact), fact)
                for fact in fact_matches
            ),
            key=lambda item: (-item[0], item[1].source, item[1].locator),
        )
        best_rank = ranked[0][0]
        if best_rank < 100:
            continue
        best = [fact for rank, fact in ranked if rank == best_rank]
        if len(best) != 1:
            continue
        fact = best[0]
        relationship = (
            claim.kind,
            claim.doc,
            claim.anchor,
            _subject(claim.subject),
            fact.source,
            fact.locator,
        )
        if relationship in accepted_relationships:
            continue
        candidates.append(
            _result(
                identifier=_candidate_id(claim, fact),
                claim=claim,
                fact=fact,
                authority="assessment",
                rank=best_rank,
            )
        )
    candidates.sort(
        key=lambda item: (
            -item.rank,
            item.status != "drift",
            item.doc,
            item.line,
            item.source,
            item.locator,
        )
    )
    bounded = tuple(candidates[:MAX_RANKED_CANDIDATES])
    return SourceClaimReport(
        "enforced" if checks else "assessment",
        tuple(sorted(results, key=lambda item: item.id)),
        bounded,
        tuple(sorted(missing, key=lambda item: item.id)),
        _totals(candidates),
    )


def claim_binding_results(
    report: SourceClaimReport,
    *,
    ref: str,
) -> list[BindingResult]:
    """Project accepted claim checks into the existing read-only check contract."""
    results = [
        BindingResult(
            binding_id=item.id,
            doc=item.doc,
            changed=item.status == "drift",
            expected=json.dumps(item.source_value, sort_keys=True),
            observed=json.dumps(item.document_value, sort_keys=True),
            diff="" if item.status == "current" else item.detail + "\n",
            provenance=Provenance(
                ref,
                item.source,
                item.locator,
                f"source-claim-{item.kind}@1",
                item.source_digest,
            ),
            binding_type="source-claim",
        )
        for item in report.results
    ]
    for item in report.missing:
        results.append(
            BindingResult(
                binding_id=item.id,
                doc=item.doc,
                changed=True,
                expected="accepted source claim relationship",
                observed="missing",
                diff=f"accepted source claim {item.id} cannot be verified: {item.detail}\n",
                provenance=Provenance(
                    ref,
                    item.source,
                    item.locator,
                    f"source-claim-{item.kind}@1",
                    _digest([item.source, item.locator]),
                ),
                binding_type="source-claim",
            )
        )
    return sorted(results, key=lambda item: item.binding_id)
