"""Compile advisory documentation obligations without mutating repository authority."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from sourcebound.inventory import scan_inventory


_INLINE_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
_REFERENCE_LINK = re.compile(r"(?<!!)\[[^\]]+\]\[([^\]]+)\]")
_REFERENCE_DEFINITION = re.compile(r"^\[([^\]]+)\]:\s*(\S+)", re.MULTILINE)
_SHORTCUT_LINK = re.compile(r"(?<!!)\[([^\]]+)\](?![\[(])")
_EXCLUDED_PARTS = frozenset({"archive", "generated", ".sourcebound", "tests"})


@dataclass(frozen=True)
class ObligationCandidate:
    id: str
    document: str
    surface_id: str
    surface_kind: str
    surface_locator: str
    evidence: tuple[str, ...]
    authority: str = "assessment"
    next_action: str = "A separate operator decision is required before any authority changes."


@dataclass(frozen=True)
class ObligationUnknown:
    id: str
    target: str
    reason: str
    evidence: tuple[str, ...]
    authority: str = "assessment"
    next_action: str = "Review the evidence; this result cannot change repository authority."


@dataclass(frozen=True)
class ObligationReport:
    candidates: tuple[ObligationCandidate, ...]
    unknowns: tuple[ObligationUnknown, ...]
    candidate_population: int
    candidate_shown: int
    candidate_truncated: int
    unknown_population: int
    unknown_shown: int
    unknown_truncated: int


def _stable_id(kind: str, *parts: str) -> str:
    value = "\x1f".join(("sourcebound.obligation.v1", kind, *parts))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _unknown(target: str, reason: str, evidence: str) -> ObligationUnknown:
    return ObligationUnknown(_stable_id("unknown", target, reason, evidence), target, reason, (evidence,))


def _readme_links(text: str) -> tuple[tuple[str, str], ...]:
    definitions = {name.casefold(): target for name, target in _REFERENCE_DEFINITION.findall(text)}
    links: list[tuple[str, str]] = [("inline", target.strip()) for target in _INLINE_LINK.findall(text)]
    links.extend(
        ("reference", definitions[name.casefold()])
        for name in _REFERENCE_LINK.findall(text)
        if name.casefold() in definitions
    )
    links.extend(("unsupported", label) for label in _SHORTCUT_LINK.findall(text))
    return tuple(links)


def _local_document(target: str) -> tuple[str | None, str | None]:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None, "external-link"
    path = parsed.path
    if not path or path.startswith("/") or any(part == ".." for part in PurePosixPath(path).parts):
        return None, "unsafe-local-link"
    relative = PurePosixPath(path)
    if relative.suffix.lower() not in {".md", ".mdx"}:
        return None, "unsupported-local-target"
    if any(part.casefold() in _EXCLUDED_PARTS or part.startswith(".") for part in relative.parts):
        return None, "excluded-document"
    return relative.as_posix(), None


def compile_obligations(root: Path, *, limit: int = 12) -> ObligationReport:
    """Return bounded advisory evidence without writing files or invoking writers."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    root = root.resolve()
    readme = root / "README.md"
    if not readme.is_file():
        return ObligationReport((), (), 0, 0, 0, 0, 0, 0)
    try:
        links = _readme_links(readme.read_text(encoding="utf-8"))
    except OSError:
        return ObligationReport((), (), 0, 0, 0, 0, 0, 0)

    surfaces = tuple(
        item for item in scan_inventory(root).items if item.kind in {"cli-command", "cli-option"}
    )
    candidates: list[ObligationCandidate] = []
    unknowns: list[ObligationUnknown] = []
    for form, target in links:
        evidence = f"README.md:{form}:{target}"
        if form == "unsupported":
            unknowns.append(_unknown(target, "unsupported-link-form", evidence))
            continue
        relative, reason = _local_document(target)
        if reason is not None:
            unknowns.append(_unknown(target, reason, evidence))
            continue
        assert relative is not None
        document = root / relative
        if not document.is_file():
            unknowns.append(_unknown(relative, "missing-local-document", evidence))
            continue
        try:
            content = document.read_text(encoding="utf-8")
        except OSError:
            unknowns.append(_unknown(relative, "unreadable-local-document", evidence))
            continue
        matched = tuple(item for item in surfaces if item.name in content)
        if not matched:
            unknowns.append(_unknown(relative, "no-local-surface-evidence", evidence))
            continue
        for item in matched:
            candidate_evidence = (evidence, f"inventory:{item.id}")
            candidates.append(
                ObligationCandidate(
                    _stable_id("candidate", relative, item.id, *candidate_evidence),
                    relative,
                    item.id,
                    item.kind,
                    item.locator,
                    candidate_evidence,
                )
            )
    unique_candidates = {candidate.id: candidate for candidate in candidates}
    unique_unknowns = {unknown.id: unknown for unknown in unknowns}
    all_candidates = tuple(unique_candidates[key] for key in sorted(unique_candidates))
    all_unknowns = tuple(unique_unknowns[key] for key in sorted(unique_unknowns))
    return ObligationReport(
        all_candidates[:limit],
        all_unknowns[:limit],
        len(all_candidates),
        min(len(all_candidates), limit),
        max(0, len(all_candidates) - limit),
        len(all_unknowns),
        min(len(all_unknowns), limit),
        max(0, len(all_unknowns) - limit),
    )
