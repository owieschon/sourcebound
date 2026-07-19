from __future__ import annotations

import json
from pathlib import Path

import pytest

from clean_docs.capabilities import CLI_REFERENCE
from clean_docs.demo import load_demo_evidence, render_static_demo, validate_static_html
from clean_docs.errors import ConfigurationError
from clean_docs.manifest import load_manifest
from clean_docs.projections import evaluate_projections, write_projections
from clean_docs.templates import TaskPage, render_task_markdown, validate_task_markdown
from scripts.record_demo import record


ROOT = Path(__file__).parents[1]


def _evidence(tmp_path: Path, *, next_href: str = "README.md#command") -> Path:
    payload = record()
    payload["next_step"]["href"] = next_href  # type: ignore[index]
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_task_page_template_requires_all_reader_slots() -> None:
    page = TaskPage(
        title="Run the check",
        intended_reader="Repository maintainers.",
        value="Catch documentation drift before merge.",
        prerequisites=("Install clean-docs.",),
        procedure=("Run clean-docs check.", "Repair the named binding."),
        limits=("Only declared bindings are checked.",),
        next_step="Add the command to CI.",
    )
    rendered = render_task_markdown(page)
    validate_task_markdown(rendered)
    assert rendered.index("## Intended reader") < rendered.index("## Procedure")
    assert "1. Run clean-docs check." in rendered

    with pytest.raises(ConfigurationError, match="missing section: Limits"):
        validate_task_markdown(rendered.replace("## Limits", "## Constraints"))


def test_static_demo_is_byte_stable_accessible_and_runtime_free(tmp_path: Path) -> None:
    evidence = load_demo_evidence(_evidence(tmp_path))
    output = Path("docs/demo/index.html")

    first = render_static_demo(evidence, output)
    second = render_static_demo(evidence, output)

    assert first == second
    validate_static_html(first)
    assert "clean-docs check" in first
    assert "clean-docs drive" in first
    assert "exit 1" in first
    assert "Make stale prose fail loudly." in first
    assert "../../README.md#command" in first
    assert "<script" not in first
    assert "fetch(" not in first
    assert "https://" not in first
    assert "Evidence sha256:" in first


def test_readme_architecture_is_text_native_and_preserves_command_boundaries() -> None:
    readme = (ROOT / "README.md").read_text()

    install = readme.index("## Install in the repository you want to protect")
    architecture = readme.index("## How the pieces fit")
    architecture_section = readme[architecture:readme.index("## Current boundaries")]
    assert install < architecture
    assert "![" not in architecture_section
    assert "<svg" not in architecture_section
    for concept in (
        "Authored intent",
        "does not infer its priority",
        "Repository contract",
        "Each mechanism proves only its declared relationship",
        "accepted source-claim checks are separate",
        "unbound prose stays visibly unknown",
        "immutable impact plan",
        "four job-specific exits",
        "Repair bounded prose",
        "Reject stale changes",
        "Publish agent context",
        "Record local state",
        "`check` and `verdict` are read-only",
        "`verdict` and `verify` produce independent receipts",
        "Neither certifies unbound or judgment prose",
    ):
        assert concept in architecture_section

    writes = {row["command"]: row["writes"] for row in CLI_REFERENCE}
    assert writes["drive"] == "yes"
    assert writes["project"] == "unless --check"
    for command in ("check", "verdict"):
        assert writes[command] == "no"
    for command in ("drive", "project", "check", "verdict", "verify"):
        assert f"`{command}`" in architecture_section


def test_static_demo_structure_rejects_inaccessible_or_runtime_content(
    tmp_path: Path,
) -> None:
    content = render_static_demo(
        load_demo_evidence(_evidence(tmp_path)), Path("docs/demo/index.html")
    )
    with pytest.raises(ConfigurationError, match="skip link"):
        validate_static_html(content.replace('href="#main"', 'href="#missing"', 1))
    with pytest.raises(ConfigurationError, match="scripts are not allowed"):
        validate_static_html(content.replace("</body>", "<script></script></body>"))


def test_project_tracks_demo_evidence_and_repairs_stale_html(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "source.txt").write_text("Bound command\n")
    (root / "README.md").write_text(
        "# Fixture\n\n## Command\n\n"
        "<!-- clean-docs:begin command -->\nBound command\n"
        "<!-- clean-docs:end command -->\n"
    )
    evidence_path = root / ".clean-docs/demo/evidence.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(_evidence(tmp_path).read_bytes())
    (root / ".clean-docs.yml").write_text("""\
version: 1
bindings:
  - id: command
    type: region
    doc: README.md
    region: command
    extractor: file
    source: {path: source.txt}
    renderer: scalar
projections:
  demo:
    output: docs/demo/index.html
    evidence: .clean-docs/demo/evidence.json
""")
    manifest = load_manifest(root / ".clean-docs.yml")

    written = write_projections(root, manifest)
    first = (root / "docs/demo/index.html").read_bytes()
    assert written == (Path("docs/demo/index.html"),)
    assert not any(result.changed for result in evaluate_projections(root, manifest))

    payload = json.loads(evidence_path.read_text())
    payload["value"] = "Updated recorded value."
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    assert evaluate_projections(root, manifest)[0].changed
    write_projections(root, manifest)
    assert (root / "docs/demo/index.html").read_bytes() != first
    assert not evaluate_projections(root, manifest)[0].changed
