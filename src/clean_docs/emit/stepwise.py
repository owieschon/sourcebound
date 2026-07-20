"""Project a Sourcebound manifest into a docs-only stepwise skill package."""

from __future__ import annotations

from pathlib import Path

import yaml

from clean_docs.errors import ConfigurationError
from clean_docs.models import Manifest
from clean_docs.regions import atomic_write


PREAMBLE = (
    "**Read ONLY this file.** Do not read any other reference file until this one tells you to."
)


def _bound_docs(manifest: Manifest) -> list[str]:
    return sorted({binding.doc.as_posix() for binding in manifest.bindings})


def _config(
    *,
    display_name: str,
    role: str,
    parent_command: str | None,
    command: str | None,
) -> dict[str, object]:
    cli: dict[str, object] = {"role": role}
    if role == "command":
        if not command:
            raise ConfigurationError("a command name is required when role is command")
        cli["command"] = command
        if parent_command:
            cli["parentCommand"] = parent_command
    elif parent_command or command:
        raise ConfigurationError("command options require role command")
    return {
        "type": "skill",
        "template": "description.md",
        "description": "Keep repository documentation true to its source with Sourcebound",
        "tags": ["documentation", "sourcebound"],
        "cli": cli,
        "references": {"preamble": PREAMBLE},
        "variants": [
            {
                "id": "all",
                "display_name": display_name,
                "tags": ["documentation"],
                "docs_urls": [],
            }
        ],
    }


def _description(bound_docs: list[str]) -> str:
    listed = "\n".join(f"- `{doc}`" for doc in bound_docs) or "- No bound documents yet."
    return (
        "# Keep documentation true\n\n"
        "<!-- sourcebound:purpose -->\n"
        "Use this package when repository documentation may have drifted from its sources. "
        "It gives maintainers an ordered audit, bounded repair, and verification path with an "
        "explicit condition for each transition.\n"
        "<!-- sourcebound:end purpose -->\n\n"
        "Bound documents in this repository:\n\n"
        f"{listed}\n"
    )


def _step_audit() -> str:
    return (
        "---\nnext_step: 2-repair.md\n---\n\n"
        "# Step 1: audit the corpus\n\n"
        "<!-- sourcebound:purpose -->\n"
        "Use this step before changing docs when the active corpus may contain structural "
        "findings. It gives maintainers a read-only list of repairs that must precede binding "
        "work.\n"
        "<!-- sourcebound:end purpose -->\n\n"
        "## Status\n\n"
        "Emit: `sourcebound: auditing documentation`.\n\n"
        "## Action\n\n"
        "Run the manifest-free corpus audit:\n\n"
        "```bash\nsourcebound audit\n```\n\n"
        "## Decision\n\n"
        "Exit `0`: proceed. Exit `1`: apply each finding's named repair, then rerun this step. "
        "Exit `2` or `3`: repair the configuration or extractor before continuing.\n\n"
        "## Navigation\n\n"
        "When the audit exits `0`, read `2-repair.md`.\n"
    )


def _step_repair() -> str:
    return (
        "---\nnext_step: 3-verify.md\n---\n\n"
        "# Step 2: repair bound regions\n\n"
        "<!-- sourcebound:purpose -->\n"
        "Use this step after the corpus audit passes and source-bound regions may be stale. "
        "It repairs declared regions while preserving prose outside their markers.\n"
        "<!-- sourcebound:end purpose -->\n\n"
        "## Status\n\n"
        "Emit: `sourcebound: repairing bound regions`.\n\n"
        "## Action\n\n"
        "Derive the declared regions from source and enforce the packaged standard:\n\n"
        "```bash\nsourcebound drive\n```\n\n"
        "This writes only the regions declared in the manifest. It preserves prose outside the "
        "markers "
        "and refuses a write when policy fails.\n\n"
        "## Decision\n\n"
        "Exit `0`: proceed. A policy finding requires an author to repair the flagged prose and "
        "rerun this step.\n\n"
        "## Navigation\n\n"
        "When `drive` exits `0`, read `3-verify.md`.\n"
    )


def _step_verify() -> str:
    return (
        "---\nnext_step: null\n---\n\n"
        "# Step 3: verify before publishing\n\n"
        "<!-- sourcebound:purpose -->\n"
        "Use this step after repair when you need evidence that the corpus and every binding "
        "are current. It gives maintainers the read-only release gate and the exact stop "
        "condition.\n"
        "<!-- sourcebound:end purpose -->\n\n"
        "## Status\n\n"
        "Emit: `sourcebound: verifying`.\n\n"
        "## Action\n\n"
        "Run the read-only gates:\n\n"
        "```bash\nsourcebound audit\nsourcebound check\n```\n\n"
        "## Decision\n\n"
        "Both commands exit `0`: publishing is allowed. Either exits nonzero: return to the step "
        "that owns the finding and do not publish.\n\n"
        "## Navigation\n\n"
        "This is the final step. It writes nothing.\n"
    )


def emit_stepwise_skill(
    manifest: Manifest,
    out_dir: Path,
    *,
    display_name: str = "Keep documentation true",
    role: str = "skill",
    parent_command: str | None = None,
    command: str | None = None,
) -> tuple[Path, ...]:
    """Write a manifest-derived stepwise skill package and return its files."""
    bound_docs = _bound_docs(manifest)
    files = {
        out_dir / "config.yaml": yaml.safe_dump(
            _config(
                display_name=display_name,
                role=role,
                parent_command=parent_command,
                command=command,
            ),
            sort_keys=False,
            allow_unicode=True,
        ),
        out_dir / "description.md": _description(bound_docs),
        out_dir / "references/1-audit.md": _step_audit(),
        out_dir / "references/2-repair.md": _step_repair(),
        out_dir / "references/3-verify.md": _step_verify(),
    }
    for path, text in files.items():
        atomic_write(path, text)
    return tuple(sorted(files))
