from __future__ import annotations

import subprocess
from pathlib import Path

from clean_docs.accessibility import check_accessibility
from clean_docs.audit import audit
from clean_docs.mdx import parse_mdx
from clean_docs.policy import check_document
from clean_docs.standard import load_default_pack


def rules(text: str) -> list[str]:
    return [
        finding.rule
        for finding in check_accessibility("docs/guide.md", text, load_default_pack())
    ]


def test_fenced_code_declares_its_reader_action() -> None:
    assert rules("Run this:\n\n```\nsourcebound audit\n```\n") == [
        "code-block-language"
    ]
    assert rules("Run this:\n\n```bash\nsourcebound audit\n```\n") == []
    assert rules("Expected output:\n\n```text\ncomplete\n```\n") == []


def test_mermaid_diagram_keeps_an_adjacent_text_equivalent() -> None:
    missing = "```mermaid\ngraph LR\nA --> B\n```\n"
    complete = missing + "\nDiagram: A sends the checked result to B.\n"

    assert rules(missing) == ["diagram-text-equivalent"]
    assert rules(complete) == []


def test_images_need_meaningful_or_explicitly_decorative_alternatives() -> None:
    assert rules("![](queue.png)\n") == ["image-alternative"]
    assert rules("![Queue waiting for a worker](queue.png)\n") == []
    assert rules(
        "<!-- sourcebound:decorative-image -->\n\n![](divider.png)\n"
    ) == []
    assert rules("<img src=\"queue.png\">\n") == ["image-alternative"]
    assert rules("<img src=\"divider.png\" alt=\"\" role=\"presentation\">\n") == []


def test_examples_inside_fences_do_not_create_image_findings() -> None:
    text = (
        "Show the syntax:\n\n"
        "```markdown\n"
        "![](example.png)\n"
        "<img src=\"example.png\">\n"
        "```\n\n"
        "Inline forms such as `![](example.png)` and `<img src=\"example.png\">` "
        "are syntax, not images.\n"
    )
    assert rules(text) == []


def test_mdx_policy_uses_unmasked_source_for_semantic_checks() -> None:
    source = (
        "# Architecture\n\n"
        "{/* sourcebound:policy register-v2 */}\n\n"
        "```mermaid\n"
        "graph LR\n"
        "A --> B\n"
        "```\n"
    )
    policy_text = parse_mdx(source).policy_text(source)

    assert "```mermaid" not in policy_text
    assert "diagram-text-equivalent" in {
        finding.rule
        for finding in check_document(
            "docs/architecture.mdx",
            policy_text,
            load_default_pack(),
            semantic_text=source,
        )
    }


def test_registered_architecture_enforces_accessible_visuals(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    document = root / "docs/architecture.md"
    document.parent.mkdir(parents=True)
    document.write_text(
        "# Architecture\n\n"
        "<!-- sourcebound:policy register-v2 -->\n\n"
        "```mermaid\n"
        "graph LR\n"
        "A --> B\n"
        "```\n\n"
        "![](flow.png)\n"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    report = audit(root)

    assert {finding.rule for finding in report.findings} == {
        "diagram-text-equivalent",
        "image-alternative",
    }
