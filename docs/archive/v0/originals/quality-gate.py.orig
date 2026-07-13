#!/usr/bin/env python3
"""PreToolUse gate on Write/Edit: blocks slop BEFORE the file exists.

Three registers, high-precision rules only (a gate that cries wolf gets
disabled): language slop, code-structure slop, engineering-claim slop.
Exit 2 + stderr = tool call blocked, model regenerates; exit 0 = clean.
Every block and every pragma-override is logged to
~/.claude/quality_gate_log.jsonl -- retro reads the catch-rate.

Escape valve (bounded, audited): a line containing `slop-ok: <reason>`
suppresses findings on that line; the override is logged. Overrides are
reviewed at retro -- they are receipts, not free passes.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

LOG_PATH = os.path.expanduser("~/.claude/quality_gate_log.jsonl")

CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".go", ".rs", ".rb", ".java", ".sql", ".c", ".cpp", ".swift"}
DATA_EXT = {".json", ".jsonl", ".csv", ".yaml", ".yml", ".toml", ".lock", ".plist"}

# Paths where authored "slop" is intentional content (fixtures, personas,
# hostile test data) or where the gate would flag its own rule list.
EXEMPT_SUBSTRINGS = (
    "narrative_content", "golden_corpus", "/gold/", "fixtures",
    "corpus", ".venv/", "node_modules/", "quality-gate", "quality_gate",
)

# (rule_id, compiled_regex, applies_to)  applies_to: all | code | prose
RULES = [
    # -- language slop (all files) --
    ("delve", re.compile(r"\bdelv(e|es|ing)\b", re.I), "all"),
    ("important-to-note", re.compile(r"\bit('| i)s important to note\b", re.I), "all"),
    ("fast-paced", re.compile(r"in today's fast-paced", re.I), "all"),
    ("as-an-ai", re.compile(r"\bas an ai\b", re.I), "all"),
    ("assistant-voice", re.compile(r"\b(great question|i'd be happy to|certainly!)\B", re.I), "all"),
    ("marketing-register", re.compile(r"\b(seamlessly integrat|game.chang|revolutioniz|rich tapestry)", re.I), "all"),
    ("utilize-verb", re.compile(r"\butiliz(e|es|ed|ing)\b", re.I), "all"),  # verb only; "utilization" the noun stays legal
    ("in-conclusion", re.compile(r"^\s*in conclusion,", re.I | re.M), "all"),
    ("hedge-stack", re.compile(r"\b(might|may|could)\s+(potentially|possibly|perhaps)\b", re.I), "all"),
    # -- engineering-claim slop (all files) --
    ("unverified-claim", re.compile(r"\bshould (now )?work\b", re.I), "all"),
    # -- code-structure slop (code files only) --
    ("bare-except", re.compile(r"^\s*except\s*:\s*(#.*)?$", re.M), "code"),
    ("swallowed-exception", re.compile(r"except[^\n]*:\s*(\n\s*)?pass\b"), "code"),
    ("placeholder-cred", re.compile(r"(your[_-]api[_-]key|changeme|<your_|sk-xxxx|lorem ipsum)", re.I), "code"),
    ("deferred-work-marker", re.compile(r"\b(TODO|FIXME|XXX|HACK)\b"), "code"),
    ("comment-meta-narration", re.compile(r"(#\s*this (function|method|class|file)\b|\"\"\"\s*This (function|method|class)\b)", re.I), "code"),
    ("emoji-in-code", re.compile(r"[\U0001F300-\U0001FAFF✅❌✨]"), "code"),
    # -- credential slop (all files; ported from gstack's secret-scan, 2026-07-04) --
    ("secret-aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "all"),
    ("secret-github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "all"),
    ("secret-openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "all"),
    ("secret-pem-private", re.compile(r"-----BEGIN [A-Z ]{0,20}PRIVATE KEY-----"), "all"),
    ("secret-jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "all"),
    ("secret-auth-header-json", re.compile(r"\"(authorization|api[_-]?key|apikey|token|secret|password)\"\s*:\s*\"(?=[^\"]*[0-9])(Bearer |Basic |Token )?[A-Za-z0-9_./+=-]{16,}\"", re.I), "all"),
]

PRAGMA = re.compile(r"slop-ok:\s*\S+")


def new_content(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Write":
        return tool_input.get("content", "")
    if tool_name == "Edit":
        return tool_input.get("new_string", "")
    if tool_name == "MultiEdit":
        return "\n".join(e.get("new_string", "") for e in tool_input.get("edits", []))
    if tool_name == "NotebookEdit":
        return tool_input.get("new_source", "")
    return ""


def file_class(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in CODE_EXT:
        return "code"
    if ext in DATA_EXT:
        return "data"
    return "prose"


def log(entry: dict) -> None:
    try:
        entry["ts"] = datetime.now(timezone.utc).isoformat()
        entry["cwd"] = os.getcwd()
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # slop-ok: logging must never block the gate itself


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")

    if any(s in path for s in EXEMPT_SUBSTRINGS):
        return 0
    fclass = file_class(path)
    if fclass == "data":
        return 0
    content = new_content(tool_name, tool_input)
    if not content:
        return 0

    lines = content.splitlines()
    findings = []
    overridden = []
    for rule_id, rx, applies in RULES:
        if applies == "code" and fclass != "code":
            continue
        if applies == "prose" and fclass != "prose":
            continue
        for m in rx.finditer(content):
            line_no = content.count("\n", 0, m.start()) + 1
            line_text = lines[line_no - 1] if line_no <= len(lines) else ""
            hit = {"rule": rule_id, "line": line_no, "snippet": line_text.strip()[:90]}
            if PRAGMA.search(line_text):
                overridden.append(hit)
            else:
                findings.append(hit)

    if overridden:
        log({"file": path, "action": "override", "hits": overridden})
    if not findings:
        return 0

    log({"file": path, "action": "block", "hits": findings})
    sys.stderr.write(
        f"QUALITY GATE: {len(findings)} slop pattern(s) blocked this write to {path}.\n"
        "Rewrite the flagged content without the pattern -- do not paraphrase around "
        "it with equivalent filler; state things plainly or cut them.\n"
    )
    for h in findings[:10]:
        sys.stderr.write(f"  [{h['rule']}] line {h['line']}: {h['snippet']}\n")
    sys.stderr.write(
        "If a flagged line is INTENTIONAL content (test data, authored persona text), "
        "append `slop-ok: <reason>` to that exact line -- overrides are logged and "
        "reviewed at retro.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
