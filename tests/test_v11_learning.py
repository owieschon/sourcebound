from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

from clean_docs.engine import evaluate
from scripts.record_learning_tutorial import record
from scripts.render_social_preview import HEIGHT, WIDTH, render_svg


ROOT = Path(__file__).parents[1]
LEARN = ROOT / "docs/learn"


def test_public_first_screen_defines_the_product_and_routes_to_learning() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    purpose = readme.index("<!-- sourcebound:purpose -->")
    badges = readme.index("[![CI]")
    start = readme.index(
        "**[Install the stable release and catch your first stale claim]"
    )
    detail = readme.index("## Why Sourcebound exists")

    assert purpose < badges < start < detail
    assert (
        "Sourcebound is a documentation engine and CLI for maintainers who need code "
        "and prose to change together." in readme[purpose:badges]
    )
    assert "actions/workflows/ci.yml/badge.svg" in readme
    assert "img.shields.io/github/v/release" in readme
    assert "img.shields.io/badge/license-MIT" in readme


def test_core_routes_name_the_reader_job_and_keep_experimental_records_out_of_default_context() -> (
    None
):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_home = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    projection = (ROOT / "llms.txt").read_text(encoding="utf-8")

    assert "## Use Sourcebound when" in readme
    assert "Use another tool when it owns the job better." in readme
    assert "Sourcebound may not justify another" in readme
    for route in (
        "learn/tutorial-catch-a-lying-doc.md",
        "SUPPORT.md",
        "REFERENCE.md",
        "CLI.md",
        "SECURITY_MODEL.md",
        "ECOSYSTEM.md",
    ):
        assert route in docs_home
    for core_document in (
        "docs/README.md",
        "docs/ECOSYSTEM.md",
        "docs/learn/tutorial-catch-a-lying-doc.md",
    ):
        assert core_document in projection
    assert "[README.md](README.md): bindings: product-overview" in projection
    for experimental_record in (
        "docs/EVALUATION.md",
        "docs/FEEDBACK.md",
        "docs/IMPROVEMENTS.md",
        "docs/RELEASES.md",
    ):
        assert experimental_record not in projection


def test_social_preview_is_current_legible_and_at_repository_aspect_ratio() -> None:
    svg = (ROOT / "docs/assets/sourcebound-social.svg").read_text(encoding="utf-8")
    png = (ROOT / "docs/assets/sourcebound-social.png").read_bytes()

    assert svg == render_svg()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (WIDTH, HEIGHT)
    for phrase in (
        "Docs that answer to code.",
        "Repository sources",
        "Source bindings",
        "Deterministic check",
        "Drift fails before merge.",
    ):
        assert phrase in svg
    assert "<title" in svg and "<desc" in svg


def test_public_repository_legibility_e2e() -> None:
    test_public_first_screen_defines_the_product_and_routes_to_learning()
    test_social_preview_is_current_legible_and_at_repository_aspect_ratio()


def test_learning_surface_contains_only_the_index_and_two_lessons() -> None:
    paths = sorted(path.name for path in LEARN.iterdir())
    assert paths == [
        "deep-dive-the-deterministic-seam.md",
        "index.md",
        "tutorial-catch-a-lying-doc.md",
    ]
    for path in LEARN.iterdir():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert lines[2] == "<!-- sourcebound:policy register-v2 -->"
        assert lines[3] == "<!-- sourcebound:purpose -->"


def test_learning_index_routes_each_reader_job_without_copying_reference() -> None:
    index = (LEARN / "index.md").read_text(encoding="utf-8")
    routing_table = index.split("| If you need to...", 1)[1]
    ordered = (
        "../../README.md",
        "tutorial-catch-a-lying-doc.md",
        "deep-dive-the-deterministic-seam.md",
    )
    positions = [routing_table.index(path) for path in ordered]
    assert positions == sorted(positions)
    assert "../CLI.md" in index
    assert "../SUPPORT.md" in index
    assert "../SECURITY_MODEL.md" in index


def test_published_tutorial_runs_the_observed_drift_loop(tmp_path: Path) -> None:
    wrapper = tmp_path / "sourcebound"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"export PYTHONPATH={ROOT / 'src'}\n"
        f'exec {sys.executable} -m clean_docs "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    first = record(wrapper)
    second = record(wrapper)
    committed = json.loads(
        (ROOT / ".sourcebound/learning/tutorial-evidence.json").read_text(
            encoding="utf-8"
        )
    )

    assert first == second == committed
    assert [step["exit"] for step in first["steps"]] == [0, 1, 0, 0, 0]


def test_deep_dive_claims_resolve_to_deterministic_implementation_sources() -> None:
    ids = {
        "deterministic-seam-evidence",
        "deterministic-seam-phrasing",
        "deterministic-seam-gate",
    }
    results = [
        result
        for result in evaluate(ROOT, ROOT / ".sourcebound.yml")
        if result.binding_id in ids
    ]

    assert {result.binding_id for result in results} == ids
    assert not any(result.changed for result in results)
    sources = {result.provenance.path for result in results}
    assert sources == {
        "src/clean_docs/engine.py",
        "src/clean_docs/phrasing.py",
        "src/clean_docs/outcomes.py",
    }


def test_llms_projection_contains_every_learning_page() -> None:
    projection = (ROOT / "llms.txt").read_text(encoding="utf-8")
    for path in sorted(LEARN.iterdir()):
        assert path.relative_to(ROOT).as_posix() in projection


def test_additive_learning_corpus_passes_audit_projection_and_links() -> None:
    test_learning_surface_contains_only_the_index_and_two_lessons()
    test_learning_index_routes_each_reader_job_without_copying_reference()
    test_llms_projection_contains_every_learning_page()
    for document in LEARN.iterdir():
        text = document.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 150
    for command in (
        [sys.executable, "-m", "clean_docs", "--root", str(ROOT), "audit"],
        [sys.executable, "-m", "clean_docs", "--root", str(ROOT), "project", "--check"],
    ):
        result = subprocess.run(
            command,
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT / "src")},
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
