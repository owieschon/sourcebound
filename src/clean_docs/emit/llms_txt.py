"""Project a clean-docs manifest into an llms.txt index of source-bound docs."""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote

from clean_docs.errors import ConfigurationError
from clean_docs.models import Manifest
from clean_docs.regions import atomic_write

DEFAULT_TITLE = "Repository documentation"
DEFAULT_SUMMARY = (
    "Index of repository documents with source-bound facts. clean-docs checks the named bindings "
    "for drift."
)


def _bound_facts(manifest: Manifest) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for binding in manifest.bindings:
        groups.setdefault(binding.doc.as_posix(), []).append(binding.id)
    return {doc: sorted(ids) for doc, ids in sorted(groups.items())}


def _one_line(value: str, name: str) -> str:
    if not value.strip() or "\n" in value or "\r" in value:
        raise ConfigurationError(f"llms.txt {name} must be one non-empty line")
    return value.strip()


def _document_metadata(manifest: Manifest, document: str) -> tuple[str, str]:
    repository_root = manifest.path.parent.resolve()
    path = repository_root / document
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ConfigurationError(f"cannot index bound document {document}: {exc}") from exc
    return quote(document, safe="/"), hashlib.sha256(content).hexdigest()


def emit_llms_txt(
    manifest: Manifest,
    out_path: Path,
    *,
    title: str | None = None,
    summary: str | None = None,
) -> Path:
    """Write an llms.txt index derived from the manifest and return its path."""
    heading = _one_line(title or DEFAULT_TITLE, "title")
    blurb = _one_line(summary or DEFAULT_SUMMARY, "summary")
    lines = [f"# {heading}", "", f"> {blurb}", "", "## Source-bound documentation", ""]
    for doc, ids in _bound_facts(manifest).items():
        link, digest = _document_metadata(manifest, doc)
        lines.append(
            f"- [{doc}]({link}): bindings: {', '.join(ids)}; sha256: {digest}"
        )
    atomic_write(out_path, "\n".join(lines) + "\n")
    return out_path
