from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path

from clean_docs.errors import ConfigurationError, ExtractionError
from clean_docs.extractors import (
    extract_command,
    extract_file,
    extract_json_pointer,
    extract_paths,
    extract_python_literal,
    extract_repository_inventory,
    extract_structured,
)
from clean_docs.manifest import load_manifest
from clean_docs.models import (
    Binding,
    BindingResult,
    ClaimBinding,
    Manifest,
    Provenance,
    RegionBinding,
    SymbolBinding,
)
from clean_docs.policy import PolicyFinding, check_documents
from clean_docs.regions import atomic_write, replace_region
from clean_docs.renderers import render
from clean_docs.snapshot import RepositorySnapshot
from clean_docs.standard import load_default_pack
from clean_docs.symbols import resolve_symbol


def _select(bindings: tuple[Binding, ...], binding_id: str | None) -> list[Binding]:
    if binding_id is None:
        return list(bindings)
    selected = [binding for binding in bindings if binding.id == binding_id]
    if not selected:
        raise ConfigurationError(f"unknown binding id: {binding_id}")
    return selected


def _document(root: Path, binding: Binding) -> str:
    try:
        return (root / binding.doc).read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read bound document {binding.doc}: {exc}") from exc


def _has_anchor(document: str, anchor: str) -> bool:
    for line in document.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            slug = re.sub(r"[^a-z0-9 -]", "", match.group(1).lower()).replace(" ", "-")
            if slug == anchor:
                return True
    return False


def _claim_result(root: Path, snapshot: RepositorySnapshot, manifest: Manifest, binding: ClaimBinding) -> BindingResult:
    document = _document(root, binding)
    if not _has_anchor(document, binding.anchor):
        raise ConfigurationError(f"document anchor not found: {binding.doc}#{binding.anchor}")
    command = next(item for item in manifest.commands if item.id == binding.command)
    evidence = extract_command(snapshot, command, binding.assertion.path)
    changed = evidence.value != binding.assertion.expected
    expected = json.dumps(binding.assertion.expected, sort_keys=True)
    observed = json.dumps(evidence.value, sort_keys=True)
    diff = "" if not changed else (
        f"claim {binding.doc}#{binding.anchor}: expected {expected}, observed {observed}\n"
    )
    return BindingResult(
        binding.id, binding.doc.as_posix(), changed, expected, observed, diff,
        evidence.provenance, "claim",
    )


def _symbol_result(root: Path, snapshot: RepositorySnapshot, binding: SymbolBinding) -> BindingResult:
    document = _document(root, binding)
    if not _has_anchor(document, binding.anchor):
        raise ConfigurationError(f"document anchor not found: {binding.doc}#{binding.anchor}")
    try:
        evidence = resolve_symbol(snapshot, binding)
        changed = False
        observed = "exists"
        provenance = evidence.provenance
        diff = ""
    except ExtractionError as exc:
        if "not found" not in str(exc) and "cannot read source" not in str(exc):
            raise
        changed = True
        observed = "missing"
        locator = binding.source.symbol or binding.source.path.as_posix()
        provenance = Provenance(
            snapshot.label,
            binding.source.path.as_posix(),
            locator,
            "symbol@1",
            hashlib.sha256(locator.encode()).hexdigest(),
        )
        diff = f"symbol {locator} referenced by {binding.doc}#{binding.anchor} is missing\n"
    return BindingResult(
        binding.id, binding.doc.as_posix(), changed, "exists", observed, diff,
        provenance, "symbol",
    )


def evaluate(
    root: Path,
    manifest_path: Path,
    *,
    ref: str | None = None,
    binding_id: str | None = None,
) -> list[BindingResult]:
    manifest = load_manifest(manifest_path)
    snapshot = RepositorySnapshot(root=root, ref=ref)
    results: list[BindingResult] = []
    documents: dict[str, str] = {}
    for binding in _select(manifest.bindings, binding_id):
        if isinstance(binding, ClaimBinding):
            results.append(_claim_result(root, snapshot, manifest, binding))
            continue
        if isinstance(binding, SymbolBinding):
            results.append(_symbol_result(root, snapshot, binding))
            continue
        assert isinstance(binding, RegionBinding)
        extractors = {
            "file": extract_file,
            "json": extract_json_pointer,
            "path": extract_paths,
            "python-literal": extract_python_literal,
            "repository-inventory": extract_repository_inventory,
            "structured-data": extract_structured,
        }
        evidence = extractors[binding.extractor](snapshot, binding)
        rendered = render(evidence, binding)
        doc_path = root / binding.doc
        doc_key = binding.doc.as_posix()
        if doc_key not in documents:
            try:
                documents[doc_key] = doc_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise ConfigurationError(
                    f"cannot read bound document {binding.doc}: {exc}"
                ) from exc
        observed = documents[doc_key]
        expected = replace_region(observed, binding.region, rendered)
        documents[doc_key] = expected
        diff = "".join(difflib.unified_diff(
            observed.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=binding.doc.as_posix(),
            tofile=f"{binding.doc.as_posix()} (derived)",
        ))
        results.append(BindingResult(
            binding_id=binding.id,
            doc=binding.doc.as_posix(),
            changed=observed != expected,
            expected=expected,
            observed=observed,
            diff=diff,
            provenance=evidence.provenance,
        ))
    return results


def write_results(root: Path, results: list[BindingResult]) -> None:
    by_doc: dict[str, str] = {}
    for result in results:
        if result.binding_type != "region":
            continue
        current = by_doc.get(result.doc)
        if current is not None and current != result.observed:
            raise ConfigurationError(
                f"multiple bindings for {result.doc} require a combined document update"
            )
        by_doc[result.doc] = result.expected
    for doc, content in by_doc.items():
        atomic_write(root / doc, content)


def planned_documents(results: list[BindingResult]) -> dict[str, str]:
    documents: dict[str, str] = {}
    for result in results:
        if result.binding_type != "region":
            continue
        current = documents.get(result.doc)
        if current is not None and current != result.observed:
            raise ConfigurationError(f"binding plan for {result.doc} is not sequential")
        documents[result.doc] = result.expected
    return documents


def drive(
    root: Path,
    manifest_path: Path,
    *,
    ref: str | None = None,
    binding_id: str | None = None,
) -> tuple[list[BindingResult], list[PolicyFinding]]:
    results = evaluate(root, manifest_path, ref=ref, binding_id=binding_id)
    findings = check_documents(planned_documents(results), load_default_pack())
    if findings:
        return results, findings
    write_results(root, results)
    remaining = evaluate(root, manifest_path, ref=ref, binding_id=binding_id)
    if any(result.changed for result in remaining if result.binding_type == "region"):
        raise ConfigurationError("drive wrote documentation but drift remains")
    return results, []
