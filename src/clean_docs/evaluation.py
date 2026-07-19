"""Run observable human tasks and replayable agent round trips."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from clean_docs.audit import audit
from clean_docs.engine import evaluate
from clean_docs.errors import CleanDocsError, ConfigurationError
from clean_docs.execution import resolve_argv
from clean_docs.manifest import load_manifest
from clean_docs.models import CommandSpec, Manifest
from clean_docs.regions import atomic_write


TASK_KEYS = {"id", "audience", "prompt", "context", "model", "scorer"}
MODEL_KEYS = {"adapter", "name", "response", "argv", "timeout_seconds"}
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 120
MAX_PROVIDER_TIMEOUT_SECONDS = 3600
SCORER_KEYS = {
    "command": {"type", "commands"},
    "structured-output": {"type", "expected"},
    "configuration": {"type", "repository"},
    "cited-limit": {"type", "answer", "citation", "forbidden"},
}
COMMAND_EXPECTATION_KEYS = {
    "ref", "documented_as", "exit_code", "stdout_contains", "stderr_contains"
}
ID = re.compile(r"^[a-z][a-z0-9-]*$")


class ResponseProvider(Protocol):
    @property
    def adapter(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def configuration_sha256(self) -> str: ...

    def complete(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class ModelSpec:
    adapter: str
    name: str
    response: Path | None = None
    argv: tuple[str, ...] = ()
    timeout_seconds: int = DEFAULT_PROVIDER_TIMEOUT_SECONDS


@dataclass(frozen=True)
class EvaluationTask:
    id: str
    audience: str
    prompt: str
    context: tuple[Path, ...]
    model: ModelSpec | None
    scorer: dict[str, Any]


@dataclass(frozen=True)
class TaskResult:
    id: str
    audience: str
    ok: bool
    scorer: str
    scorer_sha256: str
    claim: str
    corpus_sha256: str
    prompt_sha256: str
    response_sha256: str | None
    model: dict[str, str] | None
    detail: str


@dataclass(frozen=True)
class EvaluationReport:
    mode: str
    human_tasks: tuple[TaskResult, ...]
    agent_tasks: tuple[TaskResult, ...]
    hygiene_findings: tuple[dict[str, object], ...]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.human_tasks + self.agent_tasks)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "clean-docs.evaluation.v1",
            "mode": self.mode,
            "ok": self.ok,
            "scores": {
                "human": _score(self.human_tasks),
                "agent": _score(self.agent_tasks),
            },
            "human_tasks": [asdict(result) for result in self.human_tasks],
            "agent_tasks": [asdict(result) for result in self.agent_tasks],
            "hygiene_findings": list(self.hygiene_findings),
        }


@dataclass(frozen=True)
class RecordedResponseProvider:
    path: Path
    name: str
    adapter: str = "recorded"

    @property
    def configuration_sha256(self) -> str:
        return hashlib.sha256(str(self.path).encode()).hexdigest()

    def complete(self, prompt: str) -> str:
        del prompt
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(f"cannot read recorded response {self.path}: {exc}") from exc


@dataclass(frozen=True)
class CommandResponseProvider:
    argv: tuple[str, ...]
    name: str
    root: Path
    timeout_seconds: int = DEFAULT_PROVIDER_TIMEOUT_SECONDS
    adapter: str = "command"

    @property
    def configuration_sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "argv": self.argv,
                    "timeout_seconds": self.timeout_seconds,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def complete(self, prompt: str) -> str:
        try:
            proc = subprocess.run(
                resolve_argv(self.argv),
                cwd=self.root,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                env=_command_environment(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConfigurationError(f"provider command failed: {exc}") from exc
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip() or "no output"
            raise ConfigurationError(
                f"provider command exited {proc.returncode}: {detail}"
            )
        return proc.stdout


def _score(results: tuple[TaskResult, ...]) -> dict[str, int]:
    return {
        "passed": sum(result.ok for result in results),
        "attempted": len(results),
    }


def _command_environment() -> dict[str, str]:
    """Resolve sibling console scripts from the environment running clean-docs."""
    executable_dir = str(Path(sys.executable).parent)
    inherited_path = os.environ.get("PATH", "")
    path = executable_dir if not inherited_path else executable_dir + os.pathsep + inherited_path
    return {**os.environ, "NO_COLOR": "1", "PATH": path}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repository_state(root: Path, excluded: Path) -> tuple[str, str, int]:
    commit_process = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    commit = (
        commit_process.stdout.strip()
        if commit_process.returncode == 0
        else "unversioned"
    )
    try:
        excluded_relative = excluded.resolve().relative_to(root)
    except ValueError:
        excluded_relative = None
    digest = hashlib.sha256()
    count = 0
    candidates = sorted(
        path
        for path in root.rglob("*")
        if ".git" not in path.relative_to(root).parts
    )
    for candidate in candidates:
        relative_path = candidate.relative_to(root)
        relative = relative_path.as_posix()
        if (
            excluded_relative is not None
            and relative_path.is_relative_to(excluded_relative)
        ):
            continue
        if candidate.is_symlink():
            content = os.readlink(candidate).encode()
        elif candidate.is_file():
            content = candidate.read_bytes()
        else:
            continue
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
        count += 1
    return commit, digest.hexdigest(), count


def _provider_run_record(
    *,
    task: EvaluationTask,
    provider: ResponseProvider,
    commit: str,
    worktree_digest: str,
    worktree_files: int,
    corpus_digest: str,
    prompt_digest: str,
    prompt_bytes: int,
    scorer_digest: str,
) -> dict[str, object]:
    identity = {
        "task": task.id,
        "commit": commit,
        "corpus_sha256": corpus_digest,
        "prompt_sha256": prompt_digest,
        "scorer_sha256": scorer_digest,
        "provider": {
            "adapter": provider.adapter,
            "name": provider.name,
            "configuration_sha256": provider.configuration_sha256,
        },
    }
    run_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema": "clean-docs.provider-run.v1",
        "run_id": run_id,
        "idempotency_id": run_id,
        "task": task.id,
        "state": "invoking",
        "started_at": _utc_now(),
        "completed_at": None,
        "repository": {
            "commit": commit,
            "worktree_before_sha256": worktree_digest,
            "worktree_after_sha256": None,
            "files": worktree_files,
        },
        "inputs": {
            "corpus_sha256": corpus_digest,
            "prompt_sha256": prompt_digest,
            "prompt_bytes": prompt_bytes,
            "scorer_sha256": scorer_digest,
        },
        "provider": {
            "adapter": provider.adapter,
            "name": provider.name,
            "configuration_sha256": provider.configuration_sha256,
            "timeout_seconds": getattr(provider, "timeout_seconds", None),
        },
        "response_sha256": None,
        "error": None,
    }


def _complete_provider_run(
    record: dict[str, object],
    *,
    state: str,
    after_digest: str,
    response: str | None = None,
    error: CleanDocsError | None = None,
) -> dict[str, object]:
    updated = json.loads(json.dumps(record))
    updated["state"] = state
    updated["completed_at"] = _utc_now()
    repository = updated["repository"]
    assert isinstance(repository, dict)
    repository["worktree_after_sha256"] = after_digest
    if response is not None:
        updated["response_sha256"] = hashlib.sha256(response.encode()).hexdigest()
    if error is not None:
        updated["error"] = {
            "type": type(error).__name__,
            "detail_sha256": hashlib.sha256(str(error).encode()).hexdigest(),
        }
    return updated


def _mapping(raw: Any, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{where} must be a mapping")
    return raw


def _relative(raw: Any, where: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ConfigurationError(f"{where} must be a non-empty path")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{where} must stay inside the repository")
    return path


def _strings(raw: Any, where: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(raw, list) or (nonempty and not raw) or not all(
        isinstance(value, str) and value for value in raw
    ):
        qualifier = "non-empty " if nonempty else ""
        raise ConfigurationError(f"{where} must be a {qualifier}string list")
    return tuple(raw)


def _model(raw: Any, where: str) -> ModelSpec:
    data = _mapping(raw, where)
    unknown = sorted(set(data) - MODEL_KEYS)
    if unknown:
        raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")
    adapter = data.get("adapter")
    name = data.get("name")
    if adapter not in {"recorded", "command"}:
        raise ConfigurationError(f"{where}.adapter must be recorded or command")
    if not isinstance(name, str) or not name:
        raise ConfigurationError(f"{where}.name must be non-empty")
    if adapter == "recorded":
        command_only = sorted({"argv", "timeout_seconds"} & set(data))
        if command_only:
            raise ConfigurationError(
                f"{where}.{command_only[0]} is only valid for command adapters"
            )
        return ModelSpec(adapter, name, response=_relative(data.get("response"), f"{where}.response"))
    if "response" in data:
        raise ConfigurationError(f"{where}.response is only valid for recorded adapters")
    timeout_seconds = data.get(
        "timeout_seconds", DEFAULT_PROVIDER_TIMEOUT_SECONDS
    )
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS
    ):
        raise ConfigurationError(
            f"{where}.timeout_seconds must be an integer from 1 to "
            f"{MAX_PROVIDER_TIMEOUT_SECONDS}"
        )
    return ModelSpec(
        adapter,
        name,
        argv=_strings(data.get("argv"), f"{where}.argv", nonempty=True),
        timeout_seconds=timeout_seconds,
    )


def _scorer(raw: Any, where: str) -> dict[str, Any]:
    data = _mapping(raw, where)
    kind = data.get("type")
    if kind not in SCORER_KEYS:
        raise ConfigurationError(
            f"{where}.type must be command, configuration, structured-output, or cited-limit"
        )
    unknown = sorted(set(data) - SCORER_KEYS[kind])
    if unknown:
        raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")
    if kind == "command":
        commands = data.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ConfigurationError(f"{where}.commands must be a non-empty list")
        for index, candidate in enumerate(commands):
            command = _mapping(candidate, f"{where}.commands[{index}]")
            if set(command) != COMMAND_EXPECTATION_KEYS:
                raise ConfigurationError(
                    f"{where}.commands[{index}] must contain exactly: "
                    + ", ".join(sorted(COMMAND_EXPECTATION_KEYS))
                )
            if not isinstance(command["ref"], str) or not command["ref"]:
                raise ConfigurationError(f"{where}.commands[{index}].ref must be non-empty")
            if not isinstance(command["documented_as"], str) or not command["documented_as"]:
                raise ConfigurationError(
                    f"{where}.commands[{index}].documented_as must be non-empty"
                )
            if not isinstance(command["exit_code"], int):
                raise ConfigurationError(f"{where}.commands[{index}].exit_code must be an integer")
            _strings(command["stdout_contains"], f"{where}.commands[{index}].stdout_contains")
            _strings(command["stderr_contains"], f"{where}.commands[{index}].stderr_contains")
    elif kind == "configuration":
        _relative(data.get("repository"), f"{where}.repository")
    elif kind == "cited-limit":
        for field in ("answer", "citation"):
            if not isinstance(data.get(field), str) or not data[field]:
                raise ConfigurationError(f"{where}.{field} must be non-empty")
        _strings(data.get("forbidden", []), f"{where}.forbidden")
    return data


def load_evaluation_tasks(path: Path) -> tuple[EvaluationTask, ...]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read evaluation fixtures {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid evaluation fixture YAML: {exc}") from exc
    root = _mapping(raw, "evaluation fixtures")
    if set(root) != {"version", "tasks"} or root.get("version") != 1:
        raise ConfigurationError("evaluation fixtures must contain version 1 and tasks")
    raw_tasks = root.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ConfigurationError("evaluation fixtures.tasks must be a non-empty list")
    tasks: list[EvaluationTask] = []
    ids: set[str] = set()
    for index, raw_task in enumerate(raw_tasks):
        where = f"evaluation fixtures.tasks[{index}]"
        data = _mapping(raw_task, where)
        unknown = sorted(set(data) - TASK_KEYS)
        if unknown:
            raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")
        identifier = data.get("id")
        if not isinstance(identifier, str) or not ID.fullmatch(identifier):
            raise ConfigurationError(f"{where}.id must be a stable kebab-case identifier")
        if identifier in ids:
            raise ConfigurationError(f"duplicate evaluation task id: {identifier}")
        ids.add(identifier)
        audience = data.get("audience")
        if audience not in {"human", "agent"}:
            raise ConfigurationError(f"{where}.audience must be human or agent")
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ConfigurationError(f"{where}.prompt must be non-empty")
        context = tuple(
            _relative(value, f"{where}.context")
            for value in _strings(data.get("context"), f"{where}.context", nonempty=True)
        )
        model = _model(data.get("model"), f"{where}.model") if audience == "agent" else None
        if audience == "human" and data.get("model") is not None:
            raise ConfigurationError(f"{where}.model is only valid for agent tasks")
        scorer = _scorer(data.get("scorer"), f"{where}.scorer")
        if audience == "human" and scorer["type"] != "command":
            raise ConfigurationError(f"{where} human tasks must use the command scorer")
        if audience == "agent" and scorer["type"] == "command":
            raise ConfigurationError(f"{where} agent tasks cannot use the command scorer")
        tasks.append(EvaluationTask(identifier, audience, prompt.strip(), context, model, scorer))
    return tuple(tasks)


def _context(root: Path, task: EvaluationTask) -> tuple[str, str]:
    records = []
    digest = hashlib.sha256()
    for relative in task.context:
        try:
            content = (root / relative).read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(f"cannot read task context {relative}: {exc}") from exc
        records.append({"path": relative.as_posix(), "content": content})
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(content.encode())
    prompt = json.dumps({
        "schema": "clean-docs.round-trip.v1",
        "task": task.prompt,
        "context": records,
        "response_type": task.scorer["type"],
    }, sort_keys=True, separators=(",", ":"))
    return prompt, digest.hexdigest()


def _command_score(
    root: Path,
    manifest: Manifest,
    task: EvaluationTask,
) -> tuple[bool, str]:
    scorer = task.scorer
    commands = {command.id: command for command in manifest.commands}
    context = "\n".join((root / path).read_text(encoding="utf-8") for path in task.context)
    for index, expected in enumerate(scorer["commands"]):
        if expected["documented_as"] not in context:
            return False, (
                f"command {index + 1} is absent from supplied docs as "
                f"{expected['documented_as']!r}"
            )
        command: CommandSpec | None = commands.get(expected["ref"])
        if command is None:
            raise ConfigurationError(f"evaluation command is not allowlisted: {expected['ref']}")
        try:
            proc = subprocess.run(
                resolve_argv(command.argv),
                cwd=root,
                text=True,
                capture_output=True,
                timeout=command.timeout_seconds,
                check=False,
                env=_command_environment(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"command {index + 1} could not run: {exc}"
        if proc.returncode != expected["exit_code"]:
            return False, f"command {index + 1} exited {proc.returncode}"
        for stream, content in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            for required in expected[f"{stream}_contains"]:
                if required not in content:
                    return False, f"command {index + 1} {stream} omitted {required!r}"
    return True, f"{len(scorer['commands'])} documented command(s) matched expected output"


def _structured_score(response: str, scorer: dict[str, Any]) -> tuple[bool, str]:
    try:
        observed = json.loads(response)
    except json.JSONDecodeError:
        return False, "response is not valid JSON"
    if observed != scorer["expected"]:
        return False, "structured output does not match the expected value"
    return True, "structured output matches exactly"


def _configuration_score(
    root: Path, response: str, scorer: dict[str, Any]
) -> tuple[bool, str]:
    source = root / _relative(scorer["repository"], "configuration scorer repository")
    if not source.is_dir():
        raise ConfigurationError(f"configuration scorer repository does not exist: {source}")
    with tempfile.TemporaryDirectory(prefix="clean-docs-eval-config-") as temporary:
        destination = Path(temporary) / "repo"
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".git"))
        manifest_path = destination / ".clean-docs.yml"
        manifest_path.write_text(response, encoding="utf-8")
        try:
            load_manifest(manifest_path)
            results = evaluate(destination, manifest_path)
        except CleanDocsError as exc:
            return False, str(exc)
        if any(result.changed for result in results):
            return False, "configuration is valid but check reports drift"
    return True, "configuration passes schema validation and check"


def _cited_limit_score(
    root: Path, task: EvaluationTask, response: str, scorer: dict[str, Any]
) -> tuple[bool, str]:
    context = "\n".join((root / path).read_text(encoding="utf-8") for path in task.context)
    answer = scorer["answer"]
    citation = scorer["citation"]
    if answer.lower() not in context.lower():
        raise ConfigurationError(f"cited-limit answer is absent from task context: {answer}")
    citation_path, separator, citation_anchor = citation.partition("#")
    if not separator or not citation_path or not citation_anchor:
        raise ConfigurationError("cited-limit citation must be path#anchor")
    canonical = root / _relative(citation_path, "cited-limit citation path")
    try:
        canonical_text = canonical.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read cited limitation {citation_path}: {exc}") from exc
    anchors = {
        re.sub(r"[ _]+", "-", re.sub(r"[^a-z0-9 _-]", "", match.group(1).lower()))
        for line in canonical_text.splitlines()
        if (match := re.match(r"^#{1,6}\s+(.+?)\s*$", line))
    }
    if citation_anchor not in anchors:
        raise ConfigurationError(f"cited-limit anchor does not exist: {citation}")
    if answer.lower() not in response.lower():
        return False, "response omits the canonical limitation"
    if citation not in response:
        return False, "response omits the canonical citation"
    for forbidden in scorer.get("forbidden", []):
        if forbidden.lower() in response.lower():
            return False, f"response infers unsupported behavior: {forbidden}"
    return True, "response states and cites the canonical limitation"


def _provider(
    root: Path, task: EvaluationTask, mode: str
) -> ResponseProvider:
    assert task.model is not None
    model = task.model
    if mode == "replay":
        if model.adapter != "recorded" or model.response is None:
            raise ConfigurationError(
                f"replay mode requires a recorded response for task {task.id}"
            )
        return RecordedResponseProvider(root / model.response, model.name)
    if model.adapter != "command" or not model.argv:
        raise ConfigurationError(f"live mode requires a command adapter for task {task.id}")
    return CommandResponseProvider(
        model.argv,
        model.name,
        root,
        timeout_seconds=model.timeout_seconds,
    )


def run_evaluation(
    root: Path,
    manifest_path: Path,
    fixture_path: Path,
    *,
    mode: str = "replay",
    record_dir: Path | None = None,
) -> EvaluationReport:
    if mode not in {"replay", "live"}:
        raise ConfigurationError("evaluation mode must be replay or live")
    if mode == "live" and record_dir is None:
        raise ConfigurationError("live evaluation requires --record-dir")
    root = root.resolve()
    manifest = load_manifest(manifest_path)
    tasks = load_evaluation_tasks(fixture_path)
    results: list[TaskResult] = []
    for task in tasks:
        prompt, corpus_digest = _context(root, task)
        prompt_digest = hashlib.sha256(prompt.encode()).hexdigest()
        response = None
        model_record = None
        if task.audience == "human":
            ok, detail = _command_score(root, manifest, task)
            claim = "deterministic-command"
        else:
            provider = _provider(root, task, mode)
            if mode == "live":
                assert record_dir is not None
                scorer_digest = hashlib.sha256(json.dumps(
                    task.scorer, sort_keys=True, separators=(",", ":")
                ).encode()).hexdigest()
                commit, before_digest, worktree_files = _repository_state(
                    root, record_dir
                )
                run_path = record_dir / f"{task.id}.run.json"
                run_record = _provider_run_record(
                    task=task,
                    provider=provider,
                    commit=commit,
                    worktree_digest=before_digest,
                    worktree_files=worktree_files,
                    corpus_digest=corpus_digest,
                    prompt_digest=prompt_digest,
                    prompt_bytes=len(prompt.encode()),
                    scorer_digest=scorer_digest,
                )
                atomic_write(
                    run_path,
                    json.dumps(run_record, indent=2, sort_keys=True) + "\n",
                )
                try:
                    response = provider.complete(prompt)
                except CleanDocsError as exc:
                    _commit, after_digest, _files = _repository_state(
                        root, record_dir
                    )
                    state = (
                        "conflict"
                        if after_digest != before_digest
                        else "failed"
                    )
                    failed = _complete_provider_run(
                        run_record,
                        state=state,
                        after_digest=after_digest,
                        error=exc,
                    )
                    atomic_write(
                        run_path,
                        json.dumps(failed, indent=2, sort_keys=True) + "\n",
                    )
                    raise
                _commit, after_digest, _files = _repository_state(root, record_dir)
                if after_digest != before_digest:
                    conflict = _complete_provider_run(
                        run_record,
                        state="conflict",
                        after_digest=after_digest,
                        response=response,
                    )
                    atomic_write(
                        run_path,
                        json.dumps(conflict, indent=2, sort_keys=True) + "\n",
                    )
                    raise ConfigurationError(
                        f"provider changed repository bytes for task {task.id}"
                    )
                atomic_write(record_dir / f"{task.id}.txt", response)
                completed = _complete_provider_run(
                    run_record,
                    state="completed",
                    after_digest=after_digest,
                    response=response,
                )
                atomic_write(
                    run_path,
                    json.dumps(completed, indent=2, sort_keys=True) + "\n",
                )
            else:
                response = provider.complete(prompt)
            scorer_type = task.scorer["type"]
            if scorer_type == "structured-output":
                ok, detail = _structured_score(response, task.scorer)
            elif scorer_type == "configuration":
                ok, detail = _configuration_score(root, response, task.scorer)
            else:
                assert scorer_type == "cited-limit"
                ok, detail = _cited_limit_score(root, task, response, task.scorer)
            claim = "deterministic-replay" if mode == "replay" else "model-specific-live"
            model_record = {"adapter": provider.adapter, "name": provider.name}
        results.append(TaskResult(
            id=task.id,
            audience=task.audience,
            ok=ok,
            scorer=task.scorer["type"],
            scorer_sha256=hashlib.sha256(json.dumps(
                task.scorer, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest(),
            claim=claim,
            corpus_sha256=corpus_digest,
            prompt_sha256=prompt_digest,
            response_sha256=hashlib.sha256(response.encode()).hexdigest() if response is not None else None,
            model=model_record,
            detail=detail,
        ))
    audit_report = audit(root)
    hygiene = tuple(asdict(finding) for finding in audit_report.findings) + tuple(
        {**asdict(finding), "rule": "stale-baseline", "recorded_rule": finding.rule}
        for finding in audit_report.stale_baseline
    )
    return EvaluationReport(
        mode=mode,
        human_tasks=tuple(result for result in results if result.audience == "human"),
        agent_tasks=tuple(result for result in results if result.audience == "agent"),
        hygiene_findings=hygiene,
    )


def write_evaluation_history(path: Path, report: EvaluationReport) -> None:
    records = []
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"cannot read evaluation history {path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("schema") != "clean-docs.evaluation-history.v1":
            raise ConfigurationError("evaluation history has an unsupported schema")
        if not isinstance(raw.get("records"), list):
            raise ConfigurationError("evaluation history records must be a list")
        records.extend(raw["records"])
    for result in report.human_tasks + report.agent_tasks:
        record = asdict(result)
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        record["record_id"] = hashlib.sha256(payload.encode()).hexdigest()
        records.append(record)
    unique = {record["record_id"]: record for record in records}
    rendered = json.dumps({
        "schema": "clean-docs.evaluation-history.v1",
        "records": [unique[key] for key in sorted(unique)],
    }, indent=2, sort_keys=True) + "\n"
    atomic_write(path, rendered)
