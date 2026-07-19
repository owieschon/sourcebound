from __future__ import annotations

import os
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from collections.abc import Mapping
from pathlib import Path

from clean_docs.mdx import MdxParserError, parse_mdx
from clean_docs.policy import PolicyFinding


DOC_MAX_LINES = 120
SECTION_MAX_LINES = 40
MIN_PARA_TOKENS = 8
NEAR_DUP = 0.80
RESTATEMENT = 0.60
POSTINGS_CAP = 200

PROCESS_RE = re.compile(
    r"(REPORT|HANDOFF|DISPATCH|BLOCKED|STATUS|PROGRESS|RECEIPT|FINDINGS"
    r"|WEEK\d|WAVE\d|EXECUTION_PLAN|EXECUTOR|RETRO|_AUDIT)",
    re.IGNORECASE,
)
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
HARNESS_HITS = 3
STOPWORDS = frozenset(
    "the a an and or but of to in on at for with without from into is are was were be been "
    "being it its this that these those as by not no also than then so such can may must will "
    "which when where what who how why each any all one two per via if do does done only same "
    "here there they them their you your we our us".split()
)
WORD_RE = re.compile(r"[a-z][a-z0-9-]{2,}")
FENCE_RE = re.compile(r"^```")
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


def _is_document_candidate(relative: Path, *, fallback: bool) -> bool:
    """Return whether a Markdown path can belong to the reader-facing corpus."""
    parts = relative.parts
    packaged_standard = any(
        parts[index:index + 2] == ("clean_docs", "standards")
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
        and ".clean-docs" not in path.relative_to(root).parts
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
        if PROCESS_RE.search(name):
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
            if line_count > DOC_MAX_LINES and not PROCESS_RE.search(name):
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
        "surface": 0,
        "audience": 1,
        "provenance": 2,
        "near-dup": 3,
        "doc-length": 4,
        "section-length": 5,
        "restatement": 6,
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
