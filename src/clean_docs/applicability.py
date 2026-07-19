from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from clean_docs.policy import REGISTER_PROFILE


DocumentRole = Literal[
    "agent-procedure",
    "architecture",
    "component-overview",
    "evidence",
    "overview",
    "plan",
    "reference",
    "task",
    "template",
    "troubleshooting",
    "tutorial",
]

ROLE_RULES: dict[DocumentRole, frozenset[str]] = {
    "overview": frozenset({
        "purpose-contract",
        "purpose-template",
        "preamble-contract",
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
        "qualifier-density",
        "doc-length",
        "section-length",
        "readme-routing",
        "readme-reference-depth",
        "elaboration-depth",
    }),
    "component-overview": frozenset({
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
    }),
    "tutorial": frozenset({
        "purpose-contract",
        "purpose-template",
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
        "doc-length",
        "section-length",
        "elaboration-depth",
    }),
    "task": frozenset({
        "purpose-contract",
        "purpose-template",
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
        "doc-length",
        "section-length",
    }),
    "troubleshooting": frozenset({
        "purpose-contract",
        "purpose-template",
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
    }),
    "architecture": frozenset({
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
    }),
    "reference": frozenset({
        "prohibited-booster",
        "nominalization-density",
        "significance-narration",
    }),
    # These files are inputs, procedures, plans, or records. Rewriting them into a
    # generic reader page can change runtime behavior or erase evidence.
    "agent-procedure": frozenset(),
    "template": frozenset(),
    "evidence": frozenset(),
    "plan": frozenset(),
}
ROLE_DESCRIPTIONS: dict[DocumentRole, str] = {
    "overview": "repository entry point for orientation and routing",
    "component-overview": "component-local entry point whose parent supplies context",
    "tutorial": "ordered learning path to a verified result",
    "task": "procedure or explanation for one reader job",
    "troubleshooting": "symptom-to-diagnosis-to-recovery procedure",
    "reference": "lookup surface for exact current facts",
    "architecture": "design boundary, decision, or time-horizon record",
    "plan": "time-scoped work whose live or historical status needs judgment",
    "evidence": "review, result, or longitudinal observation record",
    "agent-procedure": "executable instructions for an agent reader",
    "template": "runtime prompt or generated-content input",
}
ROLE_OVERRIDE = re.compile(
    r"(?:<!--|\{/\*)\s*clean-docs:role\s+([a-z][a-z-]+)\s*(?:-->|\*/\})"
)
ROLE_MARKER = re.compile(
    r"(?:<!--|\{/\*)\s*clean-docs:role\b.*?(?:-->|\*/\})"
)
REGISTER_MARKER = re.compile(
    r"(?:<!--|\{/\*)\s*clean-docs:policy\s+register-v2\s*(?:-->|\*/\})"
)

_TEMPLATE_PARTS = frozenset({"prompts", "prompt", "templates", "template"})
_EVIDENCE_NAME = re.compile(
    r"(?:^|[-_])(?:review|report|journal|findings|receipt|retro|postmortem|"
    r"evaluation|eval-results?|status|progress|handoff|dispatch|workorder|blocked|"
    r"changelog|changes?|news|release-notes?|history)(?:[-_.]|$)",
    re.IGNORECASE,
)
_PLAN_NAME = re.compile(r"(?:^|[-_])plan(?:[-_.]|$)", re.IGNORECASE)
_REFERENCE_NAME = re.compile(
    r"(reference|standard|spec|schema|surface|commands?|cli|api|configuration|"
    r"policy|contract)",
    re.IGNORECASE,
)
_TUTORIAL_NAME = re.compile(
    r"(tutorial|quickstart|quick-start|getting-started|walkthrough)",
    re.IGNORECASE,
)
_TROUBLESHOOTING_NAME = re.compile(
    r"(troubleshoot|debug|diagnos|fixing|recovery|runbook|incident)",
    re.IGNORECASE,
)
_SUPPORT_NAMES = frozenset({"operations.md", "support.md"})
_ARCHITECTURE_NAME = re.compile(
    r"(architecture|compromise|design|decision|adr|proposal|rfc)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DocumentProfile:
    path: str
    role: DocumentRole
    reason: str
    registered: bool

    def applies(self, rule: str) -> bool:
        return rule in ROLE_RULES[self.role]


def role_override_error(text: str) -> str | None:
    markers = ROLE_MARKER.findall(text)
    overrides = ROLE_OVERRIDE.findall(text)
    if not markers:
        return None
    if len(markers) != 1 or len(overrides) != 1:
        return "add exactly one complete clean-docs role marker"
    if overrides[0] not in ROLE_RULES:
        return f"unsupported clean-docs role: {overrides[0]}"
    return None


def frontmatter_error(text: str) -> str | None:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    if "---" not in lines[1:]:
        return "frontmatter opens at the document start but has no closing delimiter"
    return None


def _has_frontmatter(text: str) -> bool:
    lines = text.splitlines()
    return bool(lines and lines[0] == "---" and "---" in lines[1:])


def classify_document(relative: Path, text: str) -> DocumentProfile:
    """Classify a Markdown file by the job its current form performs."""
    normalized = relative.as_posix()
    parts = tuple(part.lower() for part in relative.parts)
    name = relative.name.lower()
    title = next(
        (
            line.lstrip("#").strip().lower()
            for line in text.splitlines()
            if line.startswith("#")
        ),
        "",
    )
    registered = REGISTER_PROFILE in text or REGISTER_MARKER.search(text) is not None
    if match := ROLE_OVERRIDE.search(text):
        requested = match.group(1)
        if requested in ROLE_RULES:
            role = cast(DocumentRole, requested)
            return DocumentProfile(
                normalized,
                role,
                "explicit clean-docs role marker",
                registered,
            )

    if (
        name in {"agents.md", "skill.md"}
        or parts[:1] == (".agents",)
        or "skills" in parts
        and _has_frontmatter(text)
    ):
        return DocumentProfile(
            normalized,
            "agent-procedure",
            "path or frontmatter identifies an executable agent procedure",
            registered,
        )
    if any(part in _TEMPLATE_PARTS for part in parts[:-1]):
        return DocumentProfile(
            normalized,
            "template",
            "path identifies prompt or generated-content input",
            registered,
        )
    if _EVIDENCE_NAME.search(relative.name) or any(
        part in {"reviews", "reports", "journals", "receipts", "evaluations"}
        for part in parts[:-1]
    ):
        return DocumentProfile(
            normalized,
            "evidence",
            "path identifies a review, result, or longitudinal record",
            registered,
        )
    if _PLAN_NAME.search(relative.name):
        return DocumentProfile(
            normalized,
            "plan",
            "filename identifies a time-scoped plan whose status needs judgment",
            registered,
        )
    if (
        name in _SUPPORT_NAMES
        or _TROUBLESHOOTING_NAME.search(normalized)
        or _TROUBLESHOOTING_NAME.search(title)
    ):
        return DocumentProfile(
            normalized,
            "troubleshooting",
            "path or title identifies diagnose-fix-verify work",
            registered,
        )
    if _TUTORIAL_NAME.search(normalized) or _TUTORIAL_NAME.search(title):
        return DocumentProfile(
            normalized,
            "tutorial",
            "path or title identifies an ordered learning path",
            registered,
        )
    if (
        "adr" in parts
        or _ARCHITECTURE_NAME.search(relative.name)
        or _ARCHITECTURE_NAME.search(title)
    ):
        return DocumentProfile(
            normalized,
            "architecture",
            "path or title identifies a design or decision record",
            registered,
        )
    if (
        "references" in parts
        or _REFERENCE_NAME.search(relative.name)
        or _REFERENCE_NAME.search(title)
    ):
        return DocumentProfile(
            normalized,
            "reference",
            "path or title identifies a lookup surface",
            registered,
        )
    if name in {"contributing.md", "contributor-guide.md"}:
        return DocumentProfile(
            normalized,
            "component-overview",
            "filename identifies a contributor entry point with several reader routes",
            registered,
        )
    if name == "readme.md":
        if len(relative.parts) > 1:
            return DocumentProfile(
                normalized,
                "component-overview",
                "nested README identifies a component-local entry point",
                registered,
            )
        return DocumentProfile(
            normalized,
            "overview",
            "README identifies a repository or component entry point",
            registered,
        )
    return DocumentProfile(
        normalized,
        "task",
        "default role for an authored how-to or explanatory page",
        registered,
    )
