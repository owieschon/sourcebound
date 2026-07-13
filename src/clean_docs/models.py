from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Source:
    path: Path
    symbol: str


@dataclass(frozen=True)
class RegionBinding:
    id: str
    doc: Path
    region: str
    extractor: str
    source: Source
    renderer: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    path: Path
    version: int
    bindings: tuple[RegionBinding, ...]


@dataclass(frozen=True)
class Provenance:
    ref: str
    path: str
    locator: str
    extractor: str
    digest: str


@dataclass(frozen=True)
class EvidenceValue:
    kind: str
    value: Any
    provenance: Provenance


@dataclass(frozen=True)
class BindingResult:
    binding_id: str
    doc: str
    changed: bool
    expected: str
    observed: str
    diff: str
    provenance: Provenance
