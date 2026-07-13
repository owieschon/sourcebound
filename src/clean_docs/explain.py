from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from clean_docs.errors import ConfigurationError
from clean_docs.inventory import scan_inventory


RULES = {
    "audience": (
        "The document addresses a future executor instead of its product reader.",
        "Rewrite it for the reader's current task or move process state under docs/archive.",
    ),
    "broken-local-link": (
        "A relative Markdown link does not resolve from its document.",
        "Fix the target path or remove the link.",
    ),
    "cross-project-residue": (
        "Tracked content contains a token reserved for another repository.",
        "Replace the token with this repository's term or remove the copied residue.",
    ),
    "doc-length": (
        "A document exceeds the packaged line budget.",
        "Split distinct reader tasks or add a reasoned canonical-reference allowance.",
    ),
    "generated-artifact": (
        "Generated runtime residue is tracked as product source.",
        "Remove the artifact and add its pattern to the repository ignore file.",
    ),
    "local-path-residue": (
        "Tracked content contains a machine-specific home path.",
        "Replace it with a repository-relative or portable path.",
    ),
    "near-duplicate": (
        "Two reader-facing documents carry substantially the same content.",
        "Keep one canonical explanation and link to it from the other task surface.",
    ),
    "process-artifact": (
        "A status, handoff, plan, or report remains on the reader-facing surface.",
        "Move process history under docs/archive and link only if readers need it.",
    ),
    "purpose-contract": (
        "The document does not open with one marked BLUF purpose contract.",
        "Put a plain prose block after the H1 that names who should read, the problem, and the resulting capability.",
    ),
    "prohibited-booster": (
        "The prose uses a prohibited booster instead of a verifiable claim.",
        "Remove the booster and state the measured property directly.",
    ),
    "provenance": (
        "Reader-facing reference text contains authoring receipts or run provenance.",
        "Move the receipt to history and leave current truth in the reference.",
    ),
    "restatement": (
        "A fact is restated across reader-facing documents without one canonical home.",
        "Keep the fact in one document and replace sibling copies with links.",
    ),
    "section-length": (
        "A section exceeds the packaged line budget.",
        "Split the section by reader task or add a reasoned canonical-reference allowance.",
    ),
    "unreadable-document": (
        "A tracked Markdown path cannot be read from the current worktree.",
        "Restore the document, remove the stale tracked path, or fix its permissions.",
    ),
}


@dataclass(frozen=True)
class Explanation:
    id: str
    kind: str
    state: str
    summary: str
    evidence: dict[str, str]
    repair: str
    required: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def explain(root: Path, identifier: str) -> Explanation:
    if identifier in RULES:
        summary, repair = RULES[identifier]
        return Explanation(identifier, "policy-rule", "required", summary, {}, repair, True)
    item = next(
        (candidate for candidate in scan_inventory(root).items if candidate.id == identifier),
        None,
    )
    if item is None:
        raise ConfigurationError(f"unknown finding or inventory id: {identifier}")
    evidence = {
        "source": item.source,
        "locator": item.locator,
        "adapter": item.adapter,
        "sha256": item.digest,
    }
    if item.coverage == "bound":
        summary = "The detected surface has a source-specific documentation binding."
        repair = "No repair is required while the binding remains current."
    elif item.coverage == "cataloged":
        summary = (
            "The detected surface is tracked by a repository catalog, but has no "
            "source-specific documentation binding."
        )
        repair = "Add a source-specific binding if readers depend on this surface."
    elif item.coverage == "ignored":
        summary = f"The detected surface is ignored by policy: {item.coverage_reason}"
        repair = "Remove the reasoned ignore when this surface becomes reader-facing."
    else:
        summary = "The detected surface has evidence but no binding or reasoned ignore."
        repair = "Add a source binding or a specific record in .clean-docs-ignore.yml."
    return Explanation(
        item.id,
        "inventory-surface",
        item.coverage,
        summary,
        evidence,
        repair,
        False,
    )
