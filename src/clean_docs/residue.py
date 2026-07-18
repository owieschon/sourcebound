from __future__ import annotations

import fnmatch
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.policy import PolicyFinding


CONFIG_NAME = ".clean-docs-residue.yml"
ROOT_KEYS = {"version", "exclude", "rules"}
RULE_KEYS = {"id", "token_sha256", "include", "reason"}
EXCLUDE_KEYS = {"pattern", "reason"}
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
LOCAL_PATH = re.compile(
    r"(?<![A-Za-z0-9_])/(?:Users|home)/(?P<owner>[^/\s]+)/"
)
LOCAL_PATH_PLACEHOLDERS = {
    "example",
    "me",
    "user",
    "username",
    "you",
    "your_username",
}
SHA256 = re.compile(r"[0-9a-f]{64}")
GENERATED_PARTS = {"__pycache__", ".DS_Store"}
GENERATED_SUFFIXES = {".pyc", ".pyo"}
MAX_TEXT_BYTES = 1_000_000


@dataclass(frozen=True)
class ResidueRule:
    id: str
    token_sha256: str
    include: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ResidueExclusion:
    pattern: str
    reason: str


@dataclass(frozen=True)
class ResidueConfig:
    rules: tuple[ResidueRule, ...]
    exclude: tuple[ResidueExclusion, ...]


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be a mapping")
    return value


def _nonempty(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{where} must be a non-empty string")
    return value.strip()


def _reject_unknown(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")


def load_residue_config(path: Path) -> ResidueConfig:
    if not path.exists():
        return ResidueConfig((), ())
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read residue config {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in residue config {path}: {exc}") from exc
    root = _mapping(raw, "residue config")
    _reject_unknown(root, ROOT_KEYS, "residue config")
    if root.get("version") != 1:
        raise ConfigurationError("residue config version must be 1")

    rules = []
    identifiers: set[str] = set()
    raw_rules = root.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ConfigurationError("residue config rules must be a list")
    for index, item in enumerate(raw_rules):
        where = f"residue config rules[{index}]"
        data = _mapping(item, where)
        _reject_unknown(data, RULE_KEYS, where)
        identifier = _nonempty(data.get("id"), f"{where}.id")
        if identifier in identifiers:
            raise ConfigurationError(f"duplicate residue rule id: {identifier}")
        identifiers.add(identifier)
        digest = _nonempty(data.get("token_sha256"), f"{where}.token_sha256")
        if not SHA256.fullmatch(digest):
            raise ConfigurationError(f"{where}.token_sha256 must be a lowercase SHA-256")
        include = data.get("include")
        if not isinstance(include, list) or not include or not all(
            isinstance(pattern, str) and pattern for pattern in include
        ):
            raise ConfigurationError(f"{where}.include must be a non-empty string list")
        reason = _nonempty(data.get("reason"), f"{where}.reason")
        if len(reason) < 12:
            raise ConfigurationError(f"{where}.reason must explain the exclusion")
        rules.append(ResidueRule(identifier, digest, tuple(include), reason))

    exclusions = []
    raw_exclusions = root.get("exclude", [])
    if not isinstance(raw_exclusions, list):
        raise ConfigurationError("residue config exclude must be a list")
    for index, item in enumerate(raw_exclusions):
        where = f"residue config exclude[{index}]"
        data = _mapping(item, where)
        _reject_unknown(data, EXCLUDE_KEYS, where)
        pattern = _nonempty(data.get("pattern"), f"{where}.pattern")
        reason = _nonempty(data.get("reason"), f"{where}.reason")
        if len(reason) < 12:
            raise ConfigurationError(f"{where}.reason must explain the exclusion")
        exclusions.append(ResidueExclusion(pattern, reason))
    return ResidueConfig(tuple(rules), tuple(exclusions))


def _repository_files(root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [root / path for path in proc.stdout.decode().split("\0") if path]
    skipped = {".git", ".venv", "node_modules", "build", "dist", "__pycache__"}
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and not set(path.relative_to(root).parts) & skipped
    )


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _machine_path_match(line: str) -> bool:
    for match in LOCAL_PATH.finditer(line):
        owner = match.group("owner").strip("<>{}$").lower()
        if owner not in LOCAL_PATH_PLACEHOLDERS:
            return True
    return False


def scan_residue(root: Path, config_path: Path | None = None) -> list[PolicyFinding]:
    """Scan the tracked product surface for configured tokens and machine residue."""
    root = root.resolve()
    config = load_residue_config(config_path or root / CONFIG_NAME)
    findings = []
    exclusions = tuple(item.pattern for item in config.exclude)
    for path in _repository_files(root):
        relative = path.relative_to(root).as_posix()
        if _matches(relative, exclusions):
            continue
        if set(path.parts) & GENERATED_PARTS or path.suffix in GENERATED_SUFFIXES:
            findings.append(PolicyFinding(
                relative, 1, "generated-artifact", "remove generated runtime residue from git"
            ))
            continue
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if len(content) > MAX_TEXT_BYTES or b"\0" in content:
            continue
        text = content.decode("utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _machine_path_match(line):
                findings.append(PolicyFinding(
                    relative,
                    line_number,
                    "local-path-residue",
                    "replace the machine-specific home path with a repository-relative path",
                ))
            digests = {
                hashlib.sha256(token.lower().encode("utf-8")).hexdigest()
                for token in TOKEN.findall(line)
            }
            for rule in config.rules:
                if rule.token_sha256 in digests and _matches(relative, rule.include):
                    findings.append(PolicyFinding(
                        relative,
                        line_number,
                        "cross-project-residue",
                        f"remove token matched by repository residue rule {rule.id!r}",
                    ))
    findings.sort(key=lambda finding: (finding.doc, finding.line, finding.rule, finding.detail))
    return findings
