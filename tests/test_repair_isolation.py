from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from sourcebound.engine import write_results
from sourcebound.errors import ConfigurationError
from sourcebound.models import BindingResult, Provenance

from test_e2e_region import MANIFEST, README, SOURCE_THREE, _repo, _run


def _region_result(doc: str, expected: str, observed: str = "old\n") -> BindingResult:
    provenance = Provenance("HEAD", doc, "fixture", "extractor@1", "hash")
    return BindingResult(
        binding_id=doc,
        doc=doc,
        changed=True,
        expected=expected,
        observed=observed,
        diff="",
        provenance=provenance,
        binding_type="region",
    )


def test_drive_rejects_symlinked_parent_directory_escape(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "README.md").write_text(README)
    (root / "docs").symlink_to(outside, target_is_directory=True)
    (root / ".sourcebound.yml").write_text(MANIFEST.replace("doc: README.md", "doc: docs/README.md"))
    (root / "src/actions.py").write_text(SOURCE_THREE)

    driven = _run(root, "drive", "--format", "json")

    assert driven.returncode == 2, driven.stdout + driven.stderr
    assert "escapes the repository through a symlink" in driven.stderr
    assert (outside / "README.md").read_text() == README


def test_drive_rejects_direct_symlink_document_target(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    outside_file = tmp_path / "outside-readme.md"
    outside_file.write_text(README)
    (root / "README.md").unlink()
    (root / "README.md").symlink_to(outside_file)
    (root / "src/actions.py").write_text(SOURCE_THREE)

    driven = _run(root, "drive", "--format", "json")

    assert driven.returncode == 2, driven.stdout + driven.stderr
    assert "escapes the repository through a symlink" in driven.stderr
    assert outside_file.read_text() == README


def test_drive_still_repairs_valid_nested_document_path(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").unlink()
    (root / "docs").mkdir()
    (root / "docs/README.md").write_text(README)
    (root / ".sourcebound.yml").write_text(MANIFEST.replace("doc: README.md", "doc: docs/README.md"))
    (root / "src/actions.py").write_text(SOURCE_THREE)

    driven = _run(root, "drive", "--format", "json")

    assert driven.returncode == 0, driven.stderr
    assert "| call | 3 | true |" in (root / "docs/README.md").read_text()


def test_write_results_preflights_full_set_before_first_mutation(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("old\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)

    results = [
        _region_result("README.md", "new\n"),
        _region_result("escape/secret.txt", "new\n"),
    ]

    with pytest.raises(ConfigurationError):
        write_results(root, results)

    assert (root / "README.md").read_text() == "old\n"
    assert not (outside / "secret.txt").exists()


def test_write_results_rejects_malformed_external_doc_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(ConfigurationError, match="must stay inside the repository"):
        write_results(root, [_region_result("../escape.txt", "new\n")])

    with pytest.raises(ConfigurationError, match="must stay inside the repository"):
        write_results(root, [_region_result("/etc/escape.txt", "new\n")])

    assert not (root.parent / "escape.txt").exists()


@pytest.mark.parametrize(
    "resolution_error",
    [OSError("boom"), RuntimeError("Symlink loop from 'a' to 'a'")],
)
def test_write_results_reports_unresolvable_paths_as_configuration_error(
    tmp_path: Path, resolution_error: Exception
) -> None:
    # Path.resolve() raises OSError on some platforms and RuntimeError on others
    # (older CPython's symlink-loop detection); a real filesystem loop resolves
    # permissively on this environment's Python, so the failure path is
    # exercised directly rather than relying on OS-specific loop behavior.
    root = tmp_path / "repo"
    root.mkdir()

    with mock.patch.object(Path, "resolve", side_effect=resolution_error):
        with pytest.raises(ConfigurationError, match="cannot resolve bound document"):
            write_results(root, [_region_result("doc.md", "new\n")])
