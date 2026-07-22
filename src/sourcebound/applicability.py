from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from sourcebound.corpus import _markdown_control_text
from sourcebound.policy import REGISTER_PROFILE


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
        "code-block-language",
        "diagram-text-equivalent",
        "image-alternative",
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
        "code-block-language",
        "diagram-text-equivalent",
        "image-alternative",
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
    }),
    "tutorial": frozenset({
        "code-block-language",
        "diagram-text-equivalent",
        "image-alternative",
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
        "code-block-language",
        "diagram-text-equivalent",
        "image-alternative",
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
        "code-block-language",
        "diagram-text-equivalent",
        "image-alternative",
        "purpose-contract",
        "purpose-template",
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
    }),
    "architecture": frozenset({
        "code-block-language",
        "diagram-text-equivalent",
        "image-alternative",
        "prohibited-booster",
        "sentence-variance",
        "nominalization-density",
        "significance-narration",
    }),
    "reference": frozenset({
        "code-block-language",
        "diagram-text-equivalent",
        "image-alternative",
        "prohibited-booster",
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
    r"(?:<!--|\{/\*)\s*sourcebound:role\s+([a-z][a-z-]+)\s*(?:-->|\*/\})"
)
ROLE_MARKER = re.compile(
    r"(?:<!--|\{/\*)\s*sourcebound:role\b.*?(?:-->|\*/\})"
)
REGISTER_MARKER = re.compile(
    r"(?:<!--|\{/\*)\s*sourcebound:policy\s+register-v2\s*(?:-->|\*/\})"
)

_TEMPLATE_PARTS = frozenset({"prompts", "prompt", "templates", "template"})
_EVIDENCE_NAME = re.compile(
    r"(?:^|[-_])(?:audit|report|journal|findings|receipt|retro|postmortem|"
    r"eval-results?|status|progress|handoff|dispatch|workorder|blocked|"
    r"changelog|changes?|news|release-notes?|history)(?:[-_.]|$)",
    re.IGNORECASE,
)
_PLAN_NAME = re.compile(r"(?:^|[-_])plan(?:[-_.]|$)", re.IGNORECASE)
_REFERENCE_NAME = re.compile(
    r"(?:^|[-_ ])(?:references?|standards?|specs?|schemas?|surfaces?|commands?|"
    r"clis?|apis?|configurations?|ledgers?|polic(?:y|ies)|contracts?)(?:[-_. ]|$)",
    re.IGNORECASE,
)
_TUTORIAL_NAME = re.compile(
    r"(tutorial|quickstart|quick-start|getting-started|walkthrough)",
    re.IGNORECASE,
)
_TROUBLESHOOTING_NAME = re.compile(
    r"(troubleshoot|debug|diagnos|fixing|recover(?:ing)?\b|runbook|incident)",
    re.IGNORECASE,
)
_TROUBLESHOOTING_NAMES = frozenset({"operations.md", "recovery.md", "support.md"})
_ARCHITECTURE_NAME = re.compile(
    r"(?:^|[-_ ])(?:architecture|compromises?|designs?|decisions?|adrs?|proposals?|rfcs?)"
    r"(?:[-_. ]|$)",
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
    control_text = _markdown_control_text(text)
    markers = ROLE_MARKER.findall(control_text)
    overrides = ROLE_OVERRIDE.findall(control_text)
    if not markers:
        return None
    if len(markers) != 1 or len(overrides) != 1:
        return "add exactly one complete sourcebound role marker"
    if overrides[0] not in ROLE_RULES:
        return f"unsupported sourcebound role: {overrides[0]}"
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
    control_text = _markdown_control_text(text)
    normalized = relative.as_posix()
    parts = tuple(part.lower() for part in relative.parts)
    name = relative.name.lower()
    title = next(
        (
            line.lstrip("#").strip().lower()
            for line in control_text.splitlines()
            if line.startswith("#")
        ),
        "",
    )
    registered = (
        REGISTER_PROFILE in control_text
        or REGISTER_MARKER.search(control_text) is not None
    )
    if match := ROLE_OVERRIDE.search(control_text):
        requested = match.group(1)
        if requested in ROLE_RULES:
            role = cast(DocumentRole, requested)
            return DocumentProfile(
                normalized,
                role,
                "explicit sourcebound role marker",
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
    if any(
        part in {"evidence", "reviews", "reports", "journals", "receipts", "evaluations"}
        for part in parts[:-1]
    ):
        return DocumentProfile(
            normalized,
            "evidence",
            "parent directory identifies a review, result, or longitudinal record",
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
        name in _TROUBLESHOOTING_NAMES
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
        any(part in {"adr", "adrs", "decision", "decisions"} for part in parts)
        or _ARCHITECTURE_NAME.search(relative.name)
    ):
        return DocumentProfile(
            normalized,
            "architecture",
            "path or filename identifies a design or decision record",
            registered,
        )
    if (
        any(
            part in {
                "api",
                "apis",
                "contract",
                "contracts",
                "policies",
                "policy",
                "reference",
                "references",
                "schema",
                "schemas",
                "spec",
                "specs",
                "standard",
                "standards",
            }
            for part in parts[:-1]
        )
        or _REFERENCE_NAME.search(relative.name)
    ):
        return DocumentProfile(
            normalized,
            "reference",
            "path or filename identifies a lookup surface",
            registered,
        )
    if name in {"index.md", "readme.md"} and len(relative.parts) > 1:
        return DocumentProfile(
            normalized,
            "component-overview",
            "nested index identifies a component-local entry point",
            registered,
        )
    if any(part in {"guide", "guides", "help", "how-to", "howtos", "tasks"} for part in parts[:-1]):
        return DocumentProfile(
            normalized,
            "task",
            "path identifies an authored help or task page",
            registered,
        )
    if _ARCHITECTURE_NAME.search(title):
        return DocumentProfile(
            normalized,
            "architecture",
            "title identifies a design or decision record",
            registered,
        )
    if _EVIDENCE_NAME.search(relative.name):
        return DocumentProfile(
            normalized,
            "evidence",
            "filename identifies a review, result, or longitudinal record",
            registered,
        )
    if (
        _REFERENCE_NAME.search(title)
    ):
        return DocumentProfile(
            normalized,
            "reference",
            "title identifies a lookup surface",
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
