from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from clean_docs.errors import RegionError


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


def replace_region(document: str, region: str, generated: str) -> str:
    forms = [
        candidate
        for candidate in (markers(region), mdx_markers(region))
        if candidate[0] in document or candidate[1] in document
    ]
    if len(forms) != 1:
        raise RegionError(
            f"region {region!r} must use exactly one Markdown or MDX marker form"
        )
    begin, end = forms[0]
    if document.count(begin) != 1 or document.count(end) != 1:
        raise RegionError(f"region {region!r} must have exactly one begin and one end marker")
    start = document.index(begin) + len(begin)
    finish = document.index(end)
    if finish < start:
        raise RegionError(f"region {region!r} end marker precedes its begin marker")
    between = document[start:finish]
    if any(
        marker in between
        for marker in (
            "<!-- sourcebound:begin ",
            "<!-- sourcebound:end ",
            "{/* sourcebound:begin ",
            "{/* sourcebound:end ",
        )
    ):
        raise RegionError(f"region {region!r} contains nested sourcebound markers")
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
