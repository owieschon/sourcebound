from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from sourcebound.errors import ConfigurationError
from sourcebound.execution import run_bounded_command
from sourcebound.inventory import InventoryItem
from sourcebound.regions import atomic_write
from sourcebound.standard import load_default_pack
from sourcebound.write_gate import SECRET_RULES, redact_secrets


INJECTION_RULES = (
    re.compile(r"\bignore (?:all |any )?(?:previous|prior) instructions?\b", re.I),
    re.compile(r"\b(?:reveal|disclose|print|return) (?:the )?(?:system prompt|secrets?)\b", re.I),
    re.compile(r"\b(?:override|change|remove|modify) (?:the )?(?:system|required findings?|gate results?)\b", re.I),
)
SKIP_PARTS = {".git", ".venv", "node_modules", "docs/archive"}
MAX_CONTEXT_BYTES = 32_000
MAX_FILE_BYTES = 8_000
MAX_PROVIDER_OUTPUT_BYTES = 1_000_000
MAX_PROVIDER_INPUT_BYTES = 1_000_000
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 120
MAX_PROVIDER_TIMEOUT_SECONDS = 3600
MODEL_KEYS = {"adapter", "name", "response", "argv", "timeout_seconds", "env"}
TEMPLATE_KINDS = {
    "exposes": {
        "api-endpoint", "api-symbol", "cli-command", "cli-option", "mcp-tool", "schema",
    },
    "provides": {
        "api-endpoint", "api-symbol", "cli-command", "cli-option", "mcp-tool", "package",
        "make-target", "package-script", "schema", "test-runner", "test-suite",
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


@dataclass
class CommandPhrasingProvider:
    """Run an explicitly configured init proposer without granting it write authority."""

    argv: tuple[str, ...]
    name: str
    root: Path
    timeout_seconds: int = DEFAULT_PROVIDER_TIMEOUT_SECONDS
    env_names: tuple[str, ...] = ()
    last_prompt: str | None = None
    last_response: str | None = None
    last_duration_seconds: float | None = None
    last_prompt_bytes: int | None = None
    last_response_bytes: int | None = None
    last_error: str | None = None
    last_parser_accepted: bool = False
    last_model_record: ModelRecord | None = None

    @property
    def configuration_sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "argv": self.argv,
                    "timeout_seconds": self.timeout_seconds,
                    "env": self.env_names,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        request = prompt.encode()
        environment = {"NO_COLOR": "1", "PATH": os.defpath}
        for name in self.env_names:
            value = os.environ.get(name)
            if value is None:
                raise ConfigurationError(f"init proposer environment variable is unset: {name}")
            environment[name] = value
        try:
            result = run_bounded_command(
                self.argv,
                environment=environment,
                input_bytes=request,
                timeout_seconds=self.timeout_seconds,
                max_input_bytes=MAX_PROVIDER_INPUT_BYTES,
                max_output_bytes=MAX_PROVIDER_OUTPUT_BYTES,
                prefix="sourcebound-init-proposer",
            )
        except ConfigurationError as exc:
            self.last_error = str(exc)
            raise
        try:
            response = result.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            self.last_error = "init proposer returned non-UTF-8 output"
            raise ConfigurationError(self.last_error) from exc
        self.last_response = response
        self.last_duration_seconds = result.duration_seconds
        self.last_prompt_bytes = len(request)
        self.last_response_bytes = len(result.stdout)
        return response


def load_command_phrasing_provider(path: Path, root: Path) -> CommandPhrasingProvider:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"cannot read init proposer config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("init proposer config must be a mapping")
    unknown = sorted(set(raw) - MODEL_KEYS)
    if unknown:
        raise ConfigurationError(
            "init proposer config has unknown key(s): " + ", ".join(unknown)
        )
    if raw.get("adapter") != "command":
        raise ConfigurationError("init proposer config.adapter must be command")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ConfigurationError("init proposer config.name must be non-empty")
    if "response" in raw:
        raise ConfigurationError(
            "init proposer config.response is only valid for recorded adapters"
        )
    argv = raw.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(value, str) and value for value in argv)
    ):
        raise ConfigurationError("init proposer config.argv must be a non-empty string list")
    executable = argv[0]
    if executable != "{python}" and not Path(executable).is_absolute():
        raise ConfigurationError(
            "init proposer config.argv[0] must be an absolute path or {python}"
        )
    if "{python}" in argv[1:]:
        raise ConfigurationError(
            "init proposer config may use {python} only as argv[0]"
        )
    timeout_seconds = raw.get("timeout_seconds", DEFAULT_PROVIDER_TIMEOUT_SECONDS)
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS
    ):
        raise ConfigurationError(
            "init proposer config.timeout_seconds must be an integer from 1 to "
            f"{MAX_PROVIDER_TIMEOUT_SECONDS}"
        )
    env = raw.get("env", [])
    if not isinstance(env, list) or not all(
        isinstance(value, str) and value and value.isidentifier() for value in env
    ) or len(set(env)) != len(env):
        raise ConfigurationError("init proposer config.env must be unique environment variable names")
    if "PATH" in env:
        raise ConfigurationError(
            "init proposer config.env cannot grant PATH; Sourcebound supplies a fixed PATH"
        )
    return CommandPhrasingProvider(tuple(argv), name, root, timeout_seconds, tuple(env))


def write_command_proposer_transcript(
    root: Path,
    path: Path,
    provider: CommandPhrasingProvider,
    *,
    state: str,
    outcome: str,
    detail: str,
    record: ModelRecord | None = None,
) -> None:
    target = validate_command_proposer_transcript_path(root, path)
    response = provider.last_response
    redacted_response = redact_secrets(response)[0] if response is not None else None
    candidates: list[dict[str, object]] = []
    if response is not None:
        try:
            raw = json.loads(response)
        except json.JSONDecodeError:
            raw = None
        if isinstance(raw, dict) and isinstance(raw.get("drafts"), list):
            candidates = [
                {
                    "fact_id": item.get("fact_id") if isinstance(item, dict) else None,
                    "template": item.get("template") if isinstance(item, dict) else None,
                    "decision": "accepted" if outcome == "accept" else "rejected",
                }
                for item in raw["drafts"]
            ]
    payload: dict[str, Any] = {
        "schema": "sourcebound.init-proposer-transcript.v1",
        "state": state,
        "outcome": outcome,
        "detail": detail,
        "provider": {
            "name": provider.name,
            "configuration_sha256": provider.configuration_sha256,
            "timeout_seconds": provider.timeout_seconds,
            "env_names": list(provider.env_names),
            "granted_env_names": sorted({"PATH", "NO_COLOR", *provider.env_names}),
        },
        "cost": {
            "prompt_bytes": provider.last_prompt_bytes,
            "response_bytes": provider.last_response_bytes,
            "duration_seconds": provider.last_duration_seconds,
        },
        "prompt": (
            redact_secrets(provider.last_prompt)[0]
            if provider.last_prompt is not None
            else None
        ),
        "prompt_sha256": (
            hashlib.sha256(provider.last_prompt.encode()).hexdigest()
            if provider.last_prompt is not None
            else None
        ),
        "response": redacted_response,
        "response_sha256": (
            hashlib.sha256(response.encode()).hexdigest() if response is not None else None
        ),
        "candidates": candidates,
        "model_record": record.as_dict() if record is not None else None,
    }
    atomic_write(target, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def validate_command_proposer_transcript_path(root: Path, path: Path) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError("init proposer transcript must stay inside the repository")
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ConfigurationError("init proposer transcript must stay inside the repository")
    return target


def prepare_command_proposer_transcript_path(root: Path, path: Path) -> Path:
    """Prove the transcript target is writable without leaving repository state behind."""
    target = validate_command_proposer_transcript_path(root, path)
    if target.exists() and target.is_dir():
        raise ConfigurationError("init proposer transcript path is a directory")
    created: list[Path] = []
    cursor = target.parent
    missing: list[Path] = []
    while not cursor.exists():
        missing.append(cursor)
        if cursor == root:
            break
        cursor = cursor.parent
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        for parent in reversed(missing):
            if parent.exists():
                created.append(parent)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        os.close(descriptor)
        Path(temporary).unlink()
    except OSError as exc:
        raise ConfigurationError(f"cannot write init proposer transcript {path}: {exc}") from exc
    finally:
        for parent in sorted(created, key=lambda item: len(item.parts), reverse=True):
            try:
                parent.rmdir()
            except OSError:
                pass
    return target


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
        "schema": "sourcebound.phrasing-request.v1",
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
    record = ModelRecord(
        provider=provider.name,
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        response_sha256=hashlib.sha256(response.encode()).hexdigest(),
        context_flags=flags,
        drafts=drafts,
    )
    if isinstance(provider, CommandPhrasingProvider):
        provider.last_parser_accepted = True
        provider.last_model_record = record
    return record
