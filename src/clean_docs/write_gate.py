from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clean_docs.policy import PolicyFinding


CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".go", ".rs", ".rb", ".java",
    ".sql", ".c", ".cpp", ".swift",
}
DATA_EXTENSIONS = {".json", ".jsonl", ".csv", ".yaml", ".yml", ".toml", ".lock", ".plist"}
EXEMPT_PATH_PARTS = (
    "narrative_content", "golden_corpus", "/gold/", "fixtures", "corpus", ".venv/",
    "node_modules/", "quality-gate", "quality_gate",
)
SECRET_RULES = (
    ("secret-aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "all"),
    ("secret-github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "all"),
    # Fail closed: a long sk- kebab slug can be redacted rather than missed.
    ("secret-openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "all"),
    ("secret-pem-private", re.compile(r"-----BEGIN [A-Z ]{0,20}PRIVATE KEY-----"), "all"),
    ("secret-jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "all"),
    ("secret-auth-header-json", re.compile(r'"(authorization|api[_-]?key|apikey|token|secret|password)"\s*:\s*"(?=[^"]*[0-9])(Bearer |Basic |Token )?[A-Za-z0-9_./+=-]{16,}"', re.I), "all"),
)
RULES = (
    ("delve", re.compile(r"\bdelv(e|es|ing)\b", re.I), "all"),
    ("important-to-note", re.compile(r"\bit('| i)s important to note\b", re.I), "all"),
    ("fast-paced", re.compile(r"in today's fast-paced", re.I), "all"),
    ("as-an-ai", re.compile(r"\bas an ai\b", re.I), "all"),
    ("assistant-voice", re.compile(r"\b(great question|i'd be happy to|certainly!)\B", re.I), "all"),
    ("marketing-register", re.compile(r"\b(seamlessly integrat|game.chang|revolutioniz|rich tapestry)", re.I), "all"),
    ("utilize-verb", re.compile(r"\butiliz(e|es|ed|ing)\b", re.I), "all"),
    ("in-conclusion", re.compile(r"^\s*in conclusion,", re.I | re.M), "all"),
    ("hedge-stack", re.compile(r"\b(might|may|could)\s+(potentially|possibly|perhaps)\b", re.I), "all"),
    ("unverified-claim", re.compile(r"\bshould (now )?work\b", re.I), "all"),
    ("bare-except", re.compile(r"^\s*except\s*:\s*(#.*)?$", re.M), "code"),
    ("swallowed-exception", re.compile(r"except[^\n]*:\s*(\n\s*)?pass\b"), "code"),
    ("placeholder-cred", re.compile(r"(your[_-]api[_-]key|changeme|<your_|sk-xxxx|lorem ipsum)", re.I), "code"),
    ("deferred-work-marker", re.compile(r"\b(TODO|FIXME|XXX|HACK)\b"), "code"),
    ("comment-meta-narration", re.compile(r"(#\s*this (function|method|class|file)\b|\"\"\"\s*This (function|method|class)\b)", re.I), "code"),
    ("emoji-in-code", re.compile(r"[\U0001F300-\U0001FAFF✅❌✨]"), "code"),
) + SECRET_RULES
PRAGMA = re.compile(r"slop-ok:\s*\S+")


@dataclass(frozen=True)
class WriteGateResult:
    path: str
    findings: tuple[PolicyFinding, ...]
    overridden: tuple[PolicyFinding, ...]


def redact_secrets(text: str) -> tuple[str, tuple[str, ...]]:
    redacted = text
    rules: list[str] = []
    for rule_id, pattern, _applies in SECRET_RULES:
        if pattern.search(redacted):
            rules.append(rule_id)
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted, tuple(rules)


def _new_content(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name == "Write":
        return str(tool_input.get("content", ""))
    if tool_name == "Edit":
        return str(tool_input.get("new_string", ""))
    if tool_name == "MultiEdit":
        return "\n".join(str(edit.get("new_string", "")) for edit in tool_input.get("edits", []))
    if tool_name == "NotebookEdit":
        return str(tool_input.get("new_source", ""))
    return ""


def _file_class(path: str) -> str:
    extension = Path(path).suffix.lower()
    if extension in CODE_EXTENSIONS:
        return "code"
    if extension in DATA_EXTENSIONS:
        return "data"
    return "prose"


def evaluate_write(payload: dict[str, Any]) -> WriteGateResult:
    """Evaluate one pre-write hook payload without reading or writing the target file."""
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}
    path = str(tool_input.get("file_path", "") or tool_input.get("notebook_path", ""))
    if any(part in path for part in EXEMPT_PATH_PARTS) or _file_class(path) == "data":
        return WriteGateResult(path, (), ())
    content = _new_content(tool_name, tool_input)
    if not content:
        return WriteGateResult(path, (), ())
    lines = content.splitlines()
    findings: list[PolicyFinding] = []
    overridden: list[PolicyFinding] = []
    file_class = _file_class(path)
    for rule_id, pattern, applies in RULES:
        if applies == "code" and file_class != "code":
            continue
        for match in pattern.finditer(content):
            line_number = content.count("\n", 0, match.start()) + 1
            line = lines[line_number - 1] if line_number <= len(lines) else ""
            finding = PolicyFinding(path, line_number, rule_id, line.strip()[:90])
            (overridden if PRAGMA.search(line) else findings).append(finding)
    return WriteGateResult(path, tuple(findings), tuple(overridden))


def _log(path: Path, entry: dict[str, Any]) -> None:
    try:
        entry["ts"] = datetime.now(timezone.utc).isoformat()
        entry["cwd"] = os.getcwd()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    result = evaluate_write(payload)
    log_path = Path(os.path.expanduser("~/.claude/quality_gate_log.jsonl"))
    if result.overridden:
        _log(log_path, {
            "file": result.path,
            "action": "override",
            "hits": [
                {"rule": item.rule, "line": item.line, "snippet": item.detail}
                for item in result.overridden
            ],
        })
    if not result.findings:
        return 0
    _log(log_path, {
        "file": result.path,
        "action": "block",
        "hits": [
            {"rule": item.rule, "line": item.line, "snippet": item.detail}
            for item in result.findings
        ],
    })
    sys.stderr.write(
        f"QUALITY GATE: {len(result.findings)} slop pattern(s) blocked this write to {result.path}.\n"
        "Rewrite the flagged content without the pattern -- do not paraphrase around "
        "it with equivalent filler; state things plainly or cut them.\n"
    )
    for finding in result.findings[:10]:
        sys.stderr.write(f"  [{finding.rule}] line {finding.line}: {finding.detail}\n")
    sys.stderr.write(
        "If a flagged line is INTENTIONAL content (test data, authored persona text), "
        "append `slop-ok: <reason>` to that exact line -- overrides are logged and "
        "reviewed at retro.\n"
    )
    return 2
