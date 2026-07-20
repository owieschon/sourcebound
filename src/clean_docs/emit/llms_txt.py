"""Project a manifest into an llms.txt index of bound and declared canonical docs."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import quote

from clean_docs.errors import ConfigurationError
from clean_docs.models import Manifest
from clean_docs.regions import atomic_write

DEFAULT_TITLE = "Repository documentation"
DEFAULT_SUMMARY = (
    "Index of repository documents with source-bound facts. Sourcebound checks the named bindings "
    "for drift."
)


def _bound_facts(manifest: Manifest) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for binding in manifest.bindings:
        groups.setdefault(binding.doc.as_posix(), []).append(binding.id)
    return {doc: sorted(ids) for doc, ids in sorted(groups.items())}


def _indexed_documents(manifest: Manifest) -> dict[str, list[str]]:
    documents = _bound_facts(manifest)
    projection = manifest.projections.llms_txt if manifest.projections else None
    if projection is not None:
        for path in projection.include:
            documents.setdefault(path.as_posix(), [])
    return dict(sorted(documents.items()))


def _one_line(value: str, name: str) -> str:
    if not value.strip() or "\n" in value or "\r" in value:
        raise ConfigurationError(f"llms.txt {name} must be one non-empty line")
    return value.strip()


def _document_metadata(
    manifest: Manifest,
    document: str,
    documents: dict[str, bytes] | None = None,
    output_path: Path | None = None,
) -> tuple[str, str]:
    repository_root = manifest.path.parent.resolve()
    path = repository_root / document
    if documents is not None and document in documents:
        content = documents[document]
    else:
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ConfigurationError(f"cannot index document {document}: {exc}") from exc
    if output_path is None:
        link = document
    else:
        link = os.path.relpath(path, output_path.resolve().parent).replace(os.sep, "/")
    return quote(link, safe="/"), hashlib.sha256(content).hexdigest()


def render_llms_txt(
    manifest: Manifest,
    *,
    title: str | None = None,
    summary: str | None = None,
    documents: dict[str, bytes] | None = None,
    output_path: Path | None = None,
) -> str:
    """Render an llms.txt projection without writing it."""
    heading = _one_line(title or DEFAULT_TITLE, "title")
    blurb = _one_line(summary or DEFAULT_SUMMARY, "summary")
    lines = [f"# {heading}", "", f"> {blurb}", "", "## Canonical documentation", ""]
    for doc, ids in _indexed_documents(manifest).items():
        link, digest = _document_metadata(manifest, doc, documents, output_path)
        status = f"bindings: {', '.join(ids)}" if ids else "declared canonical context"
        lines.append(
            f"- [{doc}]({link}): {status}; sha256: {digest}"
        )
    return "\n".join(lines) + "\n"


def emit_llms_txt(
    manifest: Manifest,
    out_path: Path,
    *,
    title: str | None = None,
    summary: str | None = None,
) -> Path:
    """Write an llms.txt index derived from the manifest and return its path."""
    atomic_write(
        out_path,
        render_llms_txt(
            manifest,
            title=title,
            summary=summary,
            output_path=out_path,
        ),
    )
    return out_path
