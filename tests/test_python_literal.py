from pathlib import Path

import pytest

from sourcebound.errors import ExtractionError
from sourcebound.extractors import extract_python_literal
from sourcebound.models import RegionBinding, Source
from sourcebound.snapshot import RepositorySnapshot


def test_rejects_unresolved_names_in_factual_source(tmp_path: Path) -> None:
    source = tmp_path / "values.py"
    source.write_text("DEFAULT_TIER = 2\nACTIONS = [{'name': 'draft', 'tier': DEFAULT_TIER}]\n")
    binding = RegionBinding(
        id="actions",
        doc=Path("README.md"),
        region="actions",
        extractor="python-literal",
        source=Source(Path("values.py"), "ACTIONS"),
        renderer="markdown-table",
        columns=("name", "tier"),
    )
    with pytest.raises(ExtractionError, match="Name"):
        extract_python_literal(RepositorySnapshot(tmp_path), binding)


def test_extracts_a_scalar_without_importing_the_module(tmp_path: Path) -> None:
    source = tmp_path / "values.py"
    source.write_text('OVERVIEW = "Bound " + "summary"\nraise RuntimeError("must not run")\n')
    binding = RegionBinding(
        id="overview",
        doc=Path("README.md"),
        region="overview",
        extractor="python-literal",
        source=Source(Path("values.py"), "OVERVIEW"),
        renderer="scalar",
        columns=(),
    )

    evidence = extract_python_literal(RepositorySnapshot(tmp_path), binding)

    assert evidence.kind == "scalar"
    assert evidence.value == "Bound summary"


def test_extracts_a_markdown_fragment_without_collapsing_paragraphs(tmp_path: Path) -> None:
    source = tmp_path / "values.py"
    source.write_text('OVERVIEW = "First claim.\\n\\nSecond claim."\n')
    binding = RegionBinding(
        id="overview",
        doc=Path("README.md"),
        region="overview",
        extractor="python-literal",
        source=Source(Path("values.py"), "OVERVIEW"),
        renderer="markdown-fragment",
        columns=(),
    )

    evidence = extract_python_literal(RepositorySnapshot(tmp_path), binding)

    assert evidence.kind == "markdown"
    assert evidence.value == "First claim.\n\nSecond claim."
