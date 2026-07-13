from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from clean_docs.errors import RegionError


def markers(region: str) -> tuple[str, str]:
    return (
        f"<!-- clean-docs:begin {region} -->",
        f"<!-- clean-docs:end {region} -->",
    )


def replace_region(document: str, region: str, generated: str) -> str:
    begin, end = markers(region)
    if document.count(begin) != 1 or document.count(end) != 1:
        raise RegionError(f"region {region!r} must have exactly one begin and one end marker")
    start = document.index(begin) + len(begin)
    finish = document.index(end)
    if finish < start:
        raise RegionError(f"region {region!r} end marker precedes its begin marker")
    between = document[start:finish]
    if "<!-- clean-docs:begin " in between or "<!-- clean-docs:end " in between:
        raise RegionError(f"region {region!r} contains nested clean-docs markers")
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
