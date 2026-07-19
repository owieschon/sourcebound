from __future__ import annotations

import hashlib
import json
import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from clean_docs.applicability import (
    DocumentProfile,
    classify_document,
    frontmatter_error,
    role_override_error,
)
from clean_docs.corpus import _git_visible_markdown, _is_document_candidate, scan_corpus
from clean_docs.errors import ConfigurationError
from clean_docs.mdx import (
    MdxDocument,
    MdxParserError,
    parse_mdx_documents,
    parser_availability,
)
from clean_docs.policy import REGISTER_PROFILE, check_document
from clean_docs.regions import atomic_write
from clean_docs.residue import scan_residue
from clean_docs.standard import load_default_pack


LINK = re.compile(
    r"\[[^\]]+\]\(\s*(<[^>\n]*>|\[[^\]\n]+\]|\{[^}\n]+\}|[^)\s]+)"
)
HEADING = re.compile(r"^#{2,}\s+(.+?)\s*$")
IDENTITY_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
PURPOSE_BLOCK = re.compile(
    r"<!-- clean-docs:purpose -->\s*(.*?)\s*<!-- clean-docs:end purpose -->",
    re.DOTALL,
)
STOCK_PURPOSE_OPENING = re.compile(
    r"^Use this (?:guide|model|page|path|policy|reference|specification) when\b",
    re.IGNORECASE,
)
ALLOW = re.compile(
    r'<!--\s*clean-docs:allow\s+([a-z][a-z-]+)\s+reason="([^"]+)"\s*-->'
)
AUDIT_BASELINE_SCHEMA_V1 = "clean-docs.audit-baseline.v1"
AUDIT_BASELINE_SCHEMA = "clean-docs.audit-baseline.v2"
AUDIT_BASELINE_PATH = Path(".clean-docs/audit-baseline.json")


def _is_test_fixture_path(value: str) -> bool:
    path = Path(value)
    parts = set(path.parts)
    name = path.name
    return bool(
        parts & {"test", "tests", "__tests__", "fixtures", "__fixtures__"}
        or ".test." in name
        or ".spec." in name
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
    baselined_findings: tuple[AuditFinding, ...] = ()
    stale_baseline: tuple[AuditFinding, ...] = ()
    unsupported_documents: tuple[str, ...] = ()
    advisories: tuple[AuditFinding, ...] = ()
    advisory_totals: tuple[tuple[str, int], ...] = ()
    document_profiles: tuple[DocumentProfile, ...] = ()
    repository_integrity_enforced: bool = False
    policy_preview: bool = False

    @property
    def ok(self) -> bool:
        return not self.findings and not self.stale_baseline


@dataclass(frozen=True)
class _BaselineIdentity:
    finding: AuditFinding
    normalized: str
    section_anchor: str
    duplicate_ordinal: int
    fingerprint: str


@dataclass(frozen=True)
class _LoadedBaseline:
    schema: str
    identities: tuple[_BaselineIdentity, ...]


def _normalized_finding_content(finding: AuditFinding) -> str:
    return " ".join(finding.detail.split())


def finding_fingerprint(
    finding: AuditFinding,
    *,
    section_anchor: str = "__document__",
    duplicate_ordinal: int = 1,
) -> str:
    payload = json.dumps(
        {
            "duplicate_ordinal": duplicate_ordinal,
            "normalized": _normalized_finding_content(finding),
            "path": finding.path,
            "rule": finding.rule,
            "section_anchor": section_anchor,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _finding_order(finding: AuditFinding) -> tuple[str, int, str, str]:
    return (finding.path, finding.line, finding.rule, finding.detail)


def _legacy_finding_fingerprint(finding: AuditFinding) -> str:
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


def _section_anchor(root: Path | None, finding: AuditFinding) -> str:
    if root is None:
        return "__document__"
    try:
        text = (root / finding.path).read_text(encoding="utf-8")
        if Path(finding.path).suffix.lower() == ".mdx":
            text = parse_mdx_documents({finding.path: text})[0][
                finding.path
            ].policy_text(text)
        lines = text.splitlines()
    except (OSError, MdxParserError, KeyError):
        return "__document__"
    anchor = "__document__"
    for line in lines[: finding.line]:
        if match := IDENTITY_HEADING.match(line):
            anchor = re.sub(
                r"-+",
                "-",
                re.sub(r"[^a-z0-9]+", "-", match.group(1).lower()),
            ).strip("-") or "__document__"
    return anchor


def _baseline_identities(
    findings: tuple[AuditFinding, ...],
    *,
    root: Path | None,
) -> tuple[_BaselineIdentity, ...]:
    prepared = [
        (
            finding,
            _normalized_finding_content(finding),
            _section_anchor(root, finding),
        )
        for finding in findings
    ]
    prepared.sort(
        key=lambda item: (
            item[0].path,
            item[0].rule,
            item[1],
            item[2],
            item[0].line,
            item[0].detail,
        )
    )
    counts: dict[tuple[str, str, str, str], int] = {}
    identities: list[_BaselineIdentity] = []
    for finding, normalized, section_anchor in prepared:
        key = (finding.path, finding.rule, normalized, section_anchor)
        duplicate_ordinal = counts.get(key, 0) + 1
        counts[key] = duplicate_ordinal
        identities.append(
            _BaselineIdentity(
                finding,
                normalized,
                section_anchor,
                duplicate_ordinal,
                finding_fingerprint(
                    finding,
                    section_anchor=section_anchor,
                    duplicate_ordinal=duplicate_ordinal,
                ),
            )
        )
    return tuple(identities)


def _bounded_advisories(
    findings: list[AuditFinding],
    *,
    per_rule: int = 3,
) -> tuple[tuple[AuditFinding, ...], tuple[tuple[str, int], ...]]:
    totals: dict[str, int] = {}
    selected: list[AuditFinding] = []
    emitted: dict[str, int] = {}
    for finding in sorted(findings, key=_finding_order):
        totals[finding.rule] = totals.get(finding.rule, 0) + 1
        count = emitted.get(finding.rule, 0)
        if count < per_rule:
            selected.append(finding)
            emitted[finding.rule] = count + 1
    return tuple(selected), tuple(sorted(totals.items()))


def render_audit_baseline(
    findings: tuple[AuditFinding, ...],
    *,
    root: Path | None = None,
) -> str:
    entries = []
    for identity in _baseline_identities(findings, root=root):
        finding = identity.finding
        entries.append({
            "fingerprint": identity.fingerprint,
            "rule": finding.rule,
            "path": finding.path,
            "line_hint": finding.line,
            "detail": finding.detail,
            "normalized": identity.normalized,
            "section_anchor": identity.section_anchor,
            "duplicate_ordinal": identity.duplicate_ordinal,
        })
    return json.dumps(
        {"schema": AUDIT_BASELINE_SCHEMA, "findings": entries},
        indent=2,
    ) + "\n"


def _load_audit_baseline(path: Path) -> _LoadedBaseline:
    if path.is_symlink():
        raise ConfigurationError(f"audit baseline cannot be a symbolic link: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read audit baseline {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") not in {
        AUDIT_BASELINE_SCHEMA_V1,
        AUDIT_BASELINE_SCHEMA,
    }:
        raise ConfigurationError(f"audit baseline has an unsupported schema: {path}")
    schema = raw["schema"]
    entries = raw.get("findings")
    if not isinstance(entries, list):
        raise ConfigurationError(f"audit baseline findings must be a list: {path}")
    identities: list[_BaselineIdentity] = []
    fingerprints: set[str] = set()
    identity_keys: set[tuple[str, str, str, str, int]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConfigurationError(f"audit baseline finding {index} must be an object")
        expected_keys = (
            {"fingerprint", "rule", "path", "line", "detail"}
            if schema == AUDIT_BASELINE_SCHEMA_V1
            else {
                "fingerprint",
                "rule",
                "path",
                "line_hint",
                "detail",
                "normalized",
                "section_anchor",
                "duplicate_ordinal",
            }
        )
        if set(entry) != expected_keys:
            raise ConfigurationError(
                f"audit baseline finding {index} has fields that do not match {schema}"
            )
        if not all(
            isinstance(entry[key], str)
            for key in ("fingerprint", "rule", "path", "detail")
        ):
            raise ConfigurationError(f"audit baseline finding {index} has an invalid string field")
        line_key = "line" if schema == AUDIT_BASELINE_SCHEMA_V1 else "line_hint"
        if (
            not isinstance(entry[line_key], int)
            or isinstance(entry[line_key], bool)
            or entry[line_key] < 1
        ):
            raise ConfigurationError(f"audit baseline finding {index} has an invalid line")
        finding = AuditFinding(
            entry["rule"],
            entry["path"],
            entry[line_key],
            entry["detail"],
        )
        if schema == AUDIT_BASELINE_SCHEMA_V1:
            normalized = _normalized_finding_content(finding)
            section_anchor = "__legacy_line__"
            duplicate_ordinal = 1
            fingerprint = _legacy_finding_fingerprint(finding)
        else:
            if not all(
                isinstance(entry[key], str)
                for key in ("normalized", "section_anchor")
            ):
                raise ConfigurationError(
                    f"audit baseline finding {index} has invalid identity material"
                )
            duplicate_ordinal = entry["duplicate_ordinal"]
            if (
                not isinstance(duplicate_ordinal, int)
                or isinstance(duplicate_ordinal, bool)
                or duplicate_ordinal < 1
            ):
                raise ConfigurationError(
                    f"audit baseline finding {index} has an invalid duplicate ordinal"
                )
            normalized = entry["normalized"]
            section_anchor = entry["section_anchor"]
            if normalized != _normalized_finding_content(finding):
                raise ConfigurationError(
                    f"audit baseline finding {index} normalized content does not match"
                )
            fingerprint = finding_fingerprint(
                finding,
                section_anchor=section_anchor,
                duplicate_ordinal=duplicate_ordinal,
            )
        if entry["fingerprint"] != fingerprint:
            raise ConfigurationError(f"audit baseline finding {index} fingerprint does not match")
        if fingerprint in fingerprints:
            raise ConfigurationError(f"audit baseline has duplicate finding {fingerprint}")
        identity_key = (
            finding.path,
            finding.rule,
            normalized,
            section_anchor,
            duplicate_ordinal,
        )
        if schema == AUDIT_BASELINE_SCHEMA and identity_key in identity_keys:
            raise ConfigurationError(
                f"audit baseline has duplicate identity at finding {index}"
            )
        fingerprints.add(fingerprint)
        identity_keys.add(identity_key)
        identities.append(
            _BaselineIdentity(
                finding,
                normalized,
                section_anchor,
                duplicate_ordinal,
                fingerprint,
            )
        )
    identities.sort(key=lambda item: item.fingerprint)
    return _LoadedBaseline(schema, tuple(identities))


def _tracked_markdown(root: Path) -> list[Path]:
    visible = _git_visible_markdown(root)
    if visible is not None:
        return [
            relative
            for path in visible
            if _is_document_candidate(
                relative := path.relative_to(root),
                fallback=False,
            )
        ]
    return sorted(
        relative
        for pattern in ("*.md", "*.mdx")
        for path in root.rglob(pattern)
        if _is_document_candidate(
            relative := path.relative_to(root),
            fallback=True,
        )
    )


def _repository_entries(root: Path) -> set[str]:
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
                "-z",
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        proc = None
    if proc is not None and proc.returncode == 0:
        return {
            path
            for path in proc.stdout.decode(errors="surrogateescape").split("\0")
            if path
        }
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _hidden_document(relative: Path) -> bool:
    hidden = [part for part in relative.parts if part.startswith(".")]
    return bool(hidden) and relative.parts[0] != ".agents"


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
    return not target.startswith(("#", "http://", "https://", "mailto:", "data:"))


def _mask_inline_code(line: str) -> str:
    result = list(line)
    index = 0
    while index < len(line):
        if line[index] != "`" or (index > 0 and line[index - 1] == "\\"):
            index += 1
            continue
        width = 1
        while index + width < len(line) and line[index + width] == "`":
            width += 1
        end = line.find("`" * width, index + width)
        if end == -1:
            index += width
            continue
        for position in range(index, end + width):
            result[position] = " "
        index = end + width
    return "".join(result)


def _markdown_links(lines: list[str]) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    for line_number, line in enumerate(lines, start=1):
        fence_match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue
        visible = _mask_inline_code(line)
        for match in LINK.finditer(visible):
            links.append((line_number, match.group(1)))
    return links


def _placeholder_link_target(target: str) -> bool:
    candidate = target.strip()
    if candidate in {"...", "…"} or "…" in candidate:
        return True
    if re.search(r"<(?:[A-Za-z][A-Za-z0-9_-]*)>", candidate):
        return True
    if re.search(r"\{(?:[A-Za-z][A-Za-z0-9_-]*)}", candidate):
        return True
    if (
        candidate.startswith("[")
        and candidate.endswith("]")
        and re.search(r"\s", candidate[1:-1])
    ):
        return True
    if (
        candidate.startswith("<")
        and candidate.endswith(">")
        and re.search(r"\s", candidate[1:-1])
    ):
        return True
    return False


def _entry_exists(entries: set[str], candidate: str) -> bool:
    normalized = candidate.rstrip("/")
    return normalized in entries or any(
        entry.startswith(normalized + "/") for entry in entries
    )


def _link_target_exists(
    root: Path,
    source: Path,
    raw_target: str,
    entries: set[str],
) -> bool:
    target = unquote(raw_target.split("#", 1)[0].split("?", 1)[0]).strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if not target or not _local_link(target):
        return True
    repository_root = target.startswith("/")
    if repository_root:
        candidate = posixpath.normpath(target.lstrip("/"))
    else:
        candidate = posixpath.normpath(
            posixpath.join(source.parent.as_posix(), target)
        )
    if candidate == ".." or candidate.startswith("../"):
        return False
    candidates = [candidate]
    if not Path(candidate).suffix:
        candidates.extend(
            (
                candidate + ".md",
                candidate + ".mdx",
                posixpath.join(candidate, "README.md"),
                posixpath.join(candidate, "index.md"),
                posixpath.join(candidate, "index.mdx"),
            )
        )
    if any(_entry_exists(entries, item) for item in candidates):
        return True
    if any((root / item).exists() for item in candidates):
        return True
    # A leading slash can address an application or publication mount. Without
    # a declared mount, treating it as a repository path creates false blockers.
    return repository_root


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


def _purpose_template_findings(documents: dict[str, str]) -> list[AuditFinding]:
    matches: list[str] = []
    for doc, text in documents.items():
        if REGISTER_PROFILE not in text:
            continue
        block = PURPOSE_BLOCK.search(text)
        if block and STOCK_PURPOSE_OPENING.search(" ".join(block.group(1).split())):
            matches.append(doc)
    if len(matches) < 3:
        return []
    return [
        AuditFinding(
            "purpose-template",
            doc,
            next(
                (
                    line_number + 1
                    for line_number, line in enumerate(
                        documents[doc].splitlines(), start=1
                    )
                    if line.strip() == "<!-- clean-docs:purpose -->"
                ),
                1,
            ),
            "replace the repeated 'Use this ... when' shell with a reader situation specific to this page",
        )
        for doc in matches
    ]


def _scan_audit(root: Path, *, preview_policy: bool = False) -> AuditReport:
    root = root.resolve()
    repository_integrity_enforced = (root / ".clean-docs.yml").is_file()
    pack = load_default_pack()
    repository_entries = _repository_entries(root)
    tracked_documents = _tracked_markdown(root)
    mdx_sources: dict[str, str] = {}
    mdx_failures: dict[str, str] = {}
    parsed_mdx: dict[str, MdxDocument] = {}
    for relative in tracked_documents:
        if relative.suffix.lower() != ".mdx":
            continue
        normalized = relative.as_posix()
        try:
            mdx_sources[normalized] = (root / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            mdx_failures[normalized] = f"cannot read MDX: {exc}"
    if mdx_sources:
        available, detail = parser_availability()
        if not available:
            mdx_failures.update(
                (path, detail) for path in mdx_sources
            )
        else:
            try:
                parsed_mdx, parser_failures = parse_mdx_documents(mdx_sources)
            except MdxParserError as exc:
                parser_failures = {
                    path: str(exc) for path in mdx_sources
                }
            mdx_failures.update(parser_failures)
    unsupported: set[str] = set()
    section_limit = int(pack["policy"]["section_max_lines"])
    active: list[str] = []
    ignored: list[str] = []
    active_texts: dict[str, str] = {}
    profiles: dict[str, DocumentProfile] = {}
    invalid_roles: set[str] = set()
    findings: list[AuditFinding] = []
    advisories: list[AuditFinding] = []
    for relative in tracked_documents:
        normalized = relative.as_posix()
        if "archive" in relative.parts or _hidden_document(relative):
            ignored.append(normalized)
            continue
        path = root / relative
        try:
            text = (
                mdx_sources[normalized]
                if relative.suffix.lower() == ".mdx"
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as exc:
            candidate = AuditFinding("unreadable-document", normalized, 1, str(exc))
            (findings if repository_integrity_enforced else advisories).append(candidate)
            continue
        mdx_document = parsed_mdx.get(normalized)
        if relative.suffix.lower() == ".mdx" and mdx_document is None:
            unsupported.add(normalized)
            candidate = AuditFinding(
                "unsupported-mdx",
                normalized,
                1,
                mdx_failures.get(normalized, "MDX parser did not return a result"),
            )
            (findings if repository_integrity_enforced else advisories).append(candidate)
            continue
        active.append(normalized)
        lines = text.splitlines()
        policy_text = (
            mdx_document.policy_text(text) if mdx_document is not None else text
        )
        policy_lines = policy_text.splitlines()
        active_texts[normalized] = policy_text
        profile = classify_document(relative, policy_text)
        profiles[normalized] = profile
        role_error = role_override_error(text)
        structure_error = frontmatter_error(text)
        if role_error or structure_error:
            invalid_roles.add(normalized)
            findings.append(AuditFinding(
                (
                    "invalid-document-role"
                    if role_error
                    else "malformed-frontmatter"
                ),
                normalized,
                1,
                role_error or structure_error or "invalid document structure",
            ))
        allowances = _allowances(policy_lines)
        evaluate_policy = profile.registered or preview_policy
        if preview_policy and not profile.registered:
            policy_text = f"{policy_text.rstrip()}\n\n{REGISTER_PROFILE}\n"
        for item in (
            ()
            if role_error or not evaluate_policy
            else check_document(normalized, policy_text, pack)
        ):
            if not profile.applies(item.rule):
                continue
            candidate = AuditFinding(item.rule, item.doc, item.line, item.detail)
            (findings if profile.registered else advisories).append(candidate)
        page_type = _page_type(relative, text)
        if (
            not role_error
            and evaluate_policy
            and profile.role in {"overview", "task", "tutorial"}
        ):
            doc_limit = (
                int(pack["policy"]["readme_max_lines"])
                if page_type == "readme"
                else int(pack["policy"]["guide_max_lines"])
            )
            for allowance_line, rule, reason in _allowance_records(policy_lines):
                if rule in {"doc-length", "section-length"} and not re.search(
                    r"\b(?:cut|moved|split|linked|reference)\b", reason, re.I
                ):
                    candidate = AuditFinding(
                        "invalid-length-allowance",
                        normalized,
                        allowance_line,
                        "replace comprehensiveness rationale with a subtraction receipt",
                    )
                    advisories.append(candidate)
            if (
                len(lines) > doc_limit
                and "doc-length" not in allowances
            ):
                candidate = AuditFinding(
                    "doc-length",
                    normalized,
                    1,
                    f"{len(lines)} lines exceeds the {page_type} budget of {doc_limit}; move a second job behind a link",
                )
                advisories.append(candidate)
            for title, section_line, count, section_allowances in _section_ranges(
                policy_lines
            ):
                if count > section_limit and "section-length" not in section_allowances:
                    candidate = AuditFinding(
                        "section-length",
                        normalized,
                        section_line,
                        f"{title!r} is {count} lines; move its second job behind a link",
                    )
                    advisories.append(candidate)
        for candidate in _section_depth_findings(
                normalized,
            policy_lines,
                require_routes=bool(pack["policy"].get("require_readme_routes")),
                require_depth_links=bool(pack["policy"].get("require_depth_links")),
        ):
            if (
                not role_error
                and evaluate_policy
                and profile.applies(candidate.rule)
            ):
                (findings if profile.registered else advisories).append(candidate)
        document_links = (
            [(link.line, link.url) for link in mdx_document.links]
            if mdx_document is not None
            else _markdown_links(lines)
        )
        for line_number, target in document_links:
            if (
                _placeholder_link_target(target)
                and profile.role in {"agent-procedure", "template"}
            ):
                advisories.append(
                    AuditFinding(
                        "placeholder-link",
                        normalized,
                        line_number,
                        f"template destination is unresolved: {target}",
                    )
                )
                continue
            if not _link_target_exists(root, relative, target, repository_entries):
                candidate = AuditFinding(
                    "broken-local-link",
                    normalized,
                    line_number,
                    f"target does not exist: {target}",
                )
                (
                    findings
                    if repository_integrity_enforced or profile.registered
                    else advisories
                ).append(candidate)
    # These comparisons require editorial ownership knowledge. They remain
    # visible, but they cannot reject a repository from token overlap alone.
    advisories.extend(_assurance_findings(active_texts))
    for candidate in _purpose_template_findings(active_texts):
        if candidate.path in invalid_roles:
            continue
        scoped_profile = profiles.get(candidate.path)
        if scoped_profile is None or not scoped_profile.applies(candidate.rule):
            continue
        (findings if scoped_profile.registered else advisories).append(candidate)
    corpus_rule_names = {
        "surface": "process-artifact",
        "audience": "audience",
        "provenance": "provenance",
        "near-dup": "near-duplicate",
        "restatement": "restatement",
    }
    for corpus_finding in scan_corpus(
        root,
        include_lengths=False,
        prepared_documents=active_texts,
    ):
        corpus_rule = corpus_rule_names.get(corpus_finding.rule)
        if corpus_rule is None:
            continue
        corpus_profile = profiles.get(corpus_finding.doc)
        if corpus_profile is None:
            continue
        if corpus_rule == "audience" and corpus_profile.role in {
            "agent-procedure",
            "template",
        }:
            continue
        if corpus_rule == "provenance" and corpus_profile.role in {"evidence", "plan"}:
            continue
        if corpus_rule in {"near-duplicate", "restatement"}:
            if corpus_profile.role in {"agent-procedure", "evidence", "plan", "template"}:
                continue
            counterpart = re.search(r"overlap with (.+):\d+", corpus_finding.detail)
            if counterpart:
                other = profiles.get(counterpart.group(1))
                if other is not None and other.role != corpus_profile.role:
                    continue
        corpus_text = active_texts.get(corpus_finding.doc)
        if corpus_text is None:
            continue
        if corpus_rule in _allowances(corpus_text.splitlines()):
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
            for existing in [*findings, *advisories]
        ):
            advisories.append(candidate)
    for residue_finding in scan_residue(root):
        candidate = AuditFinding(
            residue_finding.rule,
            residue_finding.doc,
            residue_finding.line,
            residue_finding.detail,
        )
        residue_profile = profiles.get(residue_finding.doc)
        fixture_machine_path = (
            residue_finding.rule == "local-path-residue"
            and _is_test_fixture_path(residue_finding.doc)
        )
        residue_blocks = not fixture_machine_path and (
            repository_integrity_enforced
            or residue_profile is not None and residue_profile.registered
        )
        (
            findings
            if residue_blocks
            else advisories
        ).append(candidate)
    findings.sort(key=lambda item: (item.path, item.line, item.rule))
    bounded_advisories, advisory_totals = _bounded_advisories(advisories)
    return AuditReport(
        tuple(active),
        tuple(ignored),
        tuple(findings),
        unsupported_documents=tuple(sorted(unsupported)),
        advisories=bounded_advisories,
        advisory_totals=advisory_totals,
        document_profiles=tuple(
            profiles[path] for path in sorted(profiles)
        ),
        repository_integrity_enforced=repository_integrity_enforced,
        policy_preview=preview_policy,
    )


def audit(
    root: Path,
    *,
    use_baseline: bool = True,
    preview_policy: bool = False,
) -> AuditReport:
    root = root.resolve()
    report = _scan_audit(root, preview_policy=preview_policy)
    baseline_path = root / AUDIT_BASELINE_PATH
    if not use_baseline or not baseline_path.exists():
        return report
    baseline = _load_audit_baseline(baseline_path)
    if baseline.schema == AUDIT_BASELINE_SCHEMA_V1:
        current = {
            _legacy_finding_fingerprint(item): item
            for item in report.findings
        }
    else:
        current = {
            identity.fingerprint: identity.finding
            for identity in _baseline_identities(report.findings, root=root)
        }
    recorded = {
        identity.fingerprint: identity.finding
        for identity in baseline.identities
    }
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
        documents=report.documents,
        ignored_documents=report.ignored_documents,
        findings=active,
        baselined_findings=matched,
        stale_baseline=stale,
        unsupported_documents=report.unsupported_documents,
        advisories=report.advisories,
        advisory_totals=report.advisory_totals,
        document_profiles=report.document_profiles,
        repository_integrity_enforced=report.repository_integrity_enforced,
        policy_preview=report.policy_preview,
    )


def write_audit_baseline(root: Path) -> Path:
    root = root.resolve()
    path = root / AUDIT_BASELINE_PATH
    raw_report = audit(root, use_baseline=False)
    atomic_write(path, render_audit_baseline(raw_report.findings, root=root))
    return path
