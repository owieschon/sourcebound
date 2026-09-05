from pathlib import Path

import pytest

from sourcebound.errors import ExtractionError, RegionError
from sourcebound.extractors.json_pointer import extract_json_pointer
from sourcebound.models import RegionBinding, Source
from sourcebound.regions import replace_region
from sourcebound.renderers import render
from sourcebound.snapshot import RepositorySnapshot


def _binding(pointer: str, renderer: str = "inline-scalar") -> RegionBinding:
    return RegionBinding(
        id="flag",
        doc=Path("README.md"),
        region="flag",
        extractor="json",
        source=Source(path=Path("config.json"), pointer=pointer),
        renderer=renderer,
        columns=(),
    )


def _write_config(root: Path, payload: str) -> None:
    (root / "config.json").write_text(payload, encoding="utf-8")


def test_extracts_scalar_evidence_for_inline_scalar(tmp_path: Path) -> None:
    _write_config(tmp_path, '{"should_upload_coverage_to_codecov": "y"}')
    evidence = extract_json_pointer(
        RepositorySnapshot(tmp_path), _binding("/should_upload_coverage_to_codecov")
    )
    assert evidence.kind == "scalar"
    assert evidence.value == "y"


def test_table_extraction_is_unaffected_by_scalar_support(tmp_path: Path) -> None:
    _write_config(tmp_path, '{"cases": [{"name": "a"}]}')
    evidence = extract_json_pointer(
        RepositorySnapshot(tmp_path), _binding("/cases", renderer="markdown-table")
    )
    assert evidence.kind == "table"
    assert evidence.value == [{"name": "a"}]


def test_inline_scalar_extraction_rejects_collection_value(tmp_path: Path) -> None:
    _write_config(tmp_path, '{"cases": [{"name": "a"}]}')
    with pytest.raises(ExtractionError, match="requires a scalar JSON value"):
        extract_json_pointer(RepositorySnapshot(tmp_path), _binding("/cases"))


def test_render_inline_scalar_renders_plain_text() -> None:
    from sourcebound.models import EvidenceValue, Provenance

    evidence = EvidenceValue(
        kind="scalar",
        value="n",
        provenance=Provenance("HEAD", "config.json", "/flag", "json@1", "d" * 64),
    )
    assert render(evidence, _binding("/flag")) == "n"


@pytest.mark.parametrize("value", [["a"], {"k": "v"}])
def test_render_inline_scalar_refuses_collections(value: object) -> None:
    from sourcebound.models import EvidenceValue, Provenance

    evidence = EvidenceValue(
        kind="scalar",
        value=value,
        provenance=Provenance("HEAD", "config.json", "/flag", "json@1", "d" * 64),
    )
    with pytest.raises(ExtractionError, match="requires a scalar value"):
        render(evidence, _binding("/flag"))


def test_render_inline_scalar_refuses_newline_value() -> None:
    from sourcebound.models import EvidenceValue, Provenance

    evidence = EvidenceValue(
        kind="scalar",
        value="y\nn",
        provenance=Provenance("HEAD", "config.json", "/flag", "json@1", "d" * 64),
    )
    with pytest.raises(ExtractionError, match="single-line value"):
        render(evidence, _binding("/flag"))


def test_render_inline_scalar_refuses_embedded_marker_text() -> None:
    from sourcebound.models import EvidenceValue, Provenance

    evidence = EvidenceValue(
        kind="scalar",
        value="<!-- sourcebound:begin other -->",
        provenance=Provenance("HEAD", "config.json", "/flag", "json@1", "d" * 64),
    )
    with pytest.raises(ExtractionError, match="must not contain region markers"):
        render(evidence, _binding("/flag"))


def test_replace_region_inline_replaces_only_interior_bytes_same_line() -> None:
    before = "Upload coverage: <!-- sourcebound:begin flag -->y<!-- sourcebound:end flag --> please\n"
    after = replace_region(before, "flag", "n", inline=True)
    assert after == (
        "Upload coverage: <!-- sourcebound:begin flag -->n<!-- sourcebound:end flag --> please\n"
    )


def test_replace_region_inline_refuses_multiline_span() -> None:
    before = "<!-- sourcebound:begin flag -->\ny\n<!-- sourcebound:end flag -->\n"
    with pytest.raises(RegionError, match="same line"):
        replace_region(before, "flag", "n", inline=True)


def test_replace_region_inline_refuses_newline_replacement() -> None:
    before = "<!-- sourcebound:begin flag -->y<!-- sourcebound:end flag -->\n"
    with pytest.raises(RegionError, match="must not contain newlines"):
        replace_region(before, "flag", "n\nn", inline=True)


def test_replace_region_inline_refuses_mdx_markers() -> None:
    before = "{/* sourcebound:begin flag */}y{/* sourcebound:end flag */}\n"
    with pytest.raises(RegionError, match="does not support MDX markers"):
        replace_region(before, "flag", "n", inline=True)


@pytest.mark.parametrize(
    "document",
    [
        "no markers here\n",
        "<!-- sourcebound:begin flag -->y<!-- sourcebound:begin flag -->\n",
        "<!-- sourcebound:end flag -->y<!-- sourcebound:begin flag -->\n",
        (
            "<!-- sourcebound:begin flag -->"
            "<!-- sourcebound:begin nested -->"
            "y"
            "<!-- sourcebound:end nested -->"
            "<!-- sourcebound:end flag -->\n"
        ),
    ],
)
def test_replace_region_inline_reuses_existing_marker_errors(document: str) -> None:
    with pytest.raises(RegionError):
        replace_region(document, "flag", "n", inline=True)
