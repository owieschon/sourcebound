from __future__ import annotations

import difflib
from pathlib import Path

from clean_docs.errors import ConfigurationError
from clean_docs.extractors import extract_json_pointer, extract_python_literal
from clean_docs.manifest import load_manifest
from clean_docs.models import BindingResult, RegionBinding
from clean_docs.policy import PolicyFinding, check_documents
from clean_docs.regions import atomic_write, replace_region
from clean_docs.renderers import render_markdown_table
from clean_docs.snapshot import RepositorySnapshot
from clean_docs.standard import load_default_pack


def _select(bindings: tuple[RegionBinding, ...], binding_id: str | None) -> list[RegionBinding]:
    if binding_id is None:
        return list(bindings)
    selected = [binding for binding in bindings if binding.id == binding_id]
    if not selected:
        raise ConfigurationError(f"unknown binding id: {binding_id}")
    return selected


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
        evidence = (
            extract_python_literal(snapshot, binding)
            if binding.extractor == "python-literal"
            else extract_json_pointer(snapshot, binding)
        )
        rendered = render_markdown_table(evidence, binding)
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
    if any(result.changed for result in remaining):
        raise ConfigurationError("drive wrote documentation but drift remains")
    return results, []
