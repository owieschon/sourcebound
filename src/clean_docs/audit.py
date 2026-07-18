from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from clean_docs.corpus import scan_corpus
from clean_docs.errors import ConfigurationError
from clean_docs.policy import REGISTER_PROFILE, check_document
from clean_docs.regions import atomic_write
from clean_docs.residue import scan_residue
from clean_docs.standard import load_default_pack


PROCESS_NAME = re.compile(
    r"(?:^|[-_])(REPORT|HANDOFF|DISPATCH|BLOCKED|STATUS|PROGRESS|RECEIPT|FINDINGS|WORKORDER)(?:[-_.]|$)",
    re.IGNORECASE,
)
LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+[^)]*)?\)")
HEADING = re.compile(r"^#{2,}\s+(.+?)\s*$")
ALLOW = re.compile(
    r'<!--\s*clean-docs:allow\s+([a-z][a-z-]+)\s+reason="([^"]+)"\s*-->'
)
AUDIT_BASELINE_SCHEMA = "clean-docs.audit-baseline.v1"
AUDIT_BASELINE_PATH = Path(".clean-docs/audit-baseline.json")


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
    baselined_findings: tuple[AuditFinding, ...] = ()
    stale_baseline: tuple[AuditFinding, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.findings and not self.stale_baseline


def finding_fingerprint(finding: AuditFinding) -> str:
    payload = json.dumps(
        {
            "detail": finding.detail,
            "line": finding.line,
            "path": finding.path,
            "rule": finding.rule,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _finding_order(finding: AuditFinding) -> tuple[str, int, str, str]:
    return (finding.path, finding.line, finding.rule, finding.detail)


def render_audit_baseline(findings: tuple[AuditFinding, ...]) -> str:
    entries = []
    for finding in findings:
        entries.append({
            "fingerprint": finding_fingerprint(finding),
            "rule": finding.rule,
            "path": finding.path,
            "line": finding.line,
            "detail": finding.detail,
        })
    return json.dumps(
        {"schema": AUDIT_BASELINE_SCHEMA, "findings": entries},
        indent=2,
    ) + "\n"


def _load_audit_baseline(path: Path) -> tuple[AuditFinding, ...]:
    if path.is_symlink():
        raise ConfigurationError(f"audit baseline cannot be a symbolic link: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read audit baseline {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != AUDIT_BASELINE_SCHEMA:
        raise ConfigurationError(f"audit baseline has an unsupported schema: {path}")
    entries = raw.get("findings")
    if not isinstance(entries, list):
        raise ConfigurationError(f"audit baseline findings must be a list: {path}")
    findings: list[AuditFinding] = []
    fingerprints: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConfigurationError(f"audit baseline finding {index} must be an object")
        expected_keys = {"fingerprint", "rule", "path", "line", "detail"}
        if set(entry) != expected_keys:
            raise ConfigurationError(
                f"audit baseline finding {index} must contain exactly "
                "fingerprint, rule, path, line, and detail"
            )
        if not all(
            isinstance(entry[key], str)
            for key in ("fingerprint", "rule", "path", "detail")
        ):
            raise ConfigurationError(f"audit baseline finding {index} has an invalid string field")
        if not isinstance(entry["line"], int) or isinstance(entry["line"], bool) or entry["line"] < 1:
            raise ConfigurationError(f"audit baseline finding {index} has an invalid line")
        finding = AuditFinding(entry["rule"], entry["path"], entry["line"], entry["detail"])
        fingerprint = finding_fingerprint(finding)
        if entry["fingerprint"] != fingerprint:
            raise ConfigurationError(f"audit baseline finding {index} fingerprint does not match")
        if fingerprint in fingerprints:
            raise ConfigurationError(f"audit baseline has duplicate finding {fingerprint}")
        fingerprints.add(fingerprint)
        findings.append(finding)
    findings.sort(key=_finding_order)
    return tuple(findings)


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
            if line
            and (root / (relative := Path(line))).is_file()
            and relative.parts[:2] != ("tests", "fixtures")
            and relative.parts[:3] != ("src", "clean_docs", "standards")
            and ".fixture." not in relative.name.lower()
        ]
    return sorted(
        path.relative_to(root)
        for path in root.rglob("*.md")
        if ".git" not in path.parts
        and path.parts[-4:-1] != ("src", "clean_docs", "standards")
        and ".fixture." not in path.name.lower()
    )


def _allowances(lines: list[str]) -> set[str]:
    allowed: set[str] = set()
    for line in lines:
        match = ALLOW.search(line)
        if match and len(match.group(2).strip()) >= 12:
            allowed.add(match.group(1))
    return allowed


def _allowance_records(lines: list[str]) -> list[tuple[int, str, str]]:
    records: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(lines, start=1):
        if match := ALLOW.search(line):
            records.append((line_number, match.group(1), match.group(2).strip()))
    return records


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


def _outside_fences(lines: list[str]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    in_fence = False
    for line_number, line in enumerate(lines, start=1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append((line_number, line))
    return result


def _page_type(relative: Path, text: str) -> str:
    name = relative.name.upper()
    if relative.name == "README.md":
        return "readme"
    if (
        "REFERENCE" in name
        or name in {
            "STANDARD.MD",
            "CLEAN_DOCS_SPEC.MD",
            "DECISION_LOG.MD",
            "CLI.MD",
            "RELEASES.MD",
            "SURFACE.MD",
        }
        or text.lstrip().lower().startswith("# reference")
    ):
        return "reference"
    return "guide"


def _section_depth_findings(
    normalized: str,
    lines: list[str],
    *,
    require_routes: bool,
    require_depth_links: bool,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    text = "\n".join(lines)
    if REGISTER_PROFILE not in text:
        return findings
    allowances = _allowances(lines)
    if (
        require_routes
        and normalized == "README.md"
        and "readme-routing" not in allowances
    ):
        if not all(
            marker in text
            for marker in ("If you need to", "Start with", "You will leave with")
        ):
            findings.append(AuditFinding(
                "readme-routing",
                normalized,
                1,
                "add the required job-to-page routing table near the first action",
            ))
        in_fence = False
        fence_start = 0
        for line_number, line in enumerate(lines, start=1):
            if line.startswith("```"):
                if in_fence and line_number - fence_start > 13:
                    findings.append(AuditFinding(
                        "readme-reference-depth",
                        normalized,
                        fence_start,
                        "move configuration or schema examples over 12 lines to a reference page",
                    ))
                else:
                    fence_start = line_number
                in_fence = not in_fence
        table_start = 0
        table_lines = 0
        for line_number, line in enumerate([*lines, ""], start=1):
            if line.startswith("|"):
                if table_lines == 0:
                    table_start = line_number
                table_lines += 1
            else:
                if table_lines > 14:
                    findings.append(AuditFinding(
                        "readme-reference-depth",
                        normalized,
                        table_start,
                        "move lookup tables over 12 data rows to a reference page",
                    ))
                table_lines = 0
    if (
        require_depth_links
        and "elaboration-depth" not in allowances
        and (normalized == "README.md" or normalized.startswith("docs/learn/"))
    ):
        for title, section_line, _count, _allowances_for_section in _section_ranges(lines):
            start = section_line - 1
            following = [
                index
                for index, line in enumerate(lines[start + 1:], start=start + 1)
                if HEADING.match(line)
            ]
            end = following[0] if following else len(lines)
            body = "\n".join(lines[start + 1:end])
            words = re.findall(r"\b[\w'-]+\b", re.sub(r"`[^`]+`", "", body))
            deeper_link = any(
                target.split("#", 1)[0].endswith((".md", "/"))
                for target in LINK.findall(body)
            )
            if len(words) > 80 and not deeper_link:
                findings.append(AuditFinding(
                    "elaboration-depth",
                    normalized,
                    section_line,
                    f"{title!r} has {len(words)} words without a deeper-page route",
                ))
    return findings


def _assurance_findings(documents: dict[str, str]) -> list[AuditFinding]:
    rules = (
        (
            "model-authority",
            "docs/learn/deep-dive-the-deterministic-seam.md",
            re.compile(
                r"(?:deterministic code.{0,80}(?:owns|decides)|"
                r"models? may select|models?.{0,80}(?:cannot|never).{0,40}gate)",
                re.I,
            ),
        ),
        (
            "execution-boundary",
            "docs/SECURITY_MODEL.md",
            re.compile(
                r"(?:does not (?:execute|revoke)|without (?:importing|executing) "
                r"(?:repository|target) code)",
                re.I,
            ),
        ),
    )
    findings: list[AuditFinding] = []
    for _boundary, canonical, pattern in rules:
        for doc, text in documents.items():
            if (
                doc == canonical
                or REGISTER_PROFILE not in text
                or "assurance-dedup" in _allowances(text.splitlines())
            ):
                continue
            for line_number, line in _outside_fences(text.splitlines()):
                if pattern.search(line):
                    findings.append(AuditFinding(
                        "assurance-dedup",
                        doc,
                        line_number,
                        f"link to {canonical} instead of restating this authority boundary",
                    ))
    return findings


def _scan_audit(root: Path) -> AuditReport:
    root = root.resolve()
    pack = load_default_pack()
    section_limit = int(pack["policy"]["section_max_lines"])
    active: list[str] = []
    ignored: list[str] = []
    active_texts: dict[str, str] = {}
    findings: list[AuditFinding] = []
    for relative in _tracked_markdown(root):
        normalized = relative.as_posix()
        if "archive" in relative.parts or any(part.startswith(".") for part in relative.parts):
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
        active_texts[normalized] = text
        allowances = _allowances(lines)
        findings.extend(
            AuditFinding(item.rule, item.doc, item.line, item.detail)
            for item in check_document(normalized, text, pack)
        )
        if PROCESS_NAME.search(relative.name):
            findings.append(AuditFinding(
                "process-artifact",
                normalized,
                1,
                "move process history under an archive directory",
            ))
        page_type = _page_type(relative, text)
        doc_limit = (
            int(pack["policy"]["readme_max_lines"])
            if page_type == "readme"
            else int(pack["policy"]["guide_max_lines"])
        )
        for allowance_line, rule, reason in _allowance_records(lines):
            if rule in {"doc-length", "section-length"} and not re.search(
                r"\b(?:cut|moved|split|linked|reference)\b", reason, re.I
            ):
                findings.append(AuditFinding(
                    "invalid-length-allowance",
                    normalized,
                    allowance_line,
                    "replace comprehensiveness rationale with a subtraction receipt",
                ))
        if (
            page_type != "reference"
            and len(lines) > doc_limit
            and "doc-length" not in allowances
        ):
            findings.append(AuditFinding(
                "doc-length",
                normalized,
                1,
                f"{len(lines)} lines exceeds the {page_type} budget of {doc_limit}; move a second job behind a link",
            ))
        for title, section_line, count, section_allowances in _section_ranges(lines):
            if count > section_limit and "section-length" not in section_allowances:
                if page_type == "reference":
                    continue
                findings.append(AuditFinding(
                    "section-length",
                    normalized,
                    section_line,
                    f"{title!r} is {count} lines; move its second job behind a link",
                ))
        findings.extend(_section_depth_findings(
            normalized,
            lines,
            require_routes=bool(pack["policy"].get("require_readme_routes")),
            require_depth_links=bool(pack["policy"].get("require_depth_links")),
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
    findings.extend(_assurance_findings(active_texts))
    corpus_rule_names = {
        "surface": "process-artifact",
        "audience": "audience",
        "provenance": "provenance",
        "near-dup": "near-duplicate",
        "restatement": "restatement",
    }
    for corpus_finding in scan_corpus(root, include_lengths=False):
        corpus_rule = corpus_rule_names.get(corpus_finding.rule)
        if corpus_rule is None:
            continue
        try:
            text = (root / corpus_finding.doc).read_text(encoding="utf-8")
        except OSError:
            continue
        if corpus_rule in _allowances(text.splitlines()):
            continue
        candidate = AuditFinding(
            corpus_rule,
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


def audit(root: Path, *, use_baseline: bool = True) -> AuditReport:
    root = root.resolve()
    report = _scan_audit(root)
    baseline_path = root / AUDIT_BASELINE_PATH
    if not use_baseline or not baseline_path.exists():
        return report
    baseline = _load_audit_baseline(baseline_path)
    current = {finding_fingerprint(item): item for item in report.findings}
    recorded = {finding_fingerprint(item): item for item in baseline}
    matched = tuple(sorted(
        (current[fingerprint] for fingerprint in current.keys() & recorded.keys()),
        key=_finding_order,
    ))
    active = tuple(sorted(
        (current[fingerprint] for fingerprint in current.keys() - recorded.keys()),
        key=_finding_order,
    ))
    stale = tuple(sorted(
        (recorded[fingerprint] for fingerprint in recorded.keys() - current.keys()),
        key=_finding_order,
    ))
    return AuditReport(
        report.documents,
        report.ignored_documents,
        active,
        matched,
        stale,
    )


def write_audit_baseline(root: Path) -> Path:
    root = root.resolve()
    path = root / AUDIT_BASELINE_PATH
    raw_report = audit(root, use_baseline=False)
    atomic_write(path, render_audit_baseline(raw_report.findings))
    return path
