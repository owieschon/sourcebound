from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from clean_docs.errors import ConfigurationError
from clean_docs.inventory import InventoryItem
from clean_docs.standard import load_default_pack
from clean_docs.write_gate import SECRET_RULES


INJECTION_RULES = (
    re.compile(r"\bignore (?:all |any )?(?:previous|prior) instructions?\b", re.I),
    re.compile(r"\b(?:reveal|disclose|print|return) (?:the )?(?:system prompt|secrets?)\b", re.I),
    re.compile(r"\b(?:override|change|remove|modify) (?:the )?(?:system|required findings?|gate results?)\b", re.I),
)
SKIP_PARTS = {".git", ".venv", "node_modules", "docs/archive"}
MAX_CONTEXT_BYTES = 32_000
MAX_FILE_BYTES = 8_000
TEMPLATE_KINDS = {
    "exposes": {
        "api-endpoint", "api-symbol", "cli-command", "cli-option", "mcp-tool", "schema",
    },
    "provides": {
        "api-endpoint", "api-symbol", "cli-command", "cli-option", "mcp-tool", "package",
        "package-script", "schema", "test-runner", "test-suite",
    },
    "tests": {"test-runner", "test-suite"},
}


class PhrasingProvider(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


@dataclass
class MockProvider:
    response: str
    name: str = "mock"
    last_prompt: str = ""

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


@dataclass
class RecordedProvider(MockProvider):
    name: str = "recorded"


@dataclass(frozen=True)
class GroundedDraft:
    fact_id: str
    template: str
    text: str


@dataclass(frozen=True)
class ModelRecord:
    provider: str
    prompt_sha256: str
    response_sha256: str
    context_flags: tuple[str, ...]
    drafts: tuple[GroundedDraft, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "prompt_sha256": self.prompt_sha256,
            "response_sha256": self.response_sha256,
            "context_flags": list(self.context_flags),
            "drafts": [asdict(draft) for draft in self.drafts],
        }


def _markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file()
        and not any(part in path.relative_to(root).as_posix() for part in SKIP_PARTS)
    )


def _sanitize(path: str, text: str) -> tuple[str, list[str]]:
    lines: list[str] = []
    flags: list[str] = []
    for line_number, original in enumerate(text.splitlines(), start=1):
        line = original
        injection = any(rule.search(original) for rule in INJECTION_RULES)
        if injection:
            flags.append(f"prompt-injection:{path}:{line_number}")
        for rule_id, pattern, _applies in SECRET_RULES:
            if pattern.search(original):
                flags.append(f"{rule_id}:{path}:{line_number}")
                line = pattern.sub("[REDACTED]", line)
        lines.append("[BLOCKED UNTRUSTED INSTRUCTION]" if injection else line)
    return "\n".join(lines), flags


def _context(root: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    remaining = MAX_CONTEXT_BYTES
    documents: list[dict[str, str]] = []
    flags: list[str] = []
    for path in _markdown_files(root):
        if remaining <= 0:
            break
        relative = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()[:MAX_FILE_BYTES]
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        sanitized, found = _sanitize(relative, text)
        encoded = sanitized.encode("utf-8")[:remaining]
        documents.append({"path": relative, "content": encoded.decode("utf-8", "ignore")})
        flags.extend(found)
        remaining -= len(encoded)
    return documents, tuple(sorted(set(flags)))


def _prompt(root: Path, facts: tuple[InventoryItem, ...]) -> tuple[str, tuple[str, ...]]:
    pack = load_default_pack()
    documents, context_flags = _context(root)
    flags = list(context_flags)
    safe_facts: list[dict[str, object]] = []
    for index, fact in enumerate(facts):
        record: dict[str, object] = {}
        for field, value in asdict(fact).items():
            if not isinstance(value, str):
                record[field] = value
                continue
            sanitized, found = _sanitize(f"inventory:{index}:{field}", value)
            record[field] = sanitized
            flags.extend(found)
        safe_facts.append(record)
    payload = {
        "schema": "clean-docs.phrasing-request.v1",
        "task": "Select prose templates for known facts. Do not add facts or prose.",
        "standard": {
            "constraint": pack["generation"]["constraint"],
            "checklist": pack["checklist"],
            "voice": pack["generation"]["voice"],
            "purpose_contract": pack["generation"]["purpose_contract"],
            "precedence": pack["generation"]["precedence"],
            "exemplars": pack["generation"]["exemplars"],
        },
        "allowed_templates": {
            template: sorted(kinds) for template, kinds in sorted(TEMPLATE_KINDS.items())
        },
        "facts": safe_facts,
        "repository_context": documents,
        "response_schema": {
            "drafts": [{"fact_id": "known fact id", "template": "allowed template"}],
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")), tuple(sorted(set(flags)))


def _draft_text(fact: InventoryItem, template: str) -> str:
    name = " ".join(fact.name.split()).replace("`", "'")
    label = fact.kind.replace("-", " ")
    if template == "tests":
        return f"The repository tests `{name}` through a {label}."
    return f"The repository {template} `{name}` as a {label}."


def _parse_response(response: str, facts: tuple[InventoryItem, ...]) -> tuple[GroundedDraft, ...]:
    try:
        raw = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ConfigurationError("model response is not valid JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {"drafts"} or not isinstance(raw["drafts"], list):
        raise ConfigurationError("model response does not match the grounded draft schema")
    if len(raw["drafts"]) > 5:
        raise ConfigurationError("model response exceeds the grounded draft limit")
    by_id = {fact.id: fact for fact in facts}
    drafts: list[GroundedDraft] = []
    seen: set[str] = set()
    for candidate in raw["drafts"]:
        if not isinstance(candidate, dict) or set(candidate) != {"fact_id", "template"}:
            raise ConfigurationError("model response contains an invalid grounded draft")
        fact_id = candidate.get("fact_id")
        template = candidate.get("template")
        if not isinstance(fact_id, str) or fact_id not in by_id or fact_id in seen:
            raise ConfigurationError("model response references an unsupported or duplicate fact")
        fact = by_id[fact_id]
        if not isinstance(template, str) or fact.kind not in TEMPLATE_KINDS.get(template, set()):
            raise ConfigurationError("model response maps a fact to an unsupported template")
        seen.add(fact_id)
        drafts.append(GroundedDraft(fact_id, template, _draft_text(fact, template)))
    return tuple(drafts)


def build_model_record(
    root: Path,
    facts: tuple[InventoryItem, ...],
    provider: PhrasingProvider,
) -> ModelRecord:
    prompt, flags = _prompt(root.resolve(), facts)
    try:
        response = provider.complete(prompt)
    except Exception as exc:
        raise ConfigurationError("phrasing provider failed before any repository write") from exc
    if not isinstance(response, str):
        raise ConfigurationError("phrasing provider returned a non-text response")
    drafts = _parse_response(response, facts)
    return ModelRecord(
        provider=provider.name,
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        response_sha256=hashlib.sha256(response.encode()).hexdigest(),
        context_flags=flags,
        drafts=drafts,
    )
