from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from sourcebound.errors import RegionError


def markers(region: str) -> tuple[str, str]:
    return (
        f"<!-- sourcebound:begin {region} -->",
        f"<!-- sourcebound:end {region} -->",
    )


def mdx_markers(region: str) -> tuple[str, str]:
    return (
        f"{{/* sourcebound:begin {region} */}}",
        f"{{/* sourcebound:end {region} */}}",
    )


_NESTED_MARKER_PREFIXES = (
    "<!-- sourcebound:begin ",
    "<!-- sourcebound:end ",
    "{/* sourcebound:begin ",
    "{/* sourcebound:end ",
)


def _bounds(document: str, region: str, forms: tuple[tuple[str, str], ...]) -> tuple[str, str, int, int]:
    matched = [
        candidate
        for candidate in forms
        if candidate[0] in document or candidate[1] in document
    ]
    if len(matched) != 1:
        raise RegionError(
            f"region {region!r} must use exactly one Markdown or MDX marker form"
        )
    begin, end = matched[0]
    if document.count(begin) != 1 or document.count(end) != 1:
        raise RegionError(f"region {region!r} must have exactly one begin and one end marker")
    start = document.index(begin) + len(begin)
    finish = document.index(end)
    if finish < start:
        raise RegionError(f"region {region!r} end marker precedes its begin marker")
    between = document[start:finish]
    if any(marker in between for marker in _NESTED_MARKER_PREFIXES):
        raise RegionError(f"region {region!r} contains nested sourcebound markers")
    return begin, end, start, finish


def _replace_inline_region(document: str, region: str, generated: str) -> str:
    if any(marker in document for marker in mdx_markers(region)):
        raise RegionError(
            f"region {region!r} inline-scalar rendering does not support MDX markers"
        )
    _, _, start, finish = _bounds(document, region, (markers(region),))
    between = document[start:finish]
    if "\n" in between or "\r" in between:
        raise RegionError(f"region {region!r} inline markers must be on the same line")
    if "\n" in generated or "\r" in generated:
        raise RegionError(f"region {region!r} inline replacement must not contain newlines")
    return document[:start] + generated + document[finish:]


def replace_region(document: str, region: str, generated: str, *, inline: bool = False) -> str:
    if inline:
        return _replace_inline_region(document, region, generated)
    _, _, start, finish = _bounds(document, region, (markers(region), mdx_markers(region)))
    return document[:start] + "\n" + generated.rstrip() + "\n" + document[finish:]


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        mode = 0o644
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
