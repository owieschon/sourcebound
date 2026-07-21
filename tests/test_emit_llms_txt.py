from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


MANIFEST = """\
version: 1
bindings:
  - id: overview
    type: region
    doc: README.md
    region: overview
    extractor: file
    source: {path: source.txt}
    renderer: scalar
  - id: settings
    type: symbol
    doc: docs/REFERENCE.md
    anchor: settings
    source: {path: source.txt}
projections:
  llms_txt:
    output: llms.txt
    include: [docs/CANONICAL.md]
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    source = Path(__file__).parents[1] / "src"
    environment["PYTHONPATH"] = (
        str(source) + os.pathsep + environment.get("PYTHONPATH", "")
    )
    return subprocess.run(
        [sys.executable, "-m", "clean_docs", "--root", str(root), *args],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / ".sourcebound.yml").write_text(MANIFEST)
    (root / "source.txt").write_text("Bound overview")
    (root / "README.md").write_text(
        "# Fixture\n\n<!-- sourcebound:begin overview -->\nBound overview\n"
        "<!-- sourcebound:end overview -->\n"
    )
    (root / "docs/REFERENCE.md").write_text("# Reference\n\nSettings.\n")
    (root / "docs/CANONICAL.md").write_text("# Canonical\n\nDeclared context.\n")
    return root


def test_llms_index_follows_format_and_tracks_document_content(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    output = tmp_path / "published/llms.txt"
    arguments = (
        "emit",
        "llms-txt",
        "--out",
        str(output),
        "--title",
        "Fixture docs",
        "--summary",
        "Bound documentation index.",
    )
    first = _run(root, *arguments)
    assert first.returncode == 0, first.stderr
    text = output.read_text()
    assert text.startswith("# Fixture docs\n\n> Bound documentation index.\n")
    assert "## Canonical documentation" in text
    assert "[README.md](../repo/README.md): bindings: overview; sha256:" in text
    assert (
        "[docs/REFERENCE.md](../repo/docs/REFERENCE.md): bindings: settings; sha256:"
        in text
    )
    assert (
        "[docs/CANONICAL.md](../repo/docs/CANONICAL.md): declared canonical context; sha256:"
        in text
    )
    assert str(root) not in text
    assert len(re.findall(r"sha256: [0-9a-f]{64}", text)) == 3

    (root / "README.md").write_text(
        (root / "README.md").read_text() + "\nNew guidance.\n"
    )
    second = _run(root, *arguments)
    assert second.returncode == 0
    assert output.read_text() != text


def test_llms_index_rejects_multiline_metadata(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = _run(root, "emit", "llms-txt", "--title", "Bad\nheading")
    assert result.returncode == 2
    assert "title must be one non-empty line" in result.stderr


def test_llms_index_can_publish_only_explicit_context(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    manifest = root / ".sourcebound.yml"
    manifest.write_text(
        manifest.read_text().replace(
            "    output: llms.txt\n    include: [docs/CANONICAL.md]",
            "    output: llms.txt\n    include_bound: false\n    include: [docs/CANONICAL.md]",
        )
    )

    result = _run(root, "emit", "llms-txt")

    assert result.returncode == 0, result.stderr
    text = (root / "llms.txt").read_text()
    assert "[docs/CANONICAL.md](docs/CANONICAL.md): declared canonical context" in text
    assert "README.md" not in text
    assert "docs/REFERENCE.md" not in text
