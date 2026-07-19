from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from clean_docs.policy import PolicyFinding


FENCE = re.compile(r"^\s{0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
MARKDOWN_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\([^)]+\)")
HTML_IMAGE = re.compile(r"<img\b(?P<attributes>[^>]*)>", re.IGNORECASE | re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
MDX_COMMENT = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
INLINE_CODE = re.compile(r"(?P<fence>`+)[^\n]*?(?P=fence)")
ALT_ATTRIBUTE = re.compile(
    r"\balt\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)')",
    re.IGNORECASE,
)
PRESENTATION_ROLE = re.compile(
    r"\brole\s*=\s*(?:\"presentation\"|'presentation')",
    re.IGNORECASE,
)
DECORATIVE_MARKERS = {
    "<!-- clean-docs:decorative-image -->",
    "{/* clean-docs:decorative-image */}",
}
DIAGRAM_PREFIX = re.compile(r"^Diagram(?: description)?:\s+\S", re.IGNORECASE)


@dataclass(frozen=True)
class FenceBlock:
    line: int
    end_line: int
    language: str


def _fences(text: str) -> tuple[FenceBlock, ...]:
    lines = text.splitlines()
    blocks: list[FenceBlock] = []
    open_marker: tuple[str, int, int, str] | None = None
    for line_number, line in enumerate(lines, start=1):
        match = FENCE.match(line)
        if match is None:
            continue
        marker = match.group("marker")
        if open_marker is None:
            info = match.group("info").strip()
            language = info.split(maxsplit=1)[0] if info else ""
            open_marker = (marker[0], len(marker), line_number, language)
            continue
        character, width, start_line, language = open_marker
        if (
            marker[0] == character
            and len(marker) >= width
            and not match.group("info").strip()
        ):
            blocks.append(FenceBlock(start_line, line_number, language))
            open_marker = None
    return tuple(blocks)


def _previous_content(lines: list[str], line_number: int) -> str:
    for line in reversed(lines[: line_number - 1]):
        if line.strip():
            return line.strip()
    return ""


def _next_content(lines: list[str], line_number: int) -> tuple[int, str] | None:
    for index, line in enumerate(lines[line_number:], start=line_number + 1):
        stripped = line.strip()
        if stripped:
            return index, stripped
    return None


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _blank(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


def _visible_source(text: str, blocks: tuple[FenceBlock, ...]) -> str:
    lines = text.splitlines(keepends=True)
    fenced_lines = {
        line_number
        for block in blocks
        for line_number in range(block.line, block.end_line + 1)
    }
    visible = "".join(
        _blank(line) if line_number in fenced_lines else line
        for line_number, line in enumerate(lines, start=1)
    )
    visible = HTML_COMMENT.sub(lambda match: _blank(match.group(0)), visible)
    visible = MDX_COMMENT.sub(lambda match: _blank(match.group(0)), visible)
    return INLINE_CODE.sub(lambda match: _blank(match.group(0)), visible)


def check_accessibility(
    doc: str,
    text: str,
    pack: dict[str, Any],
) -> list[PolicyFinding]:
    from clean_docs.policy import PolicyFinding

    checks = tuple(str(check) for check in pack["checklist"])
    lines = text.splitlines()
    findings: list[PolicyFinding] = []
    blocks = _fences(text)
    visible_source = _visible_source(text, blocks)

    if any("Every fenced code block declares its language" in check for check in checks):
        findings.extend(
            PolicyFinding(
                doc,
                block.line,
                "code-block-language",
                "add a language label; use text for literal output or prompts",
            )
            for block in blocks
            if not block.language
        )

    if any(
        "Every Mermaid diagram has an adjacent text equivalent" in check
        for check in checks
    ):
        for block in blocks:
            if block.language.lower() != "mermaid":
                continue
            following = _next_content(lines, block.end_line)
            if following is None or not DIAGRAM_PREFIX.match(following[1]):
                findings.append(PolicyFinding(
                    doc,
                    block.line,
                    "diagram-text-equivalent",
                    "add an adjacent 'Diagram:' description after the Mermaid block",
                ))

    if any("Every image has useful alternative text" in check for check in checks):
        for line_number, line in enumerate(visible_source.splitlines(), start=1):
            for match in MARKDOWN_IMAGE.finditer(line):
                if match.group("alt").strip():
                    continue
                if _previous_content(lines, line_number) in DECORATIVE_MARKERS:
                    continue
                findings.append(PolicyFinding(
                    doc,
                    line_number,
                    "image-alternative",
                    "write useful alt text or precede a decorative image with "
                    "'<!-- clean-docs:decorative-image -->'",
                ))
        for match in HTML_IMAGE.finditer(visible_source):
            line_number = _line_number(visible_source, match.start())
            attributes = match.group("attributes")
            alt = ALT_ATTRIBUTE.search(attributes)
            if alt is None:
                findings.append(PolicyFinding(
                    doc,
                    line_number,
                    "image-alternative",
                    "add an alt attribute; use alt=\"\" and role=\"presentation\" "
                    "for a decorative image",
                ))
                continue
            value = alt.group("double")
            if value is None:
                value = alt.group("single")
            if not value and PRESENTATION_ROLE.search(attributes) is None:
                findings.append(PolicyFinding(
                    doc,
                    line_number,
                    "image-alternative",
                    "pair an empty alt attribute with role=\"presentation\" or "
                    "write useful alt text",
                ))
    return findings
