from pathlib import Path


PROJECT = Path(__file__).parents[1]


def _v11_section() -> str:
    specification = (PROJECT / "CLEAN_DOCS_SPEC.md").read_text()
    section = specification.split("### Version 1.1: Governed learning layer", 1)[1]
    return section.split("## 14. Test architecture", 1)[0]


def test_v11_learning_layer_is_bounded_and_starts_after_stable_v10() -> None:
    section = _v11_section()

    assert "Version 1.0 stable release is published" in section
    assert "non-blocking pilot observation window" in section
    assert "does not delay this version" in section
    assert "Do not add a fourth lesson" in section
    assert "no separate learning site or" in section


def test_v11_plan_names_each_learning_surface_and_its_proof() -> None:
    section = _v11_section()
    normalized = " ".join(section.split())

    for path in (
        "docs/learn/index.md",
        "docs/learn/tutorial-catch-a-lying-doc.md",
        "docs/learn/postmortem-the-readme-that-lied.md",
        "docs/learn/deep-dive-the-deterministic-seam.md",
    ):
        assert path in normalized

    for scenario in (
        "public repository legibility",
        "tutorial from a clean room",
        "postmortem facts cannot drift",
        "deterministic-seam boundary",
        "additive learning corpus",
        "fresh-reader learning path",
    ):
        assert f"**{scenario}**" in normalized

    assert "Link to existing reference facts instead of copying" in normalized
    assert "Receipts bind the corpus digest and task outputs" in normalized
