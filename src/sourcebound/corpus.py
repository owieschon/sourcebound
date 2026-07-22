from __future__ import annotations

import os
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from collections.abc import Mapping
from pathlib import Path

from sourcebound.mdx import MdxParserError, parse_mdx
from sourcebound.policy import PolicyFinding


DOC_MAX_LINES = 120
SECTION_MAX_LINES = 40
MIN_PARA_TOKENS = 8
NEAR_DUP = 0.80
RESTATEMENT = 0.60
POSTINGS_CAP = 200

PROCESS_RE = re.compile(
    r"(REPORT|HANDOFF|(?:NEXT|RESEARCH)[_-]DISPATCH|BLOCKED|STATUS|PROGRESS|FINDINGS"
    r"|WEEK\d|WAVE\d|EXECUTION_PLAN|EXECUTOR|RETRO|_AUDIT)",
    re.IGNORECASE,
)
TOP_LEVEL_PROCESS_NAMES = frozenset({"dispatch.md"})
CHANGELOG_RE = re.compile(r"(CHANGELOG|DECISION_LOG|PROGRAM_REPORT|RETRO)", re.IGNORECASE)
HARNESS_RE = re.compile(
    r"\b(next executor|pick up this branch|worktree|STOP condition|tripwire"
    r"|do not edit|mid-edit|reconciles exactly|diff budget|skeptical reviewer"
    r"|origin/main|git log|killed PID|baseline SHA|DoD table)\b",
    re.IGNORECASE,
)
PROVENANCE_RE = re.compile(
    r"(\((?:Program|Wave|Harvest|Dispatch|WS-[A-Za-z]+)\s*\d*\)"
    r"|verified after authoring|\$\d+\.\d{6})"
)
PREDECESSOR_MARKER_RE = re.compile(
    r"(?:<!--[ \t]*clean[-_]docs:[^\n]*?-->"
    r"|\{/\*[ \t]*clean[-_]docs:[^\n]*?\*/\})",
    re.IGNORECASE,
)
HARNESS_HITS = 3
STOPWORDS = frozenset(
    "the a an and or but of to in on at for with without from into is are was were be been "
    "being it its this that these those as by not no also than then so such can may must will "
    "which when where what who how why each any all one two per via if do does done only same "
    "here there they them their you your we our us".split()
)
WORD_RE = re.compile(r"[a-z][a-z0-9-]{2,}")
FENCE_RE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<rest>.*)$")
LIST_ITEM_RE = re.compile(r"^(?P<indent> {0,3})(?:[-+*]|\d+[.)])(?P<space>[ \t]+)")
BLOCKQUOTE_RE = re.compile(r"^ {0,3}>[ \t]?")
HTML_COMMENT_RE = re.compile(r"^\s*<!--.*?-->\s*$")
FALLBACK_SKIP_PARTS = frozenset({
    ".git",
    ".nox",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
})


def _is_process_artifact(relative: str, name: str, text: str) -> bool:
    if PROCESS_RE.search(name):
        return True
    return (
        len(Path(relative).parts) == 1
        and name.casefold() in TOP_LEVEL_PROCESS_NAMES
        and HARNESS_RE.search(text) is not None
    )


def _active_predecessor_markers(text: str) -> Iterable[tuple[int, re.Match[str]]]:
    """Yield predecessor markers that Markdown or MDX treats as active comments."""
    visible_text = _markdown_control_text(text)
    for line_number, visible in enumerate(visible_text.splitlines(), start=1):
        for marker in PREDECESSOR_MARKER_RE.finditer(visible):
            yield line_number, marker


def _markdown_control_text(text: str, *, mask_inline_code: bool = True) -> str:
    """Mask supported Markdown examples while retaining active comments and prose."""
    fence_char: str | None = None
    fence_length = 0
    fence_quote_depth = 0
    fence_list_indent: int | None = None
    list_content_indent: int | None = None
    visible_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        (
            container_line,
            quote_depth,
            next_list_indent,
            list_item,
            continued_list,
        ) = _markdown_container_view(
            line,
            list_content_indent,
            allow_new_list=fence_char is None,
        )
        if fence_char is not None and line.strip() and (
            quote_depth < fence_quote_depth
            or (fence_list_indent is not None and not continued_list)
        ):
            fence_char = None
            fence_length = 0
            fence_quote_depth = 0
            fence_list_indent = None
            list_content_indent = None
            (
                container_line,
                quote_depth,
                next_list_indent,
                list_item,
                continued_list,
            ) = _markdown_container_view(
                line,
                None,
                allow_new_list=True,
            )
        if fence_char is None:
            list_content_indent = next_list_indent
        fence = FENCE_RE.match(container_line)
        if fence:
            marker = fence.group("marker")
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
                fence_quote_depth = quote_depth
                fence_list_indent = list_content_indent
            elif (
                marker[0] == fence_char
                and len(marker) >= fence_length
                and not fence.group("rest").strip()
                and quote_depth == fence_quote_depth
                and (
                    fence_list_indent is None
                    or continued_list
                )
            ):
                fence_char = None
                fence_length = 0
                fence_quote_depth = 0
                fence_list_indent = None
            visible_lines.append(_blank_preserving_newlines(line))
            continue
        if fence_char is not None:
            visible_lines.append(_blank_preserving_newlines(line))
            continue
        if list_item:
            visible_lines.append(line)
            continue
        indent = _markdown_indent(container_line)
        if container_line.strip() and not continued_list:
            list_content_indent = None
        if indent >= 4:
            visible_lines.append(_blank_preserving_newlines(line))
            continue
        visible_lines.append(line)
    visible = "".join(visible_lines)
    return _without_inline_code(visible) if mask_inline_code else visible


def _markdown_container_view(
    line: str,
    active_list_indent: int | None,
    *,
    allow_new_list: bool,
) -> tuple[str, int, int | None, bool, bool]:
    """Strip supported blockquote/list containers in either nesting order."""
    content = line
    quote_depth = 0
    list_indent = active_list_indent
    list_item = False
    continued_list = False
    while True:
        if (
            active_list_indent is not None
            and not continued_list
            and _markdown_indent(content) >= active_list_indent
        ):
            content = _strip_markdown_indent(content, active_list_indent)
            continued_list = True
            continue
        blockquote = BLOCKQUOTE_RE.match(content)
        if blockquote is not None:
            content = content[blockquote.end():]
            quote_depth += 1
            continue
        candidate = LIST_ITEM_RE.match(content) if allow_new_list else None
        if candidate is not None:
            prefix_width = _markdown_width(candidate.group(0))
            list_indent = (
                (active_list_indent if continued_list and active_list_indent else 0)
                + prefix_width
            )
            list_item = True
            content = content[candidate.end():]
            continue
        break
    return content, quote_depth, list_indent, list_item, continued_list


def _strip_markdown_indent(line: str, columns: int) -> str:
    """Remove up to ``columns`` leading Markdown indentation columns."""
    index = 0
    consumed = 0
    while index < len(line) and consumed < columns:
        character = line[index]
        if character == " ":
            consumed += 1
        elif character == "\t":
            consumed += 4 - (consumed % 4)
        else:
            break
        index += 1
    return line[index:]


def _blank_preserving_newlines(text: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in text)


def _markdown_indent(line: str) -> int:
    """Return leading Markdown indentation in columns, including tab stops."""
    columns = 0
    for character in line:
        if character == " ":
            columns += 1
        elif character == "\t":
            columns += 4 - (columns % 4)
        else:
            break
    return columns


def _markdown_width(text: str) -> int:
    """Return the display columns occupied by a Markdown container prefix."""
    columns = 0
    for character in text:
        if character == "\t":
            columns += 4 - (columns % 4)
        else:
            columns += 1
    return columns


def _without_inline_code(line: str) -> str:
    """Mask matched Markdown code spans in linear time while preserving lines."""
    runs: list[tuple[int, int, int]] = []
    index = 0
    backslash_run = 0
    while index < len(line):
        if line[index] == "\\":
            backslash_run += 1
            index += 1
            continue
        if line[index] != "`" or backslash_run % 2 == 1:
            backslash_run = 0
            index += 1
            continue
        start = index
        while index < len(line) and line[index] == "`":
            index += 1
        runs.append((start, index, index - start))
        backslash_run = 0

    next_same: list[int | None] = [None] * len(runs)
    next_by_length: dict[int, int] = {}
    for run_index in range(len(runs) - 1, -1, -1):
        length = runs[run_index][2]
        next_same[run_index] = next_by_length.get(length)
        next_by_length[length] = run_index

    visible = list(line)
    run_index = 0
    while run_index < len(runs):
        close_index = next_same[run_index]
        if close_index is None:
            run_index += 1
            continue
        for position in range(runs[run_index][0], runs[close_index][1]):
            if visible[position] != "\n":
                visible[position] = " "
        run_index = close_index + 1
    return "".join(visible)


def _is_document_candidate(relative: Path, *, fallback: bool) -> bool:
    """Return whether a Markdown path can belong to the reader-facing corpus."""
    parts = relative.parts
    packaged_standard = any(
        parts[index:index + 2] == ("sourcebound", "standards")
        for index in range(len(parts) - 1)
    )
    return not (
        parts[:2] == ("tests", "fixtures")
        or packaged_standard
        or ".fixture." in relative.name.lower()
        or (fallback and bool(set(parts) & FALLBACK_SKIP_PARTS))
    )


def _git_visible_markdown(root: Path) -> list[Path] | None:
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
                "--",
                "*.md",
                "*.mdx",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0:
        return None
    candidates = sorted(
        {
            root / line
            for line in proc.stdout.splitlines()
            if line.strip() and (root / line).is_file()
        },
        key=lambda path: (path.is_symlink(), path.as_posix()),
    )
    canonical: dict[Path, Path] = {}
    for path in candidates:
        try:
            identity = path.resolve(strict=True)
        except OSError:
            identity = path.absolute()
        canonical.setdefault(identity, path)
    return sorted(canonical.values())


def _hidden_document(relative: Path) -> bool:
    hidden = [part for part in relative.parts if part.startswith(".")]
    return bool(hidden) and relative.parts[0] != ".agents"


def list_documents(root: Path) -> list[Path]:
    """Return the reader-facing Markdown surface used by the Version 0 linter."""
    if root.is_file():
        return [root]
    visible = _git_visible_markdown(root)
    if visible is not None:
        return [
            path
            for path in visible
            if "archive" not in path.relative_to(root).parts
            and _is_document_candidate(path.relative_to(root), fallback=False)
            and not _hidden_document(path.relative_to(root))
        ]
    return sorted(
        path
        for pattern in ("*.md", "*.mdx")
        for path in root.rglob(pattern)
        if _is_document_candidate(path.relative_to(root), fallback=True)
        and "archive" not in path.relative_to(root).parts
        and ".sourcebound" not in path.relative_to(root).parts
        and not _hidden_document(path.relative_to(root))
    )


def _read(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if path.suffix.lower() == ".mdx":
        try:
            return parse_mdx(text).policy_text(text)
        except MdxParserError:
            return ""
    return text


def _content_tokens(text: str) -> frozenset[str]:
    return frozenset(word for word in WORD_RE.findall(text.lower()) if word not in STOPWORDS)


def _paragraphs(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    buffer: list[str] = []
    in_fence = False
    start = 1
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not raw.strip():
            if buffer:
                result.append((start, " ".join(buffer)))
                buffer = []
            continue
        if HTML_COMMENT_RE.match(raw):
            if buffer:
                result.append((start, " ".join(buffer)))
                buffer = []
            continue
        if not buffer:
            start = line_number
        stripped = raw.lstrip()
        if stripped.startswith(("#", "|", ">")):
            if buffer:
                result.append((start, " ".join(buffer)))
                buffer = []
            continue
        buffer.append(stripped)
    if buffer:
        result.append((start, " ".join(buffer)))
    return result


def _sections(text: str) -> list[tuple[str, int, int]]:
    lines = text.splitlines()
    headings = [
        (index + 1, line)
        for index, line in enumerate(lines)
        if re.match(r"^#{2,} ", line)
    ]
    result = []
    for position, (line_number, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines) + 1
        result.append((title.strip("# ").strip(), line_number, end - line_number))
    return result


def _duplicate_findings(
    paragraphs: list[tuple[str, int, frozenset[str], str]],
    index: dict[str, list[int]],
) -> list[PolicyFinding]:
    seen_pairs: set[tuple[int, int]] = set()
    findings = []
    for postings in index.values():
        if len(postings) > POSTINGS_CAP or len(postings) < 2:
            continue
        for left_position, left_id in enumerate(postings):
            for right_id in postings[left_position + 1:]:
                pair = (left_id, right_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                left_tokens = paragraphs[left_id][2]
                right_tokens = paragraphs[right_id][2]
                intersection = len(left_tokens & right_tokens)
                if intersection < 4:
                    continue
                overlap = intersection / len(left_tokens | right_tokens)
                if overlap < RESTATEMENT:
                    continue
                left = paragraphs[left_id]
                right = paragraphs[right_id]
                same_document = left[0] == right[0]
                rule = "near-dup" if overlap >= NEAR_DUP or not same_document else "restatement"
                location = f"{right[0]}:{right[1]}"
                detail = f"~{overlap:.0%} overlap with {location}"
                if not same_document:
                    detail += " (different doc -- pick one canonical home)"
                findings.append(PolicyFinding(left[0], left[1], rule, detail))
    return findings


def scan_corpus(
    root: Path,
    *,
    include_lengths: bool = True,
    prepared_documents: Mapping[str, str] | None = None,
) -> list[PolicyFinding]:
    """Run the tuned Version 0 corpus rules with stable finding identifiers."""
    root = root.resolve()
    base = root if root.is_dir() else root.parent
    findings: list[PolicyFinding] = []
    paragraph_index: dict[str, list[int]] = {}
    paragraphs: list[tuple[str, int, frozenset[str], str]] = []

    document_rows = (
        (
            os.path.relpath(path, base),
            path.name,
            _read(path),
        )
        for path in list_documents(root)
    ) if prepared_documents is None else (
        (relative, Path(relative).name, text)
        for relative, text in sorted(prepared_documents.items())
    )
    for relative, name, text in document_rows:
        for line_number, _marker in _active_predecessor_markers(text):
            findings.append(PolicyFinding(
                relative,
                line_number,
                "predecessor-marker",
                "predecessor policy marker is ignored; migrate it to a sourcebound marker",
            ))
        process_artifact = _is_process_artifact(relative, name, text)
        if process_artifact:
            findings.append(PolicyFinding(
                relative,
                1,
                "surface",
                "process-artifact name on the reader-facing doc surface",
            ))
        if not CHANGELOG_RE.search(name):
            harness_hits = len(HARNESS_RE.findall(text))
            if harness_hits >= HARNESS_HITS:
                findings.append(PolicyFinding(
                    relative,
                    1,
                    "audience",
                    f"{harness_hits} harness/agent-address terms -- audience reads as an agent",
                ))
            provenance = PROVENANCE_RE.findall(text)
            if provenance:
                match = PROVENANCE_RE.search(text)
                assert match is not None
                line = text.count("\n", 0, match.start()) + 1
                findings.append(PolicyFinding(
                    relative,
                    line,
                    "provenance",
                    f"{len(provenance)} provenance/receipt marks in a reference doc "
                    f"(e.g. {match.group(0)!r})",
                ))
        if include_lengths:
            line_count = text.count("\n") + 1
            if line_count > DOC_MAX_LINES and not process_artifact:
                findings.append(PolicyFinding(
                    relative,
                    1,
                    "doc-length",
                    f"{line_count} lines (> {DOC_MAX_LINES}) -- justify one file or split",
                ))
            for title, line_number, count in _sections(text):
                if count > SECTION_MAX_LINES:
                    findings.append(PolicyFinding(
                        relative,
                        line_number,
                        "section-length",
                        f"section {title!r} is {count} lines (> {SECTION_MAX_LINES})",
                    ))
        for start, paragraph in _paragraphs(text):
            tokens = _content_tokens(paragraph)
            if len(tokens) < MIN_PARA_TOKENS:
                continue
            paragraph_id = len(paragraphs)
            paragraphs.append((relative, start, tokens, paragraph))
            for token in tokens:
                paragraph_index.setdefault(token, []).append(paragraph_id)

    findings.extend(_duplicate_findings(paragraphs, paragraph_index))
    order = {
        "predecessor-marker": 0,
        "surface": 1,
        "audience": 2,
        "provenance": 3,
        "near-dup": 4,
        "doc-length": 5,
        "section-length": 6,
        "restatement": 7,
    }
    findings.sort(key=lambda finding: (
        order.get(finding.rule, 9), finding.doc, finding.line
    ))
    return findings


def findings_as_json(findings: Iterable[PolicyFinding]) -> list[dict[str, object]]:
    return [
        {
            "check": finding.rule,
            "file": finding.doc,
            "line": finding.line,
            "detail": finding.detail,
        }
        for finding in findings
    ]


def main(argv: list[str] | None = None) -> int:
    """Run the Version 0 command-line contract through the packaged engine."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in arguments
    positional = [argument for argument in arguments if argument != "--json"]
    root = Path(positional[0] if positional else os.getcwd()).resolve()
    findings = scan_corpus(root)
    if as_json:
        print(json.dumps(findings_as_json(findings), indent=2))
        return 1 if findings else 0
    if not findings:
        print(f"doc-hygiene: clean ({root})")
        return 0
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.rule] = counts.get(finding.rule, 0) + 1
    print(f"doc-hygiene: {len(findings)} finding(s) in {root}")
    print("  " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print()
    for finding in findings:
        print(f"  [{finding.rule}] {finding.doc}:{finding.line}  {finding.detail}")
    return 1
