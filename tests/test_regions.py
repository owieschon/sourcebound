from pathlib import Path

import pytest

from clean_docs.errors import RegionError
from clean_docs.regions import atomic_write, replace_region


def test_replaces_only_marker_body() -> None:
    before = "before\n<!-- clean-docs:begin x -->\nold\n<!-- clean-docs:end x -->\nafter\n"
    after = replace_region(before, "x", "new")
    assert after == "before\n<!-- clean-docs:begin x -->\nnew\n<!-- clean-docs:end x -->\nafter\n"


@pytest.mark.parametrize(
    "document",
    [
        "no markers",
        "<!-- clean-docs:begin x -->\nmissing end",
        "<!-- clean-docs:end x -->\n<!-- clean-docs:begin x -->",
    ],
)
def test_rejects_corrupt_markers(document: str) -> None:
    with pytest.raises(RegionError):
        replace_region(document, "x", "new")


def test_composes_two_regions_without_touching_author_text() -> None:
    document = (
        "intro\n"
        "<!-- clean-docs:begin a -->\nold a\n<!-- clean-docs:end a -->\n"
        "middle\n"
        "<!-- clean-docs:begin b -->\nold b\n<!-- clean-docs:end b -->\n"
        "ending\n"
    )
    first = replace_region(document, "a", "new a")
    second = replace_region(first, "b", "new b")
    assert second.startswith("intro\n<!-- clean-docs:begin a -->\nnew a")
    assert "<!-- clean-docs:end a -->\nmiddle\n<!-- clean-docs:begin b -->" in second
    assert second.endswith("\nnew b\n<!-- clean-docs:end b -->\nending\n")


def test_replaces_mdx_comment_region_without_touching_surrounding_bytes() -> None:
    before = (
        "# Guide\n\n"
        "{/* clean-docs:begin commands */}\n"
        "| old |\n"
        "{/* clean-docs:end commands */}\n\n"
        "<Callout>Author-owned text.</Callout>\n"
    )

    after = replace_region(before, "commands", "| new |")

    assert after == (
        "# Guide\n\n"
        "{/* clean-docs:begin commands */}\n"
        "| new |\n"
        "{/* clean-docs:end commands */}\n\n"
        "<Callout>Author-owned text.</Callout>\n"
    )


def test_rejects_mixed_markdown_and_mdx_marker_forms() -> None:
    document = (
        "<!-- clean-docs:begin x -->\n"
        "old\n"
        "{/* clean-docs:end x */}\n"
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
