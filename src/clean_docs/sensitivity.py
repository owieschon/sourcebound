"""Prove that one static documentation check depends on one selected source fact."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from clean_docs.claims import extract_source_facts, scan_source_claims
from clean_docs.errors import ConfigurationError
from clean_docs.models import SourceClaimCheck


PROPOSAL_SCHEMA = "sourcebound.binding-proposal.v1"
FACT_SCHEMA = "sourcebound.mutation-target.v1"
RECEIPT_SCHEMA = "sourcebound.binding-sensitivity.v1"
GENERATOR = "python-identifier-set-key@1"
MAX_INPUT_BYTES = 1_048_576
ID = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
PROPOSAL_KEYS = {"schema", "repository_commit", "relationship"}
RELATIONSHIP_KEYS = {
    "id",
    "kind",
    "doc",
    "anchor",
    "subject",
    "source",
    "locator",
}
FACT_KEYS = {
    "schema",
    "repository_commit",
    "selection_basis",
    "kind",
    "source",
    "locator",
    "member",
    "value_sha256",
}
FACT_SELECTION_BASES = {"configured-source-claim", "frozen-evaluation-fact"}


class UnsupportedMutation(Exception):
    """The selected static fact has no safe first-party mutation."""


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _mapping(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be a mapping")
    return value


def _exact_keys(data: dict[str, Any], expected: set[str], where: str) -> None:
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing:
        raise ConfigurationError(f"{where} is missing key(s): {', '.join(missing)}")
    if unknown:
        raise ConfigurationError(f"{where} has unknown key(s): {', '.join(unknown)}")


def _nonempty(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{where} must be a non-empty string")
    if len(value) > 4096 or "\0" in value:
        raise ConfigurationError(f"{where} exceeds the supported text boundary")
    return value


def _relative(value: object, where: str) -> Path:
    raw = _nonempty(value, where)
    path = Path(raw)
    if path == Path(".") or path.is_absolute() or ".." in path.parts or ":" in raw:
        raise ConfigurationError(f"{where} must stay inside the repository")
    return path


def _validate_proposal(raw: object) -> dict[str, Any]:
    proposal = _mapping(raw, "proposal")
    _exact_keys(proposal, PROPOSAL_KEYS, "proposal")
    if proposal["schema"] != PROPOSAL_SCHEMA:
        raise ConfigurationError(f"proposal.schema must be {PROPOSAL_SCHEMA}")
    commit = _nonempty(proposal["repository_commit"], "proposal.repository_commit")
    if not HEX_COMMIT.fullmatch(commit):
        raise ConfigurationError("proposal.repository_commit must be a full hexadecimal commit")
    relationship = _mapping(proposal["relationship"], "proposal.relationship")
    _exact_keys(relationship, RELATIONSHIP_KEYS, "proposal.relationship")
    identifier = _nonempty(relationship["id"], "proposal.relationship.id")
    if len(identifier) > 128 or not ID.fullmatch(identifier):
        raise ConfigurationError("proposal.relationship.id must be kebab-case")
    if relationship["kind"] != "identifier-set":
        raise ConfigurationError(
            "proposal.relationship.kind must be identifier-set in this release"
        )
    source = _relative(relationship["source"], "proposal.relationship.source")
    if source.suffix != ".py":
        raise ConfigurationError(
            "proposal.relationship.source must be a Python file in this release"
        )
    doc = _relative(relationship["doc"], "proposal.relationship.doc")
    if doc.suffix.lower() not in {".md", ".mdx"}:
        raise ConfigurationError(
            "proposal.relationship.doc must be Markdown or MDX in this release"
        )
    for field in ("anchor", "subject", "locator"):
        _nonempty(relationship[field], f"proposal.relationship.{field}")
    return proposal


def _validate_fact(raw: object) -> dict[str, Any]:
    fact = _mapping(raw, "fact")
    _exact_keys(fact, FACT_KEYS, "fact")
    if fact["schema"] != FACT_SCHEMA:
        raise ConfigurationError(f"fact.schema must be {FACT_SCHEMA}")
    commit = _nonempty(fact["repository_commit"], "fact.repository_commit")
    if not HEX_COMMIT.fullmatch(commit):
        raise ConfigurationError("fact.repository_commit must be a full hexadecimal commit")
    if fact["selection_basis"] not in FACT_SELECTION_BASES:
        raise ConfigurationError(
            "fact.selection_basis must be configured-source-claim or "
            "frozen-evaluation-fact"
        )
    if fact["kind"] != "identifier-set":
        raise ConfigurationError("fact.kind must be identifier-set in this release")
    _relative(fact["source"], "fact.source")
    for field in ("locator", "member"):
        _nonempty(fact[field], f"fact.{field}")
    digest = _nonempty(fact["value_sha256"], "fact.value_sha256")
    if not HEX_SHA256.fullmatch(digest):
        raise ConfigurationError("fact.value_sha256 must be a lowercase SHA-256 digest")
    return fact


def decode_json_object(raw: bytes, where: str) -> dict[str, Any]:
    if len(raw) > MAX_INPUT_BYTES:
        raise ConfigurationError(f"{where} exceeds {MAX_INPUT_BYTES} bytes")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{where} is not valid JSON: {exc}") from exc
    return _mapping(value, where)


def load_json_object(path: Path, where: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigurationError(f"cannot read {where} {path}: {exc}") from exc
    return decode_json_object(raw, where), raw


def _git(root: Path, *args: str) -> bytes:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(f"cannot inspect repository state: {exc}") from exc
    if process.returncode != 0:
        detail = process.stderr.decode(errors="replace").strip()
        raise ConfigurationError(detail or f"git {' '.join(args)} failed")
    return process.stdout


def _worktree_status(root: Path, excluded: Path | None) -> bytes:
    arguments = [
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    ]
    if excluded is not None:
        try:
            relative = excluded.resolve().relative_to(root)
        except ValueError:
            relative = None
        if relative is not None:
            arguments.extend(("--", ".", f":(exclude){relative.as_posix()}"))
    return _git(root, *arguments)


def _tracked_text(root: Path, commit: str, path: Path) -> tuple[str, str, str]:
    relative = path.as_posix()
    tree = _git(root, "ls-tree", "-z", commit, "--", relative)
    if not tree:
        raise ConfigurationError(f"selected path is not tracked at {commit}: {relative}")
    header, separator, _name = tree.partition(b"\t")
    if not separator:
        raise ConfigurationError(f"cannot inspect selected path mode: {relative}")
    fields = header.split(b" ")
    if len(fields) != 3:
        raise ConfigurationError(f"cannot inspect selected path object: {relative}")
    mode, _kind, object_id = fields
    if mode not in {b"100644", b"100755"}:
        raise ConfigurationError(f"selected path is not a regular file: {relative}")
    content = _git(root, "show", f"{commit}:{relative}")
    try:
        return (
            content.decode("utf-8"),
            _bytes_sha256(content),
            object_id.decode(),
        )
    except UnicodeDecodeError as exc:
        raise ConfigurationError(f"selected path is not UTF-8 text: {relative}") from exc


def _assignment(tree: ast.Module, symbol: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == symbol
                for target in node.targets
            ):
                return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == symbol
            and node.value is not None
        ):
            return node.value
    raise UnsupportedMutation(f"static assignment not found: {symbol}")


def _mapping_node(text: str, locator: str) -> ast.Dict:
    if not locator.endswith("#keys"):
        raise UnsupportedMutation("identifier-set locator must end in #keys")
    parts = locator.removesuffix("#keys").split(".")
    if len(parts) not in {1, 2} or any(not part for part in parts):
        raise UnsupportedMutation("identifier-set locator shape is unsupported")
    try:
        value = _assignment(ast.parse(text), parts[0])
    except SyntaxError as exc:
        raise UnsupportedMutation(f"selected Python source does not parse: {exc}") from exc
    if len(parts) == 1 and isinstance(value, ast.Dict):
        return value
    if len(parts) == 2 and isinstance(value, ast.Call):
        matches = [
            keyword.value
            for keyword in value.keywords
            if keyword.arg == parts[1] and isinstance(keyword.value, ast.Dict)
        ]
        if len(matches) == 1:
            return matches[0]
    raise UnsupportedMutation("selected identifier set is not a static mapping")


def _mutate_identifier(
    text: str,
    locator: str,
    member: str,
) -> tuple[str, dict[str, object]]:
    mapping = _mapping_node(text, locator)
    matches = [
        key
        for key in mapping.keys
        if isinstance(key, ast.Constant) and key.value == member
    ]
    if len(matches) != 1:
        raise UnsupportedMutation(
            f"selected member must resolve to exactly one mapping key; found {len(matches)}"
        )
    key = matches[0]
    if (
        key.end_lineno is None
        or key.end_col_offset is None
        or key.lineno != key.end_lineno
    ):
        raise UnsupportedMutation("multiline mapping keys are unsupported")
    replacement_value = f"{member}__clean_docs_probe"
    existing = {
        candidate.value
        for candidate in mapping.keys
        if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str)
    }
    if replacement_value in existing:
        raise UnsupportedMutation("deterministic replacement key already exists")
    source = text.encode("utf-8")
    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: key.lineno - 1]) + key.col_offset
    end = sum(len(line) for line in lines[: key.end_lineno - 1]) + key.end_col_offset
    replacement = json.dumps(replacement_value).encode()
    mutated_bytes = source[:start] + replacement + source[end:]
    try:
        mutated = mutated_bytes.decode("utf-8")
        ast.parse(mutated)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise UnsupportedMutation(f"generated mutation is not valid Python: {exc}") from exc
    plan = {
        "generator": GENERATOR,
        "class": "rename-mapping-member",
        "member": member,
        "replacement": replacement_value,
        "reversal": {
            "byte_range": {
                "start": start,
                "end": start + len(replacement),
            },
            "replacement": json.dumps(member),
        },
        "line": key.lineno,
        "byte_range": {"start": start, "end": end},
        "before_sha256": _bytes_sha256(source),
        "after_sha256": _bytes_sha256(mutated_bytes),
        "target_execution_required": False,
    }
    return mutated, {**plan, "plan_sha256": _canonical_sha256(plan)}


def _relationship_check(relationship: dict[str, Any]) -> SourceClaimCheck:
    return SourceClaimCheck(
        id=relationship["id"],
        kind=relationship["kind"],
        doc=Path(relationship["doc"]),
        anchor=relationship["anchor"],
        subject=relationship["subject"],
        source=Path(relationship["source"]),
        locator=relationship["locator"],
    )


def _observed_status(root: Path, check: SourceClaimCheck) -> tuple[str, dict[str, object] | None]:
    report = scan_source_claims(root, (check,), discover=False)
    if report.missing or len(report.results) != 1:
        return "missing", None
    result = report.results[0]
    return result.status, result.as_dict()


def _base_receipt(
    *,
    state: str,
    proposal: dict[str, Any],
    fact: dict[str, Any],
    proposal_bytes: bytes,
    fact_bytes: bytes,
    fact_file_sha256: str,
    commit: str,
    head_after: str,
    status_before: bytes,
    status_after: bytes,
    detail: str,
) -> dict[str, object]:
    return {
        "schema": RECEIPT_SCHEMA,
        "state": state,
        "sensitive": state == "sensitive",
        "semantic_relationship_authorized": False,
        "detail": detail,
        "repository": {
            "commit": commit,
            "head_after": head_after,
            "clean_before": not status_before,
            "clean_after": not status_after,
            "status_before_sha256": _bytes_sha256(status_before),
            "status_after_sha256": _bytes_sha256(status_after),
            "caller_worktree_unchanged": status_before == status_after,
            "caller_repository_unchanged": (
                status_before == status_after and head_after == commit
            ),
        },
        "inputs": {
            "proposal_sha256": _bytes_sha256(proposal_bytes),
            "fact_sha256": _bytes_sha256(fact_bytes),
            "expected_fact_file_sha256": fact_file_sha256,
            "relationship": proposal["relationship"],
            "fact_selection_basis": fact["selection_basis"],
            "fact_value_sha256": fact["value_sha256"],
        },
        "execution": {
            "disposable_copy": True,
            "target_code_executed": False,
            "repository_commands_executed": False,
            "caller_files_written": 0,
        },
    }


def evaluate_binding_sensitivity(
    root: Path,
    proposal_raw: object,
    fact_raw: object,
    *,
    proposal_bytes: bytes,
    fact_bytes: bytes,
    expected_fact_file_sha256: str,
    excluded_worktree_path: Path | None = None,
) -> dict[str, object]:
    """Return a read-only dependency-sensitivity receipt for one static relationship."""
    root = root.resolve()
    proposal = _validate_proposal(proposal_raw)
    fact = _validate_fact(fact_raw)
    if len(proposal_bytes) > MAX_INPUT_BYTES or len(fact_bytes) > MAX_INPUT_BYTES:
        raise ConfigurationError(
            f"proposal and fact inputs must each be at most {MAX_INPUT_BYTES} bytes"
        )
    if not HEX_SHA256.fullmatch(expected_fact_file_sha256):
        raise ConfigurationError("expected fact file digest must be a lowercase SHA-256")
    observed_fact_file_sha256 = _bytes_sha256(fact_bytes)
    if observed_fact_file_sha256 != expected_fact_file_sha256:
        raise ConfigurationError("fact file SHA-256 does not match the expected digest")
    relationship = proposal["relationship"]
    if proposal["repository_commit"] != fact["repository_commit"]:
        raise ConfigurationError("proposal and fact must bind the same repository commit")
    for field in ("kind", "source", "locator"):
        if relationship[field] != fact[field]:
            raise ConfigurationError(f"proposal relationship and fact disagree on {field}")

    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    if commit != proposal["repository_commit"]:
        raise ConfigurationError("repository HEAD does not match the proposal commit")
    status_before = _worktree_status(root, excluded_worktree_path)
    if status_before:
        raise ConfigurationError("binding sensitivity requires a clean caller worktree")

    source_path = _relative(relationship["source"], "proposal.relationship.source")
    doc_path = _relative(relationship["doc"], "proposal.relationship.doc")
    source_text, source_blob_sha256, source_blob_id = _tracked_text(
        root,
        commit,
        source_path,
    )
    doc_text, doc_blob_sha256, doc_blob_id = _tracked_text(
        root,
        commit,
        doc_path,
    )
    facts = [
        candidate
        for candidate in extract_source_facts(source_path.as_posix(), source_text)
        if candidate.kind == fact["kind"] and candidate.locator == fact["locator"]
    ]
    status_after: bytes = status_before
    base = {
        "source_blob_sha256": source_blob_sha256,
        "source_blob_id": source_blob_id,
        "document_blob_sha256": doc_blob_sha256,
        "document_blob_id": doc_blob_id,
    }
    if len(facts) != 1 or facts[0].digest != fact["value_sha256"]:
        status_after = _worktree_status(root, excluded_worktree_path)
        head_after = _git(root, "rev-parse", "HEAD").decode().strip()
        return {
            **_base_receipt(
                state="invalid",
                proposal=proposal,
                fact=fact,
                proposal_bytes=proposal_bytes,
                fact_bytes=fact_bytes,
                fact_file_sha256=expected_fact_file_sha256,
                commit=commit,
                head_after=head_after,
                status_before=status_before,
                status_after=status_after,
                detail="the frozen fact does not match the selected source evidence",
            ),
            "baseline": base,
            "mutation": None,
            "mutated": None,
        }
    fact_value = facts[0].value
    if not isinstance(fact_value, tuple):
        raise ConfigurationError("selected identifier-set fact did not resolve to names")
    if fact["member"] not in fact_value:
        status_after = _worktree_status(root, excluded_worktree_path)
        head_after = _git(root, "rev-parse", "HEAD").decode().strip()
        return {
            **_base_receipt(
                state="invalid",
                proposal=proposal,
                fact=fact,
                proposal_bytes=proposal_bytes,
                fact_bytes=fact_bytes,
                fact_file_sha256=expected_fact_file_sha256,
                commit=commit,
                head_after=head_after,
                status_before=status_before,
                status_after=status_after,
                detail="the selected member is absent from the frozen fact",
            ),
            "baseline": {**base, "source_fact": facts[0].digest},
            "mutation": None,
            "mutated": None,
        }

    check = _relationship_check(relationship)
    with tempfile.TemporaryDirectory(prefix="sourcebound-sensitivity-") as temporary:
        disposable = Path(temporary)
        disposable_source = disposable / source_path
        disposable_doc = disposable / doc_path
        disposable_source.parent.mkdir(parents=True, exist_ok=True)
        disposable_doc.parent.mkdir(parents=True, exist_ok=True)
        disposable_source.write_text(source_text, encoding="utf-8")
        disposable_doc.write_text(doc_text, encoding="utf-8")
        baseline_status, baseline_result = _observed_status(disposable, check)
        if baseline_status != "current":
            status_after = _worktree_status(root, excluded_worktree_path)
            head_after = _git(root, "rev-parse", "HEAD").decode().strip()
            return {
                **_base_receipt(
                    state="invalid",
                    proposal=proposal,
                    fact=fact,
                    proposal_bytes=proposal_bytes,
                    fact_bytes=fact_bytes,
                    fact_file_sha256=expected_fact_file_sha256,
                    commit=commit,
                    head_after=head_after,
                    status_before=status_before,
                    status_after=status_after,
                    detail=f"the proposed relationship baseline is {baseline_status}, not current",
                ),
                "baseline": {**base, "result": baseline_result},
                "mutation": None,
                "mutated": None,
            }
        try:
            mutated_text, mutation = _mutate_identifier(
                source_text,
                fact["locator"],
                fact["member"],
            )
        except UnsupportedMutation as exc:
            status_after = _worktree_status(root, excluded_worktree_path)
            head_after = _git(root, "rev-parse", "HEAD").decode().strip()
            return {
                **_base_receipt(
                    state="unsupported",
                    proposal=proposal,
                    fact=fact,
                    proposal_bytes=proposal_bytes,
                    fact_bytes=fact_bytes,
                    fact_file_sha256=expected_fact_file_sha256,
                    commit=commit,
                    head_after=head_after,
                    status_before=status_before,
                    status_after=status_after,
                    detail=str(exc),
                ),
                "baseline": {**base, "result": baseline_result},
                "mutation": None,
                "mutated": None,
            }
        disposable_source.write_text(mutated_text, encoding="utf-8")
        mutated_status, mutated_result = _observed_status(disposable, check)

    status_after = _worktree_status(root, excluded_worktree_path)
    head_after = _git(root, "rev-parse", "HEAD").decode().strip()
    if status_after != status_before or head_after != commit:
        state = "invalid"
        detail = "the caller repository changed during sensitivity verification"
    elif mutated_status == "drift":
        state = "sensitive"
        detail = "the selected relationship became stale after the independent fact mutation"
    elif mutated_status == "current":
        state = "insensitive"
        detail = "the selected relationship stayed current after the independent fact mutation"
    else:
        state = "invalid"
        detail = f"the mutated relationship resolved to {mutated_status}"
    return {
        **_base_receipt(
            state=state,
            proposal=proposal,
            fact=fact,
            proposal_bytes=proposal_bytes,
            fact_bytes=fact_bytes,
            fact_file_sha256=expected_fact_file_sha256,
            commit=commit,
            head_after=head_after,
            status_before=status_before,
            status_after=status_after,
            detail=detail,
        ),
        "baseline": {**base, "result": baseline_result},
        "mutation": mutation,
        "mutated": {"result": mutated_result},
    }
