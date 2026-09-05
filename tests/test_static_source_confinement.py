from __future__ import annotations

from pathlib import Path

import pytest

from sourcebound.engine import drive
from sourcebound.errors import ExtractionError
from sourcebound.snapshot import RepositorySnapshot

README_TEMPLATE = """\
# Fixture

<!-- sourcebound:begin example -->
stale
<!-- sourcebound:end example -->
"""

MANIFEST_TEMPLATE = """\
version: 1
bindings:
  - id: example
    type: region
    doc: README.md
    region: example
    extractor: file
    source: {{path: {source_path}}}
    renderer: fenced-text
    language: text
"""


def _repo(tmp_path: Path, source_path: str) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text(README_TEMPLATE)
    (root / ".sourcebound.yml").write_text(
        MANIFEST_TEMPLATE.format(source_path=source_path)
    )
    return root


def test_drive_refuses_worktree_symlink_that_escapes_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside-sentinel.json"
    outside.write_text('{"leaked": true}\n')

    root = _repo(tmp_path, "linked.json")
    (root / "linked.json").symlink_to(outside)
    before = (root / "README.md").read_text()

    with pytest.raises(ExtractionError, match="source path escapes repository"):
        drive(root, root / ".sourcebound.yml")

    assert (root / "README.md").read_text() == before
    assert "leaked" not in (root / "README.md").read_text()


def test_drive_follows_in_root_symlink(tmp_path: Path) -> None:
    root = _repo(tmp_path, "linked.txt")
    (root / "actual.txt").write_text("real content\n")
    (root / "linked.txt").symlink_to(root / "actual.txt")

    drive(root, root / ".sourcebound.yml")

    assert "real content" in (root / "README.md").read_text()


def test_read_text_rejects_out_of_root_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    (root / "escape.txt").symlink_to(outside)

    with pytest.raises(ExtractionError, match="source path escapes repository"):
        RepositorySnapshot(root).read_text(Path("escape.txt"))


def test_read_text_allows_in_root_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "actual.txt").write_text("real\n")
    (root / "linked.txt").symlink_to(root / "actual.txt")

    assert RepositorySnapshot(root).read_text(Path("linked.txt")) == "real\n"


def test_read_text_reports_ordinary_error_for_missing_source(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(ExtractionError, match="cannot read source"):
        RepositorySnapshot(root).read_text(Path("missing.txt"))


def test_read_text_reports_ordinary_error_for_dangling_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "dangling.txt").symlink_to(root / "does-not-exist.txt")

    with pytest.raises(ExtractionError, match="cannot read source"):
        RepositorySnapshot(root).read_text(Path("dangling.txt"))


def test_read_text_reports_ordinary_error_for_symlink_loop(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "loop-a.txt").symlink_to(root / "loop-b.txt")
    (root / "loop-b.txt").symlink_to(root / "loop-a.txt")

    with pytest.raises(ExtractionError, match="cannot read source"):
        RepositorySnapshot(root).read_text(Path("loop-a.txt"))
