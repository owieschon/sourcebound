from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLUGIN_API_VERSION = 1
PLUGIN_INTERFACES = frozenset({"discoverer", "extractor", "policy", "renderer"})


@dataclass(frozen=True)
class Source:
    path: Path
    symbol: str | None = None
    pointer: str | None = None
    glob: str | None = None


@dataclass(frozen=True)
class RegionBinding:
    id: str
    doc: Path
    region: str
    extractor: str
    source: Source
    renderer: str
    columns: tuple[str, ...]
    language: str | None = None


@dataclass(frozen=True)
class Assertion:
    path: str
    operator: str
    expected: Any


@dataclass(frozen=True)
class ClaimBinding:
    id: str
    doc: Path
    anchor: str
    extractor: str
    command: str
    assertion: Assertion


@dataclass(frozen=True)
class SymbolBinding:
    id: str
    doc: Path
    anchor: str
    source: Source


Binding = RegionBinding | ClaimBinding | SymbolBinding


@dataclass(frozen=True)
class SourceClaimCheck:
    id: str
    kind: str
    doc: Path
    anchor: str
    subject: str
    source: Path
    locator: str


@dataclass(frozen=True)
class CommandSpec:
    id: str
    argv: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True)
class PluginSpec:
    id: str
    api_version: int
    interfaces: tuple[str, ...]
    argv: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True)
class LlmsTxtProjection:
    output: Path
    title: str | None = None
    summary: str | None = None
    include: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ContextBundleProjection:
    id: str
    output: Path
    include: tuple[Path, ...]


@dataclass(frozen=True)
class StaticDemoProjection:
    output: Path
    evidence: Path


@dataclass(frozen=True)
class VisualProjection:
    id: str
    source: Path
    human_output: Path
    agent_output: Path


@dataclass(frozen=True)
class ReviewLocator:
    id: str
    path: Path
    extractor: str
    locator: str


@dataclass(frozen=True)
class ReviewContract:
    id: str
    mode: str
    sources: tuple[ReviewLocator, ...]
    targets: tuple[ReviewLocator, ...]


@dataclass(frozen=True)
class ProjectionConfig:
    llms_txt: LlmsTxtProjection | None = None
    bundles: tuple[ContextBundleProjection, ...] = ()
    demo: StaticDemoProjection | None = None
    visuals: tuple[VisualProjection, ...] = ()


@dataclass(frozen=True)
class Manifest:
    path: Path
    version: int
    bindings: tuple[Binding, ...]
    commands: tuple[CommandSpec, ...] = ()
    plugins: tuple[PluginSpec, ...] = ()
    projections: ProjectionConfig | None = None
    source_claim_checks: tuple[SourceClaimCheck, ...] = ()
    review_contracts: tuple[ReviewContract, ...] = ()
    deprecations: tuple[str, ...] = ()


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
    binding_type: str = "region"
    state: str | None = None
