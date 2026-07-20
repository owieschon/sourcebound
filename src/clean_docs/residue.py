from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.policy import PolicyFinding


CONFIG_NAME = ".sourcebound-residue.yml"
LOCAL_CONFIG_NAME = ".sourcebound-residue.local.yml"
ROOT_KEYS = {"version", "exclude", "rules"}
RULE_KEYS = {"id", "token_sha256", "include", "reason"}
LOCAL_RULE_KEYS = {"id", "token", "include"}
EXCLUDE_KEYS = {"pattern", "reason"}
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
POLICY_METADATA = re.compile(r"^\s*(?:-\s+)?(?:id|pattern|reason):\s*(?P<value>.*)$")
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
MAX_LOCAL_BYTES = 64 * 1024
MAX_LOCAL_RULES = 128


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


@dataclass(frozen=True)
class LocalResidueRule:
    id: str
    token: str
    include: tuple[str, ...]


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
    version = root.get("version")
    if version not in {1, 2}:
        raise ConfigurationError("residue config version must be 1 or 2")
    if version == 2 and "rules" in root:
        raise ConfigurationError("residue config version 2 permits exclusions only")

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


def load_local_residue_rules(path: Path) -> tuple[LocalResidueRule, ...]:
    """Load untracked plaintext residue rules without exposing their values."""
    if not path.exists():
        return ()
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ConfigurationError(f"cannot inspect local residue config: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ConfigurationError("local residue config must be a regular file")
    if os.name == "posix" and stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ConfigurationError("local residue config must have mode 0600")
    if metadata.st_size > MAX_LOCAL_BYTES:
        raise ConfigurationError("local residue config exceeds 64 KiB")
    try:
        root = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "local residue config")
    except OSError as exc:
        raise ConfigurationError(f"cannot read local residue config: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in local residue config: {exc}") from exc
    _reject_unknown(root, {"version", "rules"}, "local residue config")
    if root.get("version") != 1:
        raise ConfigurationError("local residue config version must be 1")
    raw_rules = root.get("rules", [])
    if not isinstance(raw_rules, list) or len(raw_rules) > MAX_LOCAL_RULES:
        raise ConfigurationError("local residue config permits at most 128 rules")
    rules = []
    identifiers: set[str] = set()
    for index, item in enumerate(raw_rules):
        where = f"local residue config rules[{index}]"
        data = _mapping(item, where)
        _reject_unknown(data, LOCAL_RULE_KEYS, where)
        identifier = _nonempty(data.get("id"), f"{where}.id")
        if identifier in identifiers:
            raise ConfigurationError(f"duplicate local residue rule id: {identifier}")
        identifiers.add(identifier)
        token = _nonempty(data.get("token"), f"{where}.token")
        include = data.get("include")
        if not isinstance(include, list) or not include or not all(isinstance(value, str) and value for value in include):
            raise ConfigurationError(f"{where}.include must be a non-empty string list")
        rules.append(LocalResidueRule(identifier, token.lower(), tuple(include)))
    return tuple(rules)


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


def _policy_metadata_findings(
    root: Path,
    path: Path,
    config: ResidueConfig,
    local_rules: tuple[LocalResidueRule, ...],
) -> list[PolicyFinding]:
    """Check public policy labels without exposing restricted rule material."""
    try:
        relative = path.resolve().relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return []
    findings = []
    for line_number, line in enumerate(lines, start=1):
        match = POLICY_METADATA.match(line)
        if match is None:
            continue
        tokens = {token.lower() for token in TOKEN.findall(match.group("value"))}
        digests = {
            hashlib.sha256(token.encode("utf-8")).hexdigest()
            for token in tokens
        }
        if any(rule.token_sha256 in digests for rule in config.rules) or any(
            rule.token in tokens for rule in local_rules
        ):
            findings.append(PolicyFinding(
                relative,
                line_number,
                "residue-policy-metadata",
                "remove restricted context from residue policy metadata",
            ))
    return findings


def scan_residue(root: Path, config_path: Path | None = None) -> list[PolicyFinding]:
    """Scan the tracked product surface for configured tokens and machine residue."""
    root = root.resolve()
    policy_path = config_path or root / CONFIG_NAME
    config = load_residue_config(policy_path)
    local_rules = load_local_residue_rules(root / LOCAL_CONFIG_NAME)
    findings = _policy_metadata_findings(root, policy_path, config, local_rules)
    exclusions = tuple(item.pattern for item in config.exclude)
    for path in _repository_files(root):
        relative = path.relative_to(root).as_posix()
        if relative == LOCAL_CONFIG_NAME:
            continue
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
            for local_rule in local_rules:
                if local_rule.token in {token.lower() for token in TOKEN.findall(line)} and _matches(relative, local_rule.include):
                    findings.append(PolicyFinding(
                        relative,
                        line_number,
                        "cross-project-residue",
                        f"remove token matched by local repository residue rule {local_rule.id!r}",
                    ))
    findings.sort(key=lambda finding: (finding.doc, finding.line, finding.rule, finding.detail))
    return findings
