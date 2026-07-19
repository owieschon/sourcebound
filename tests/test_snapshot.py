from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from clean_docs.errors import ExtractionError
from clean_docs.snapshot import RepositorySnapshot


def _commit(root: Path) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "snapshot",
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def test_snapshot_materializes_internal_relative_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    nested = root / "playground/nextjs"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "playground/.pnpmfile.cjs").write_text("module.exports = {}\n")
    (nested / ".pnpmfile.cjs").symlink_to("../.pnpmfile.cjs")
    ref = _commit(root)

    with RepositorySnapshot(root, ref).materialized_root() as snapshot:
        linked = snapshot / "playground/nextjs/.pnpmfile.cjs"
        assert linked.is_symlink()
        assert linked.read_text() == "module.exports = {}\n"


def test_snapshot_rejects_symlink_that_escapes_root(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "escape").symlink_to("../../outside")
    ref = _commit(root)

    with pytest.raises(ExtractionError, match="unsafe path"):
        with RepositorySnapshot(root, ref).materialized_root():
            pass


def test_snapshot_materializes_only_selected_project(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    (root / "apps/docs").mkdir(parents=True)
    (root / "large-sibling").mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "apps/docs/README.md").write_text("# Docs\n")
    (root / "large-sibling/payload.txt").write_text("not selected\n")
    ref = _commit(root)

    with RepositorySnapshot(root, ref).materialized_root(
        paths=(Path("apps/docs"),)
    ) as snapshot:
        assert (snapshot / "apps/docs/README.md").read_text() == "# Docs\n"
        assert not (snapshot / "large-sibling").exists()


def test_selected_project_includes_internal_symlink_targets(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    project = root / "apps/docs"
    shared = root / "shared"
    project.mkdir(parents=True)
    shared.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (shared / "source.md").write_text("# Shared source\n")
    (project / "source.md").symlink_to("../../shared/source.md")
    ref = _commit(root)

    with RepositorySnapshot(root, ref).materialized_root(
        paths=(Path("apps/docs"),)
    ) as snapshot:
        linked = snapshot / "apps/docs/source.md"
        assert linked.is_symlink()
        assert linked.read_text() == "# Shared source\n"
        assert not (snapshot / "large-sibling").exists()


@pytest.mark.parametrize(
    "link_target",
    (
        r"C:\outside",
        r"\\server\share\outside",
        r"..\..\..\outside",
    ),
)
def test_snapshot_rejects_windows_shaped_symlink_targets(
    tmp_path: Path,
    link_target: str,
) -> None:
    root = tmp_path / "repository"
    project = root / "apps/docs"
    project.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (project / "escape").symlink_to(link_target)
    ref = _commit(root)

    with pytest.raises(ExtractionError, match="unsafe path"):
        with RepositorySnapshot(root, ref).materialized_root():
            pass


def test_snapshot_rejects_windows_shaped_member_traversal(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / r"docs\..\outside.md").write_text("# Outside\n")
    ref = _commit(root)

    with pytest.raises(ExtractionError, match="unsafe path"):
        with RepositorySnapshot(root, ref).materialized_root():
            pass


def test_selected_project_rejects_symlink_to_repository_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    project = root / "apps/docs"
    project.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (project / "repository-root").symlink_to("../..")
    ref = _commit(root)

    with pytest.raises(
        ExtractionError,
        match="selected snapshot symlink expands scope to repository root",
    ):
        with RepositorySnapshot(root, ref).materialized_root(
            paths=(Path("apps/docs"),)
        ):
            pass


def test_snapshot_rejects_selected_path_that_escapes_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "README.md").write_text("# Docs\n")
    ref = _commit(root)

    with pytest.raises(ExtractionError, match="snapshot path escapes repository"):
        with RepositorySnapshot(root, ref).materialized_root(
            paths=(Path("../outside"),)
        ):
            pass
