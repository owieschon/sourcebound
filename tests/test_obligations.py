from pathlib import Path

from sourcebound.obligations import compile_obligations


def _repository(tmp_path: Path, readme: str) -> Path:
    root = tmp_path / "repository"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text(readme)
    (root / "src" / "service").mkdir(parents=True)
    (root / "src" / "service" / "cli.py").write_text(
        """import argparse

def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose')
    sub = parser.add_subparsers()
    sub.add_parser('serve')
    return parser
"""
    )
    return root


def test_evidence_backed_linked_cli_reference_yields_assessment_candidates(tmp_path: Path) -> None:
    root = _repository(tmp_path, "# Service\n\n[Command reference](docs/commands.md)\n")
    (root / "docs" / "commands.md").write_text(
        "# Commands\n\nRun `serve` with `--verbose` for diagnostics.\n"
    )

    report = compile_obligations(root)

    assert report.candidate_population == 2
    assert {candidate.surface_locator for candidate in report.candidates} == {"serve", "--verbose"}
    assert all(candidate.authority == "assessment" for candidate in report.candidates)
    assert all(candidate.document == "docs/commands.md" for candidate in report.candidates)
    assert all(candidate.evidence[0] == "README.md:inline:docs/commands.md" for candidate in report.candidates)


def test_ambiguous_linked_document_is_unknown_not_filename_authority(tmp_path: Path) -> None:
    root = _repository(tmp_path, "# Service\n\n[CLI](docs/CLI.md)\n")
    (root / "docs" / "CLI.md").write_text("# CLI\n\nGeneral notes without a concrete surface.\n")

    report = compile_obligations(root)

    assert report.candidates == ()
    assert [unknown.reason for unknown in report.unknowns] == ["no-local-surface-evidence"]


def test_excluded_external_and_unlinked_documents_do_not_become_candidates(tmp_path: Path) -> None:
    root = _repository(
        tmp_path,
        "# Service\n\n[Archive](docs/archive/commands.md)\n[Vendor](https://example.test/cli)\n",
    )
    (root / "docs" / "archive").mkdir()
    (root / "docs" / "archive" / "commands.md").write_text("serve --verbose\n")
    (root / "docs" / "commands.md").write_text("serve --verbose\n")

    report = compile_obligations(root)

    assert report.candidates == ()
    assert {unknown.reason for unknown in report.unknowns} == {"excluded-document", "external-link"}


def test_authority_is_unchanged(tmp_path: Path) -> None:
    root = _repository(tmp_path, "# Service\n\n[Commands](docs/commands.md)\n")
    document = root / "docs" / "commands.md"
    document.write_text("serve --verbose\n")
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    compile_obligations(root)

    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert after == before
    assert not (root / ".sourcebound.yml").exists()


def test_bounded_candidates_preserve_complete_stable_population(tmp_path: Path) -> None:
    root = _repository(tmp_path, "# Service\n\n[Commands](docs/commands.md)\n")
    (root / "docs" / "commands.md").write_text("serve --verbose\n")

    first = compile_obligations(root, limit=1)
    second = compile_obligations(root, limit=1)

    assert first.candidate_population == second.candidate_population == 2
    assert first.candidate_shown == second.candidate_shown == 1
    assert first.candidate_truncated == second.candidate_truncated == 1
    assert first.candidates[0].id == second.candidates[0].id


def test_reference_style_local_link_is_supported(tmp_path: Path) -> None:
    root = _repository(tmp_path, "# Service\n\n[Commands][reference]\n\n[reference]: docs/commands.md\n")
    (root / "docs" / "commands.md").write_text("serve --verbose\n")

    report = compile_obligations(root)

    assert report.candidate_population == 2
    assert all(candidate.evidence[0].startswith("README.md:reference:") for candidate in report.candidates)


def test_never_silent_for_unsupported_or_unsafe_material_links(tmp_path: Path) -> None:
    root = _repository(tmp_path, "# Service\n\n[Commands]\n[Escape](../commands.md)\n")

    report = compile_obligations(root)

    assert {unknown.reason for unknown in report.unknowns} == {"unsupported-link-form", "unsafe-local-link"}


def test_rejects_generic_authority(tmp_path: Path) -> None:
    root = _repository(tmp_path, "# Service\n\n[Commands](docs/commands.md)\n")
    (root / "docs" / "commands.md").write_text("# Commands\n\nNo evidence here.\n")

    report = compile_obligations(root)

    assert report.candidates == ()
    assert report.unknown_population == 1
