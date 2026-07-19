from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from clean_docs.models import ReviewContract, ReviewLocator
from clean_docs.review_contracts import evaluate_review_contract


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "fixture@example.test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Fixture"],
        check=True,
    )
    return root


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", message],
        check=True,
    )
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _delivery_contract() -> ReviewContract:
    return ReviewContract(
        id="result-page-delivery",
        mode="observe",
        sources=(
            ReviewLocator(
                id="default-pagination-test",
                path=Path("tests/test_delivery.py"),
                extractor="python-symbol",
                locator="TestDelivery.test_fetch_caps_first_page",
            ),
        ),
        targets=(
            ReviewLocator(
                id="large-result-instructions",
                path=Path("docs/delivery.md"),
                extractor="markdown-section",
                locator="#reading-large-results",
            ),
        ),
    )


def _write_pagination_base(root: Path) -> str:
    _write(
        root,
        "tests/test_delivery.py",
        """
class TestDelivery:
    def test_fetch_returns_short_body(self):
        assert fetch("short").body == "short"
""".lstrip(),
    )
    _write(
        root,
        "docs/delivery.md",
        """
# Delivery

## Reading large results

Fetch once and read the returned body.

## Publishing a result

Use the current version when writing.
""".lstrip(),
    )
    return _commit(root, "baseline")


def _add_pagination_behavior_test(root: Path) -> None:
    _write(
        root,
        "tests/test_delivery.py",
        """
class TestDelivery:
    def test_fetch_returns_short_body(self):
        assert fetch("short").body == "short"

    def test_fetch_caps_first_page(self):
        response = fetch("x" * 8050)
        assert len(response.body) == 8000
        assert response.body_next_offset == 8000
""".lstrip(),
    )


def test_new_behavior_with_unchanged_instruction_recommends_review(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    base = _write_pagination_base(root)
    _add_pagination_behavior_test(root)
    head = _commit(root, "add default pagination behavior")

    result = evaluate_review_contract(
        root,
        _delivery_contract(),
        base=base,
        head=head,
    )

    assert result.state == "review-recommended"
    assert result.sources[0].state == "added"
    assert result.targets[0].state == "unchanged"
    assert not result.semantic_correctness_checked
    assert result.as_dict()["semantic_correctness_checked"] is False


def test_behavior_and_relevant_instruction_change_are_cochanged(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    base = _write_pagination_base(root)
    _add_pagination_behavior_test(root)
    _write(
        root,
        "docs/delivery.md",
        """
# Delivery

## Reading large results

Read the first page, then pass `body_next_offset` as `body_offset`.
Continue until `body_next_offset` is null.

## Publishing a result

Use the current version when writing.
""".lstrip(),
    )
    head = _commit(root, "document default pagination")

    result = evaluate_review_contract(
        root,
        _delivery_contract(),
        base=base,
        head=head,
    )

    assert result.state == "cochanged"
    assert result.sources[0].state == "added"
    assert result.targets[0].state == "changed"
    assert not result.semantic_correctness_checked


def test_unrelated_code_and_whitespace_changes_are_unaffected(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    _write(
        root,
        "src/delivery.py",
        '''
class Delivery:
    def fetch(self, request):
        """Return one body page."""
        body_length = request.get("body_length")
        return body_length

    def health(self):
        return "ok"


DEFAULT_BODY_PAGE_LENGTH = 8000
'''.lstrip(),
    )
    _write(
        root,
        "docs/delivery.md",
        """
# Delivery

## Fetching a body

Fetch the body once and inspect the result.

## Health

The service reports its health.
""".lstrip(),
    )
    base = _commit(root, "baseline")

    _write(
        root,
        "src/delivery.py",
        '''
class Delivery:
    def fetch( self, request ):
        """A rewritten docstring does not change behavior."""
        # Comments and formatting are not contract evidence.
        body_length=request.get( "body_length" )
        return body_length

    def health(self):
        return "changed"


DEFAULT_BODY_PAGE_LENGTH = 4000
'''.lstrip(),
    )
    _write(
        root,
        "docs/delivery.md",
        """
# Delivery

## Fetching a body

Fetch   the body once
and inspect the result.

## Health

The service now reports detailed health.
""".lstrip(),
    )
    head = _commit(root, "unrelated implementation and whitespace")
    contract = ReviewContract(
        id="fetch-result",
        mode="observe",
        sources=(
            ReviewLocator(
                id="method",
                path=Path("src/delivery.py"),
                extractor="python-symbol",
                locator="Delivery.fetch",
            ),
        ),
        targets=(
            ReviewLocator(
                id="instructions",
                path=Path("docs/delivery.md"),
                extractor="markdown-section",
                locator="#fetching-a-body",
            ),
        ),
    )

    result = evaluate_review_contract(root, contract, base=base, head=head)

    assert result.state == "unaffected"
    assert result.sources[0].state == "unchanged"
    assert result.targets[0].state == "unchanged"


def test_missing_locator_is_unknown(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _write(root, "src/delivery.py", "class Delivery:\n    pass\n")
    _write(root, "docs/delivery.md", "# Delivery\n\n## Fetching a body\n\nFetch it.\n")
    base = _commit(root, "baseline")
    _write(root, "docs/delivery.md", "# Delivery\n\n## Fetching a body\n\nFetch it now.\n")
    head = _commit(root, "edit instructions")
    contract = ReviewContract(
        id="missing-source",
        mode="observe",
        sources=(
            ReviewLocator(
                id="missing-method",
                path=Path("src/delivery.py"),
                extractor="python-symbol",
                locator="Delivery.fetch",
            ),
        ),
        targets=(
            ReviewLocator(
                id="instructions",
                path=Path("docs/delivery.md"),
                extractor="markdown-section",
                locator="#fetching-a-body",
            ),
        ),
    )

    result = evaluate_review_contract(root, contract, base=base, head=head)

    assert result.state == "unknown"
    assert result.sources[0].state == "unknown"
    assert result.sources[0].base_digest is None
    assert result.sources[0].head_digest is None


def test_removed_source_recommends_review(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _write(
        root,
        "src/skills.py",
        "def fetch_page():\n    return {'body_next_offset': 8000}\n",
    )
    _write(
        root,
        "docs/skills.md",
        "# Skills\n\n## Fetching pages\n\nContinue from `body_next_offset`.\n",
    )
    base = _commit(root, "baseline")
    _write(root, "src/skills.py", "def fetch_all():\n    return 'complete'\n")
    head = _commit(root, "remove pagination behavior")
    contract = ReviewContract(
        id="pagination-removal",
        mode="observe",
        sources=(
            ReviewLocator(
                id="fetch-page",
                path=Path("src/skills.py"),
                extractor="python-symbol",
                locator="fetch_page",
            ),
        ),
        targets=(
            ReviewLocator(
                id="fetching-pages",
                path=Path("docs/skills.md"),
                extractor="markdown-section",
                locator="#fetching-pages",
            ),
        ),
    )

    result = evaluate_review_contract(root, contract, base=base, head=head)

    assert result.state == "review-recommended"
    assert result.sources[0].state == "removed"
    assert result.targets[0].state == "unchanged"


def test_missing_head_target_is_unknown(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _write(root, "src/skills.py", "PAGE_LENGTH = 8000\n")
    _write(
        root,
        "docs/skills.md",
        "# Skills\n\n## Fetching pages\n\nPages contain 8000 characters.\n",
    )
    base = _commit(root, "baseline")
    _write(root, "src/skills.py", "PAGE_LENGTH = 4000\n")
    _write(root, "docs/skills.md", "# Skills\n")
    head = _commit(root, "remove page instructions")
    contract = ReviewContract(
        id="missing-head-target",
        mode="observe",
        sources=(
            ReviewLocator(
                id="page-length",
                path=Path("src/skills.py"),
                extractor="python-symbol",
                locator="PAGE_LENGTH",
            ),
        ),
        targets=(
            ReviewLocator(
                id="fetching-pages",
                path=Path("docs/skills.md"),
                extractor="markdown-section",
                locator="#fetching-pages",
            ),
        ),
    )

    result = evaluate_review_contract(root, contract, base=base, head=head)

    assert result.state == "unknown"
    assert result.sources[0].state == "changed"
    assert result.targets[0].state == "removed"
    assert result.targets[0].head_digest is None


@pytest.mark.parametrize(
    ("filename", "base_content", "head_content"),
    [
        (
            "contract.json",
            '{"api":{"paging":{"mode":"full","terminal":null}}}\n',
            '{"api":{"paging":{"terminal":null,"mode":"paged"}}}\n',
        ),
        (
            "contract.yaml",
            "api:\n  paging:\n    mode: full\n    terminal: null\n",
            "api:\n  paging:\n    terminal: null\n    mode: paged\n",
        ),
        (
            "contract.toml",
            '[api.paging]\nmode = "full"\nterminal = "null"\n',
            '[api.paging]\nterminal = "null"\nmode = "paged"\n',
        ),
    ],
)
def test_structured_data_uses_canonical_json_pointer(
    tmp_path: Path,
    filename: str,
    base_content: str,
    head_content: str,
) -> None:
    root = _repository(tmp_path)
    _write(root, filename, base_content)
    _write(root, "docs/contract.md", "# Contract\n\n## Body delivery\n\nBodies are complete.\n")
    base = _commit(root, "baseline")
    _write(root, filename, head_content)
    head = _commit(root, "change delivery contract")
    contract = ReviewContract(
        id=f"structured-{Path(filename).suffix}",
        mode="observe",
        sources=(
            ReviewLocator(
                id="delivery-fact",
                path=Path(filename),
                extractor="structured-data",
                locator="/api/paging",
            ),
        ),
        targets=(
            ReviewLocator(
                id="delivery-doc",
                path=Path("docs/contract.md"),
                extractor="markdown-section",
                locator="#body-delivery",
            ),
        ),
    )

    result = evaluate_review_contract(root, contract, base=base, head=head)

    assert result.state == "review-recommended"
    assert result.sources[0].state == "changed"
    assert result.targets[0].state == "unchanged"


def test_dotted_assignment_locator_hashes_only_selected_assignment(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    _write(
        root,
        "src/config.py",
        "class Delivery:\n    PAGE_LENGTH = 8000\n    FILE_LIMIT = 50\n",
    )
    _write(root, "docs/contract.md", "# Contract\n\n## Page length\n\nThe page is 8000 characters.\n")
    base = _commit(root, "baseline")
    _write(
        root,
        "src/config.py",
        "class Delivery:\n    PAGE_LENGTH = 4000\n    FILE_LIMIT = 75\n",
    )
    _write(root, "docs/contract.md", "# Contract\n\n## Page length\n\nThe page is 4000 characters.\n")
    head = _commit(root, "change page length")
    contract = ReviewContract(
        id="page-length",
        mode="observe",
        sources=(
            ReviewLocator(
                id="page-length-source",
                path=Path("src/config.py"),
                extractor="python-symbol",
                locator="Delivery.PAGE_LENGTH",
            ),
        ),
        targets=(
            ReviewLocator(
                id="page-length-doc",
                path=Path("docs/contract.md"),
                extractor="markdown-section",
                locator="#page-length",
            ),
        ),
    )

    result = evaluate_review_contract(root, contract, base=base, head=head)

    assert result.state == "cochanged"
    assert result.sources[0].state == "changed"
    assert result.targets[0].state == "changed"
