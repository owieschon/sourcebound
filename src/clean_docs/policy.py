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


def _prose_lines(text: str) -> list[tuple[int, str]]:
    result = []
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and "slop-ok:" not in line:
            result.append((line_number, line))
    return result


def check_document(doc: str, text: str, pack: dict[str, Any]) -> list[PolicyFinding]:
    policy = pack["policy"]
    boosters = tuple(str(word) for word in policy["prohibited_boosters"])
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(word) for word in boosters) + r")\b", re.I)
    findings = []
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


def check_documents(documents: dict[str, str], pack: dict[str, Any]) -> list[PolicyFinding]:
    return [
        finding
        for doc, text in documents.items()
        for finding in check_document(doc, text, pack)
    ]
