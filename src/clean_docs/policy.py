from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyFinding:
    doc: str
    line: int
    rule: str
    detail: str


H1_RE = re.compile(r"^#\s+(.+?)\s*$")
WORD_RE = re.compile(r"[a-z0-9]+")
TITLE_FILLER = {
    "a",
    "an",
    "the",
    "this",
    "page",
    "document",
    "guide",
    "describes",
    "explains",
    "defines",
    "covers",
    "is",
}
PURPOSE_BEGIN = "<!-- clean-docs:purpose -->"
PURPOSE_END = "<!-- clean-docs:end purpose -->"
NON_PROSE_STARTS = ("#", "- ", "* ", ">", "|", "```", "![", "[![", "<img", "<picture")


def _prose_lines(text: str) -> list[tuple[int, str]]:
    result = []
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and "slop-ok:" not in line and not line.startswith("#"):
            result.append((line_number, line))
    return result


def _title_tokens(text: str) -> set[str]:
    return {
        token
        for token in WORD_RE.findall(text.lower())
        if token not in TITLE_FILLER
    }


def _outside_fences(lines: list[str]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append((index, line))
    return result


def _purpose_contract(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    if not pack["policy"].get("require_purpose_contract", False):
        return []
    contract = pack["style"]["purpose_contract"]
    begin = str(contract["begin_marker"])
    end = str(contract["end_marker"])
    lines = text.splitlines()
    structural_lines = _outside_fences(lines)
    headings = [
        (index, match.group(1))
        for index, line in structural_lines
        if (match := H1_RE.match(line))
    ]
    if len(headings) != 1:
        return [PolicyFinding(
            doc,
            1,
            "purpose-contract",
            "add one H1 followed immediately by one marked BLUF purpose contract",
        )]
    begin_lines = [index for index, line in structural_lines if line.strip() == begin]
    end_lines = [index for index, line in structural_lines if line.strip() == end]
    if len(begin_lines) != 1 or len(end_lines) != 1 or begin_lines[0] >= end_lines[0]:
        return [PolicyFinding(
            doc,
            headings[0][0] + 1,
            "purpose-contract",
            "add exactly one complete marked BLUF purpose contract after the H1",
        )]
    h1_index, title = headings[0]
    first_body = h1_index + 1
    while first_body < len(lines):
        stripped = lines[first_body].strip()
        if not stripped or stripped.startswith("<!-- clean-docs:allow "):
            first_body += 1
            continue
        break
    if first_body != begin_lines[0]:
        return [PolicyFinding(
            doc,
            begin_lines[0] + 1,
            "purpose-contract",
            "move the purpose contract before all body content",
        )]
    body = lines[begin_lines[0] + 1:end_lines[0]]
    prose = " ".join(line.strip() for line in body if line.strip())
    if not prose or any(
        line.lstrip().lower().startswith(NON_PROSE_STARTS)
        for line in body
        if line.strip()
    ):
        return [PolicyFinding(
            doc,
            begin_lines[0] + 1,
            "purpose-contract",
            "write the purpose contract as one plain prose block",
        )]
    first_sentence = re.split(r"(?<=[.!?])\s+", prose, maxsplit=1)[0]
    title_tokens = _title_tokens(title)
    sentence_tokens = _title_tokens(first_sentence)
    if title_tokens and title_tokens <= sentence_tokens and len(sentence_tokens - title_tokens) < 3:
        return [PolicyFinding(
            doc,
            begin_lines[0] + 2,
            "purpose-contract",
            "replace the title restatement with applicability, problem, and outcome",
        )]
    return []


def _substantive_purpose(lines: list[str]) -> bool:
    prose = " ".join(line.strip() for line in lines).strip()
    words = WORD_RE.findall(prose.lower())
    if len(words) < 8:
        return False
    if all(re.match(r"^(?:\*\*)?[^:]{1,32}:(?:\*\*)?\s*", line.strip()) for line in lines):
        return False
    signals = {
        "use", "when", "for", "before", "without", "after", "lets", "gives",
        "exposes", "accepts", "describes", "documents", "captures", "flags",
        "prevents", "allows", "provides", "returns", "helps",
    }
    return len(words) >= 30 or bool(signals & set(words))


def ensure_purpose_contract(text: str, *, fallback: bool = True) -> str:
    """Move substantive authored prose to the opening contract or add an optional fallback."""
    if PURPOSE_BEGIN in text or PURPOSE_END in text:
        return text
    lines = text.splitlines()
    heading = next(
        ((index, match.group(1)) for index, line in _outside_fences(lines) if (match := H1_RE.match(line))),
        None,
    )
    if heading is None:
        return text
    h1_index, title = heading
    title_tokens = _title_tokens(title)
    selected: tuple[int, int, list[str]] | None = None
    rejected_restatements: list[tuple[int, int]] = []
    index = h1_index + 1
    in_fence = False
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("## "):
            break
        if stripped.startswith("```"):
            in_fence = not in_fence
            index += 1
            continue
        if (
            in_fence
            or not stripped
            or stripped.startswith("<!--")
            or stripped.lower().startswith(NON_PROSE_STARTS)
        ):
            index += 1
            continue
        end = index
        while end < len(lines) and lines[end].strip():
            candidate = lines[end].lstrip()
            if candidate.lower().startswith(NON_PROSE_STARTS) or candidate.startswith("<!--"):
                break
            end += 1
        paragraph = lines[index:end]
        opening = " ".join(line.strip() for line in paragraph)
        opening_tokens = _title_tokens(
            re.split(r"(?<=[.!?])\s+", opening, maxsplit=1)[0]
        )
        restates_title = (
            bool(title_tokens)
            and title_tokens <= opening_tokens
            and len(opening_tokens - title_tokens) < 3
        )
        if not restates_title:
            if fallback or _substantive_purpose(paragraph):
                selected = (index, end, paragraph)
                break
        else:
            rejected_restatements.append((index, end))
        index = max(end, index + 1)

    insertion = h1_index + 1
    while insertion < len(lines) and (
        not lines[insertion].strip()
        or lines[insertion].strip().startswith("<!-- clean-docs:allow ")
    ):
        insertion += 1
    if selected is None:
        if not fallback:
            return text
        topic = " ".join(title.split())
        opening = (
            f"Use this page when you need to understand {topic} before changing this repository. "
            "Without the documented scope and constraints, a change can rely on behavior the "
            "project does not promise; after reading, you can work from the stated contract."
        )
        purpose_lines = [opening]
        remaining = lines
        for start, end in reversed(rejected_restatements):
            remaining = remaining[:start] + remaining[end:]
    else:
        start, end, purpose_lines = selected
        remaining = lines[:start] + lines[end:]
        if start < insertion:
            insertion -= end - start
    replacement = [PURPOSE_BEGIN, *purpose_lines, PURPOSE_END]
    updated = remaining[:insertion] + replacement + remaining[insertion:]
    return "\n".join(updated).rstrip() + "\n"


def check_prose(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    policy = pack["policy"]
    boosters = tuple(str(word) for word in policy["prohibited_boosters"])
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(word) for word in boosters) + r")\b", re.I)
    findings: list[PolicyFinding] = []
    for line_number, line in _prose_lines(text):
        match = pattern.search(line)
        if match:
            findings.append(PolicyFinding(
                doc=doc,
                line=line_number,
                rule="prohibited-booster",
                detail=f"remove {match.group(0)!r} or state the claim directly",
            ))
    return findings


def check_document(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    return _purpose_contract(doc, text, pack) + check_prose(doc, text, pack)


def check_documents(documents: dict[str, str], pack: dict[str, Any]) -> list[PolicyFinding]:
    return [
        finding
        for doc, text in documents.items()
        for finding in check_document(doc, text, pack)
    ]
