from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clean_docs.corpus import scan_corpus
from clean_docs.residue import scan_residue
from clean_docs.standard import load_default_pack


PROCESS_NAME = re.compile(
    r"(?:^|[-_])(REPORT|HANDOFF|DISPATCH|BLOCKED|STATUS|PROGRESS|RECEIPT|FINDINGS|WORKORDER|NOTES|PLAN)(?:[-_.]|$)",
    re.IGNORECASE,
)
LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+[^)]*)?\)")
HEADING = re.compile(r"^#{2,}\s+(.+?)\s*$")
ALLOW = re.compile(
    r'<!--\s*clean-docs:allow\s+([a-z][a-z-]+)\s+reason="([^"]+)"\s*-->'
)


@dataclass(frozen=True)
class AuditFinding:
    rule: str
    path: str
    line: int
    detail: str


@dataclass(frozen=True)
class AuditReport:
    documents: tuple[str, ...]
    ignored_documents: tuple[str, ...]
    findings: tuple[AuditFinding, ...]


def _tracked_markdown(root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "*.md"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [
            relative
            for line in proc.stdout.splitlines()
            if line and (root / (relative := Path(line))).is_file()
        ]
    return sorted(path.relative_to(root) for path in root.rglob("*.md") if ".git" not in path.parts)


def _allowances(lines: list[str]) -> set[str]:
    allowed: set[str] = set()
    for line in lines:
        match = ALLOW.search(line)
        if match and len(match.group(2).strip()) >= 12:
            allowed.add(match.group(1))
    return allowed


def _section_ranges(lines: list[str]) -> list[tuple[str, int, int, set[str]]]:
    headings = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        if (match := HEADING.match(line))
    ]
    sections = []
    for position, (start, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        sections.append((title, start + 1, end - start, _allowances(lines[start:end])))
    return sections


def _local_link(target: str) -> bool:
    return not target.startswith(("#", "http://", "https://", "mailto:"))


def audit(root: Path) -> AuditReport:
    root = root.resolve()
    pack = load_default_pack()
    doc_limit = int(pack["policy"]["doc_max_lines"])
    section_limit = int(pack["policy"]["section_max_lines"])
    active: list[str] = []
    ignored: list[str] = []
    findings: list[AuditFinding] = []
    for relative in _tracked_markdown(root):
        normalized = relative.as_posix()
        if "archive" in relative.parts:
            ignored.append(normalized)
            continue
        active.append(normalized)
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(AuditFinding("unreadable-document", normalized, 1, str(exc)))
            continue
        lines = text.splitlines()
        allowances = _allowances(lines)
        if PROCESS_NAME.search(relative.name):
            findings.append(AuditFinding(
                "process-artifact",
                normalized,
                1,
                "move process history under an archive directory",
            ))
        if len(lines) > doc_limit and "doc-length" not in allowances:
            findings.append(AuditFinding(
                "doc-length",
                normalized,
                1,
                f"{len(lines)} lines exceeds {doc_limit}; split it or add a reasoned allowance",
            ))
        for title, section_line, count, section_allowances in _section_ranges(lines):
            if count > section_limit and "section-length" not in section_allowances:
                findings.append(AuditFinding(
                    "section-length",
                    normalized,
                    section_line,
                    f"{title!r} is {count} lines; split it or add a reasoned allowance",
                ))
        for line_number, document_line in enumerate(lines, start=1):
            for match in LINK.finditer(document_line):
                target = match.group(1).split("#", 1)[0].replace("%20", " ")
                if target and _local_link(target) and not (path.parent / target).exists():
                    findings.append(AuditFinding(
                        "broken-local-link",
                        normalized,
                        line_number,
                        f"target does not exist: {target}",
                    ))
    corpus_rule_names = {
        "surface": "process-artifact",
        "audience": "audience",
        "provenance": "provenance",
        "near-dup": "near-duplicate",
        "restatement": "restatement",
    }
    for corpus_finding in scan_corpus(root, include_lengths=False):
        rule = corpus_rule_names.get(corpus_finding.rule)
        if rule is None:
            continue
        try:
            text = (root / corpus_finding.doc).read_text(encoding="utf-8")
        except OSError:
            continue
        if rule in _allowances(text.splitlines()):
            continue
        candidate = AuditFinding(
            rule,
            corpus_finding.doc,
            corpus_finding.line,
            corpus_finding.detail,
        )
        if not any(
            existing.rule == candidate.rule
            and existing.path == candidate.path
            and existing.line == candidate.line
            for existing in findings
        ):
            findings.append(candidate)
    for residue_finding in scan_residue(root):
        findings.append(AuditFinding(
            residue_finding.rule,
            residue_finding.doc,
            residue_finding.line,
            residue_finding.detail,
        ))
    findings.sort(key=lambda item: (item.path, item.line, item.rule))
    return AuditReport(tuple(active), tuple(ignored), tuple(findings))
