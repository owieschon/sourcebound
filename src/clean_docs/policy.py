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
REGISTER_PROFILE = "<!-- clean-docs:policy register-v2 -->"
CANNED_PURPOSE_STEMS = (
    "read this page before changing or relying on",
    "defines the repository's current contract for this surface",
    "it gathers the relevant scope and constraints in one place",
)
NON_PROSE_STARTS = ("#", "- ", "* ", ">", "|", "```", "![", "[![", "<img", "<picture")
POLICY_ALLOW = re.compile(
    r'<!--\s*clean-docs:allow\s+([a-z][a-z-]+)\s+reason="([^"]+)"\s*-->'
)
POLICY_YIELD = re.compile(
    r'<!--\s*clean-docs:yield\s+rule="([a-z][a-z-]+)"\s+'
    r'to="([a-z][a-z-]+)"\s+reason="([^"]+)"\s*-->'
)
ABSTRACTION_SUFFIX = re.compile(r"[a-z]+(?:tion|sion|ment|ance|ence|ivity)\b", re.I)
QUALIFIER = re.compile(r"\b(?:may|only|unless|except)\b", re.I)
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE = re.compile(r"`[^`]*`")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


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


def _rule_allowed(text: str, rule: str) -> bool:
    return any(
        match.group(1) == rule and len(match.group(2).strip()) >= 12
        for match in POLICY_ALLOW.finditer(text)
    )


def _yielded_rules(text: str) -> dict[int, set[str]]:
    yielded: dict[int, set[str]] = {}
    lines = text.splitlines()
    valid_winners = {
        "truth-honesty",
        "grounding",
        "reader-budget",
        "register",
        "warmth",
    }
    for match in POLICY_YIELD.finditer(text):
        if match.group(2) not in valid_winners or len(match.group(3).strip()) < 12:
            continue
        end_line = text.count("\n", 0, match.end()) + 1
        for target_line in range(end_line + 1, len(lines) + 1):
            stripped = lines[target_line - 1].strip()
            if not stripped or stripped.startswith("<!--"):
                continue
            yielded.setdefault(target_line, set()).add(match.group(1))
            break
    return yielded


def _preamble_contract(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    policy = pack["policy"]
    if (
        doc == "<fragment>"
        or REGISTER_PROFILE not in text
        or not policy.get("require_preamble_contract", False)
        or _rule_allowed(text, "preamble-contract")
    ):
        return []
    window_size = int(policy["preamble_window_lines"])
    lines = text.splitlines()
    window = lines[:window_size]
    joined = "\n".join(window)
    has_purpose = PURPOSE_BEGIN in window and PURPOSE_END in window
    has_fence = any(
        re.match(r"```(?:bash|sh|shell|console)\b", line, re.I)
        for line in window
    )
    has_bold_route = bool(re.search(r"\*\*\[[^\]]+\]\([^)]+\)\*\*", joined))
    has_proof = (
        any(line.startswith("[![") for line in window)
        or bool(re.search(r"\b(?:clean-docs\s+)?verify\b", joined, re.I))
        or bool(
            re.search(
                r"\b(?:proof|proves|receipt|outcome|verification)\b",
                joined,
                re.I,
            )
        )
        or any(
            re.search(r"\b(?:proof|receipt|result|outcome|verification)\b", label, re.I)
            for label, _target in MARKDOWN_LINK.findall(joined)
        )
    )
    missing = [
        label
        for label, present in (
            ("marked purpose", has_purpose),
            ("primary action", has_fence or has_bold_route),
            ("proof", has_proof),
        )
        if not present
    ]
    if not missing:
        return []
    return [PolicyFinding(
        doc,
        1,
        "preamble-contract",
        f"put {', '.join(missing)} inside the first {window_size} lines",
    )]


def _paragraphs(text: str) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    current: list[str] = []
    start = 0
    in_fence = False
    visible_text = HTML_COMMENT.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        text,
    )

    def flush() -> None:
        nonlocal current, start
        if current:
            paragraphs.append((start, "\n".join(part.strip() for part in current)))
            current = []
            start = 0

    for line_number, line in enumerate(visible_text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if (
            in_fence
            or not stripped
            or stripped.startswith(("#", "<!--", "|", "- ", "* ", ">", "![", "[!["))
        ):
            flush()
            continue
        if not current:
            start = line_number
        current.append(stripped)
    flush()
    return paragraphs


def _sentences(paragraph: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph)
        if sentence.strip()
    ]


def _visible_sentence(sentence: str) -> str:
    without_targets = MARKDOWN_LINK.sub(lambda match: match.group(1), sentence)
    return INLINE_CODE.sub("", without_targets)


def _section_titles(text: str) -> list[tuple[int, str]]:
    return [
        (line_number, line.lstrip("#").strip().lower())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.startswith("##")
    ]


def _literal_section(line_number: int, sections: list[tuple[int, str]]) -> bool:
    title = ""
    for section_line, candidate in sections:
        if section_line > line_number:
            break
        title = candidate
    return "limit" in title or "security" in title or "privacy" in title


def _register_findings(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    if REGISTER_PROFILE not in text:
        return []
    policy = pack["policy"]
    findings: list[PolicyFinding] = []
    allowlist = {
        str(token).lower() for token in policy["nominalization_allowlist"]
    }
    significance = tuple(
        str(phrase).lower() for phrase in policy["significance_phrases"]
    )
    yielded = _yielded_rules(text)
    sections = _section_titles(text)
    qualifier_scope = doc == "README.md" or doc.startswith("docs/learn/")
    for line_number, paragraph in _paragraphs(text):
        sentences = _sentences(paragraph)
        paragraph_yields = yielded.get(line_number, set())
        if (
            len(sentences) >= 3
            and not _rule_allowed(text, "sentence-variance")
            and "sentence-variance" not in paragraph_yields
        ):
            counts = [len(WORD_RE.findall(sentence)) for sentence in sentences]
            if all(
                int(policy["sentence_variance_min_words"])
                <= count
                <= int(policy["sentence_variance_max_words"])
                for count in counts
            ):
                findings.append(PolicyFinding(
                    doc,
                    line_number,
                    "sentence-variance",
                    "add one short sentence beat or combine claims that share evidence",
                ))
        offset = 0
        for sentence in sentences:
            sentence_line = line_number + paragraph[:offset].count("\n")
            offset += len(sentence) + 1
            lowered = _visible_sentence(sentence).lower()
            if (
                not _rule_allowed(text, "nominalization-density")
                and "nominalization-density" not in paragraph_yields
            ):
                abstractions = [
                    token
                    for token in ABSTRACTION_SUFFIX.findall(lowered)
                    if token not in allowlist
                ]
                if len(abstractions) >= int(policy["nominalization_threshold"]):
                    findings.append(PolicyFinding(
                        doc,
                        sentence_line,
                        "nominalization-density",
                        "replace clustered abstractions with actors and concrete verbs: "
                        + ", ".join(abstractions),
                    ))
            if (
                not _rule_allowed(text, "significance-narration")
                and "significance-narration" not in paragraph_yields
                and (match := next((phrase for phrase in significance if phrase in lowered), None))
            ):
                findings.append(PolicyFinding(
                    doc,
                    sentence_line,
                    "significance-narration",
                    f"replace {match!r} with the consequence for the reader",
                ))
            if (
                qualifier_scope
                and not _literal_section(sentence_line, sections)
                and not _rule_allowed(text, "qualifier-density")
                and "qualifier-density" not in paragraph_yields
            ):
                guards = QUALIFIER.findall(sentence)
                if len(guards) > int(policy["qualifier_threshold"]):
                    findings.append(PolicyFinding(
                        doc,
                        sentence_line,
                        "qualifier-density",
                        "move a guard to the canonical limits page or split the authority boundary",
                    ))
    return findings


def _purpose_contract(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    if (
        REGISTER_PROFILE not in text
        or not pack["policy"].get("require_purpose_contract", False)
    ):
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
        if (
            not stripped
            or stripped.startswith("<!-- clean-docs:allow ")
            or stripped == REGISTER_PROFILE
        ):
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
    lowered_prose = prose.lower()
    if any(stem in lowered_prose for stem in CANNED_PURPOSE_STEMS):
        return [PolicyFinding(
            doc,
            begin_lines[0] + 2,
            "purpose-contract",
            "replace stock purpose language with the subject, operator, consequential failure, and authority boundary",
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
    return True


def ensure_purpose_contract(text: str, *, fallback: bool = False) -> str:
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
        return text
    else:
        start, end, purpose_lines = selected
        remaining = lines[:start] + lines[end:]
        if start < insertion:
            insertion -= end - start
    replacement = [PURPOSE_BEGIN, *purpose_lines, PURPOSE_END]
    updated = remaining[:insertion] + replacement + remaining[insertion:]
    return "\n".join(updated).rstrip() + "\n"


def check_prose(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    if REGISTER_PROFILE not in text:
        return []
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


def check_document(
    doc: str,
    text: str,
    pack: dict[str, Any],
    *,
    semantic_text: str | None = None,
) -> list[PolicyFinding]:
    from clean_docs.accessibility import check_accessibility

    return (
        _purpose_contract(doc, text, pack)
        + _preamble_contract(doc, text, pack)
        + check_prose(doc, text, pack)
        + _register_findings(doc, text, pack)
        + check_accessibility(doc, semantic_text if semantic_text is not None else text, pack)
    )


def check_documents(documents: dict[str, str], pack: dict[str, Any]) -> list[PolicyFinding]:
    return [
        finding
        for doc, text in documents.items()
        for finding in check_document(doc, text, pack)
    ]
