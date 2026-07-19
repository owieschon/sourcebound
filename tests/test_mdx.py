from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from clean_docs.mdx import (
    MDX_PARSER_ID,
    MdxParserError,
    parse_mdx,
    parse_mdx_documents,
)


def test_parser_returns_semantic_nodes_and_masks_non_prose(tmp_path: Path) -> None:
    side_effect = tmp_path / "executed"
    source = (
        "---\n"
        "title: Structural guide\n"
        "---\n\n"
        f"import SideEffect from '{side_effect.as_posix()}'\n\n"
        "# Structural [guide](./guide.md)\n\n"
        "<Callout tone=\"[attribute](./missing-attribute.md)\">\n"
        "## Nested heading\n\n"
        "Read [details](./details.md).\n"
        "</Callout>\n\n"
        "```md\n"
        "## Fake heading\n"
        "[fake](./missing-fence.md)\n"
        "```\n\n"
        "{/* [fake](./missing-comment.md) */}\n"
    )

    parsed = parse_mdx(source)

    assert parsed.parser == MDX_PARSER_ID
    assert parsed.digest == hashlib.sha256(source.encode()).hexdigest()
    assert [link.url for link in parsed.links] == ["./guide.md", "./details.md"]
    assert [
        (node.depth, node.text)
        for node in parsed.nodes
        if node.type == "heading"
    ] == [(1, "Structural guide"), (2, "Nested heading")]
    assert "missing-fence.md" not in parsed.masked_text
    assert "missing-comment.md" not in parsed.masked_text
    assert not side_effect.exists()


def test_parser_batches_valid_and_invalid_documents_without_laundering() -> None:
    parsed, errors = parse_mdx_documents(
        {
            "good.mdx": "# Good\n\n<Component />\n",
            "bad.mdx": "# Bad\n\n<Component>\n",
        }
    )

    assert set(parsed) == {"good.mdx"}
    assert set(errors) == {"bad.mdx"}
    assert "closing tag" in errors["bad.mdx"]


def test_parser_preserves_utf8_byte_locations() -> None:
    parsed = parse_mdx("# Café\n\n<Badge>🥐</Badge>\n")
    jsx = next(node for node in parsed.nodes if node.type.startswith("mdxJsx"))

    assert jsx.start_byte == len("# Café\n\n".encode())
    assert jsx.end_byte == len("# Café\n\n<Badge>🥐</Badge>".encode())


def test_policy_controls_have_an_mdx_safe_comment_form() -> None:
    source = (
        "# Guide\n\n"
        "{/* clean-docs:policy register-v2 */}\n"
        "{/* clean-docs:role reference */}\n"
        "{/* clean-docs:purpose */}\n"
        "Look up the current contract.\n"
        "{/* clean-docs:end purpose */}\n"
    )

    policy_text = parse_mdx(source).policy_text(source)

    assert "<!-- clean-docs:policy register-v2 -->" in policy_text
    assert "<!-- clean-docs:role reference -->" in policy_text
    assert "<!-- clean-docs:purpose -->" in policy_text
    assert "Look up the current contract." in policy_text


def test_parser_rejects_malformed_mdx() -> None:
    with pytest.raises(MdxParserError, match="closing tag"):
        parse_mdx("# Guide\n\n<Component>\n")
