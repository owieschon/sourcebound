"""Render and verify projections of the canonical documentation graph."""

from __future__ import annotations

import difflib
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from clean_docs.demo import load_demo_evidence, render_static_demo
from clean_docs.emit import render_llms_txt
from clean_docs.errors import ConfigurationError
from clean_docs.models import (
    BindingResult,
    ContextBundleProjection,
    Manifest,
    Provenance,
)
from clean_docs.regions import atomic_write
from clean_docs.visuals import (
    load_visual_record,
    render_agent_visual,
    render_human_visual,
)


LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+[^)]*)?\)")
HTML_LINK = re.compile(r'href="([^"]+)"')
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
CANONICAL_BLOCK = re.compile(
    r"<!-- sourcebound:canonical .+? begin -->.*?"
    r"<!-- sourcebound:canonical .+? end -->",
    re.DOTALL,
)


@dataclass(frozen=True)
class ProjectionSet:
    source_ref: str
    corpus_digest: str
    files: dict[Path, str]
    digests: dict[Path, str]


def _read_documents(root: Path, manifest: Manifest) -> dict[str, bytes]:
    documents: dict[str, bytes] = {}
    paths: set[str] = set()
    llms = manifest.projections.llms_txt if manifest.projections else None
    if llms is None or llms.include_bound:
        paths.update(binding.doc.as_posix() for binding in manifest.bindings)
    if llms is not None:
        paths.update(path.as_posix() for path in llms.include)
    if manifest.projections is not None:
        for bundle in manifest.projections.bundles:
            paths.update(path.as_posix() for path in bundle.include)
    for document in sorted(paths):
        try:
            documents[document] = (root / document).read_bytes()
        except OSError as exc:
            raise ConfigurationError(
                f"cannot project bound document {document}: {exc}"
            ) from exc
    return documents


def _corpus_digest(documents: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, content in sorted(documents.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _source_ref() -> str:
    # A working-tree projection cannot embed HEAD without becoming stale when its own commit
    # changes HEAD. The corpus digest identifies the exact bytes; immutable refs use a separate
    # snapshot path when supported.
    return "WORKTREE"


def _relative_link(root: Path, output: Path, document: Path) -> str:
    link = os.path.relpath(root / document, (root / output).parent).replace(os.sep, "/")
    return link


def _render_bundle(
    root: Path,
    bundle: ContextBundleProjection,
    documents: dict[str, bytes],
    source_ref: str,
    corpus_digest: str,
) -> str:
    lines = [
        f"# Context bundle: {bundle.id}",
        "",
        f"- Source ref: `{source_ref}`",
        f"- Corpus sha256: `{corpus_digest}`",
        "- Content: exact canonical document bytes",
    ]
    for document in bundle.include:
        key = document.as_posix()
        content = documents[key].decode("utf-8")
        link = _relative_link(root, bundle.output, document)
        digest = hashlib.sha256(documents[key]).hexdigest()
        lines.extend(
            [
                "",
                f"## Canonical document: {key}",
                "",
                f"- Source: [{key}]({link})",
                f"- Content sha256: `{digest}`",
                "",
                f"<!-- sourcebound:canonical {key} begin -->",
                content.rstrip(),
                f"<!-- sourcebound:canonical {key} end -->",
            ]
        )
    return "\n".join(lines) + "\n"


def _slug(title: str) -> str:
    value = re.sub(r"<[^>]+>", "", title).strip().lower()
    value = re.sub(r"[^a-z0-9 _-]", "", value)
    return re.sub(r"[ _]+", "-", value).strip("-")


def _anchors(content: str) -> set[str]:
    counts: dict[str, int] = {}
    anchors: set[str] = set()
    for line in content.splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        base = _slug(match.group(1))
        count = counts.get(base, 0)
        counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")
    anchors.update(re.findall(r'\bid="([^"]+)"', content))
    return anchors


def _verify_links(root: Path, files: dict[Path, str]) -> None:
    source_paths = set(files)
    for relative, content in files.items():
        # Embedded canonical bytes retain links relative to their original page. The original
        # page is checked separately; generated bundle metadata is checked at the bundle path.
        checked_content = CANONICAL_BLOCK.sub("", content)
        matches = [
            *LINK.finditer(checked_content),
            *HTML_LINK.finditer(checked_content),
        ]
        for match in matches:
            raw = unquote(match.group(1))
            if raw.startswith(("http://", "https://", "mailto:")):
                continue
            target_text, _, fragment = raw.partition("#")
            target = (
                relative
                if not target_text
                else Path(os.path.normpath((relative.parent / target_text).as_posix()))
            )
            if target.is_absolute() or ".." in target.parts:
                resolved = (root / relative.parent / target_text).resolve()
                try:
                    target = resolved.relative_to(root)
                except ValueError as exc:
                    raise ConfigurationError(
                        f"projection link escapes repository: {relative} -> {raw}"
                    ) from exc
            if target in source_paths:
                target_content = files[target]
            else:
                path = root / target
                if path.exists() and not fragment:
                    continue
                try:
                    target_content = path.read_text(encoding="utf-8")
                except OSError as exc:
                    raise ConfigurationError(
                        f"broken projection link: {relative} -> {raw}"
                    ) from exc
            if fragment and unquote(fragment) not in _anchors(target_content):
                raise ConfigurationError(
                    f"broken projection anchor: {relative} -> {raw}"
                )


def render_projections(root: Path, manifest: Manifest) -> ProjectionSet:
    root = root.resolve()
    if manifest.projections is None:
        raise ConfigurationError("manifest does not configure projections")
    documents = _read_documents(root, manifest)
    corpus_digest = _corpus_digest(documents)
    source_ref = _source_ref()
    files: dict[Path, str] = {}
    digests: dict[Path, str] = {}
    llms = manifest.projections.llms_txt
    if llms:
        files[llms.output] = render_llms_txt(
            manifest,
            title=llms.title,
            summary=llms.summary,
            documents=documents,
            output_path=root / llms.output,
        )
        digests[llms.output] = corpus_digest
    for bundle in manifest.projections.bundles:
        files[bundle.output] = _render_bundle(
            root, bundle, documents, source_ref, corpus_digest
        )
        digests[bundle.output] = corpus_digest
    demo = manifest.projections.demo
    if demo:
        evidence = load_demo_evidence(root / demo.evidence)
        files[demo.output] = render_static_demo(evidence, demo.output)
        digests[demo.output] = evidence.digest
    for visual in manifest.projections.visuals:
        record = load_visual_record(root / visual.source, visual.id)
        files[visual.human_output] = render_human_visual(root, visual, record)
        files[visual.agent_output] = render_agent_visual(root, visual, record)
        digests[visual.human_output] = record.digest
        digests[visual.agent_output] = record.digest
    combined = {
        Path(path): content.decode("utf-8") for path, content in documents.items()
    }
    combined.update(files)
    _verify_links(root, combined)
    return ProjectionSet(source_ref, corpus_digest, files, digests)


def evaluate_projections(root: Path, manifest: Manifest) -> list[BindingResult]:
    projection_set = render_projections(root, manifest)
    results = []
    for path, expected in sorted(
        projection_set.files.items(), key=lambda item: item[0].as_posix()
    ):
        try:
            observed = (root / path).read_text(encoding="utf-8")
        except FileNotFoundError:
            observed = ""
        except OSError as exc:
            raise ConfigurationError(f"cannot read projection {path}: {exc}") from exc
        diff = "".join(
            difflib.unified_diff(
                observed.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile=path.as_posix(),
                tofile=f"{path.as_posix()} (projected)",
            )
        )
        results.append(
            BindingResult(
                binding_id=f"projection:{path.as_posix()}",
                doc=path.as_posix(),
                changed=observed != expected,
                expected=expected,
                observed=observed,
                diff=diff,
                provenance=Provenance(
                    ref=projection_set.source_ref,
                    path=path.as_posix(),
                    locator="documentation-graph",
                    extractor="projection",
                    digest=projection_set.digests[path],
                ),
                binding_type="projection",
            )
        )
    return results


def write_projections(root: Path, manifest: Manifest) -> tuple[Path, ...]:
    projection_set = render_projections(root, manifest)
    written = []
    for path, content in sorted(
        projection_set.files.items(), key=lambda item: item[0].as_posix()
    ):
        atomic_write(root / path, content)
        written.append(path)
    return tuple(written)
