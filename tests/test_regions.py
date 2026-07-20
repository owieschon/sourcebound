from pathlib import Path

import pytest

from clean_docs.errors import RegionError
from clean_docs.regions import atomic_write, replace_region


def test_replaces_only_marker_body() -> None:
    before = "before\n<!-- sourcebound:begin x -->\nold\n<!-- sourcebound:end x -->\nafter\n"
    after = replace_region(before, "x", "new")
    assert after == "before\n<!-- sourcebound:begin x -->\nnew\n<!-- sourcebound:end x -->\nafter\n"


@pytest.mark.parametrize(
    "document",
    [
        "no markers",
        "<!-- sourcebound:begin x -->\nmissing end",
        "<!-- sourcebound:end x -->\n<!-- sourcebound:begin x -->",
    ],
)
def test_rejects_corrupt_markers(document: str) -> None:
    with pytest.raises(RegionError):
        replace_region(document, "x", "new")


def test_composes_two_regions_without_touching_author_text() -> None:
    document = (
        "intro\n"
        "<!-- sourcebound:begin a -->\nold a\n<!-- sourcebound:end a -->\n"
        "middle\n"
        "<!-- sourcebound:begin b -->\nold b\n<!-- sourcebound:end b -->\n"
        "ending\n"
    )
    first = replace_region(document, "a", "new a")
    second = replace_region(first, "b", "new b")
    assert second.startswith("intro\n<!-- sourcebound:begin a -->\nnew a")
    assert "<!-- sourcebound:end a -->\nmiddle\n<!-- sourcebound:begin b -->" in second
    assert second.endswith("\nnew b\n<!-- sourcebound:end b -->\nending\n")


def test_replaces_mdx_comment_region_without_touching_surrounding_bytes() -> None:
    before = (
        "# Guide\n\n"
        "{/* sourcebound:begin commands */}\n"
        "| old |\n"
        "{/* sourcebound:end commands */}\n\n"
        "<Callout>Author-owned text.</Callout>\n"
    )

    after = replace_region(before, "commands", "| new |")

    assert after == (
        "# Guide\n\n"
        "{/* sourcebound:begin commands */}\n"
        "| new |\n"
        "{/* sourcebound:end commands */}\n\n"
        "<Callout>Author-owned text.</Callout>\n"
    )


def test_rejects_mixed_markdown_and_mdx_marker_forms() -> None:
    document = (
        "<!-- sourcebound:begin x -->\n"
        "old\n"
        "{/* sourcebound:end x */}\n"
    )

    with pytest.raises(RegionError, match="exactly one Markdown or MDX marker form"):
        replace_region(document, "x", "new")


def test_atomic_write_preserves_destination_mode(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("old")
    path.chmod(0o640)
    atomic_write(path, "new")
    assert path.read_text() == "new"
    assert path.stat().st_mode & 0o777 == 0o640
