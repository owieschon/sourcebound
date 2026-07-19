from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import clean_docs.review_contracts as review_contracts
from clean_docs.models import ReviewContract, ReviewLocator
from clean_docs.review_contracts import (
    evaluate_review_contract,
    evaluate_review_contracts,
)
from clean_docs.review_limits import MAX_REVIEW_FILE_BYTES
from clean_docs.snapshot import RepositorySnapshot


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


def _markdown_target_contract() -> ReviewContract:
    return ReviewContract(
        id="delivery-guidance",
        mode="observe",
        sources=(
            ReviewLocator(
                id="delivery-mode",
                path=Path("src/delivery.py"),
                extractor="python-symbol",
                locator="DELIVERY_MODE",
            ),
        ),
        targets=(
            ReviewLocator(
                id="delivery-instructions",
                path=Path("docs/guide.mdx"),
                extractor="markdown-section",
                locator="#target",
            ),
        ),
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
        "src/delivery.py",
        "def fetch_page():\n    return {'body_next_offset': 8000}\n",
    )
    _write(
        root,
        "docs/delivery.md",
        "# Delivery\n\n## Fetching pages\n\nContinue from `body_next_offset`.\n",
    )
    base = _commit(root, "baseline")
    _write(root, "src/delivery.py", "def fetch_all():\n    return 'complete'\n")
    head = _commit(root, "remove pagination behavior")
    contract = ReviewContract(
        id="pagination-removal",
        mode="observe",
        sources=(
            ReviewLocator(
                id="fetch-page",
                path=Path("src/delivery.py"),
                extractor="python-symbol",
                locator="fetch_page",
            ),
        ),
        targets=(
            ReviewLocator(
                id="fetching-pages",
                path=Path("docs/delivery.md"),
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
    _write(root, "src/delivery.py", "PAGE_LENGTH = 8000\n")
    _write(
        root,
        "docs/delivery.md",
        "# Delivery\n\n## Fetching pages\n\nPages contain 8000 characters.\n",
    )
    base = _commit(root, "baseline")
    _write(root, "src/delivery.py", "PAGE_LENGTH = 4000\n")
    _write(root, "docs/delivery.md", "# Delivery\n")
    head = _commit(root, "remove page instructions")
    contract = ReviewContract(
        id="missing-head-target",
        mode="observe",
        sources=(
            ReviewLocator(
                id="page-length",
                path=Path("src/delivery.py"),
                extractor="python-symbol",
                locator="PAGE_LENGTH",
            ),
        ),
        targets=(
            ReviewLocator(
                id="fetching-pages",
                path=Path("docs/delivery.md"),
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


def test_fenced_heading_before_real_target_does_not_hide_real_change(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    _write(root, "src/delivery.py", 'DELIVERY_MODE = "single"\n')
    _write(
        root,
        "docs/guide.mdx",
        """
# Delivery

```markdown
## Target
Example content.
```

## Target

Fetch one complete result.

## Next

Continue elsewhere.
""".lstrip(),
    )
    base = _commit(root, "baseline")
    _write(root, "src/delivery.py", 'DELIVERY_MODE = "paged"\n')
    _write(
        root,
        "docs/guide.mdx",
        """
# Delivery

```markdown
## Target
Example content.
```

## Target

Fetch each page until the continuation token is absent.

## Next

Continue elsewhere.
""".lstrip(),
    )
    head = _commit(root, "change delivery guidance")

    result = evaluate_review_contract(
        root,
        _markdown_target_contract(),
        base=base,
        head=head,
    )

    assert result.state == "cochanged"
    assert result.sources[0].state == "changed"
    assert result.targets[0].state == "changed"


def test_change_only_inside_fenced_example_leaves_target_unchanged(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    _write(root, "src/delivery.py", 'DELIVERY_MODE = "single"\n')
    _write(
        root,
        "docs/guide.mdx",
        """
# Delivery

```markdown
## Target
Example content.
```

## Target

Fetch one complete result.

```markdown
## Example
The example uses one result.
```
""".lstrip(),
    )
    base = _commit(root, "baseline")
    _write(
        root,
        "docs/guide.mdx",
        """
# Delivery

```markdown
## Target
Rewritten example content.
```

## Target

Fetch one complete result.

```markdown
## Example
The rewritten example uses several results.
```
""".lstrip(),
    )
    head = _commit(root, "edit fenced example")

    result = evaluate_review_contract(
        root,
        _markdown_target_contract(),
        base=base,
        head=head,
    )

    assert result.state == "unaffected"
    assert result.sources[0].state == "unchanged"
    assert result.targets[0].state == "unchanged"


def test_duplicate_rendered_heading_is_unknown(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _write(root, "src/delivery.py", 'DELIVERY_MODE = "single"\n')
    _write(
        root,
        "docs/guide.mdx",
        """
# Delivery

## Target

First instruction.

## Target

Second instruction.
""".lstrip(),
    )
    head = _commit(root, "ambiguous guide")

    result = evaluate_review_contract(
        root,
        _markdown_target_contract(),
        base=head,
        head=head,
    )

    assert result.state == "unknown"
    assert result.targets[0].state == "unknown"
    assert result.targets[0].base_digest is None
    assert result.targets[0].head_digest is None


def test_html_block_and_mdx_expression_do_not_create_section_headings(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    _write(root, "src/delivery.py", 'DELIVERY_MODE = "single"\n')
    _write(
        root,
        "docs/guide.mdx",
        """
# Delivery

<div>
## Target
HTML example content.
</div>

{`## Target`}

<!--
## Target
HTML comment content.
-->

## Target

Fetch one complete result.
""".lstrip(),
    )
    base = _commit(root, "baseline")
    _write(root, "src/delivery.py", 'DELIVERY_MODE = "paged"\n')
    _write(
        root,
        "docs/guide.mdx",
        """
# Delivery

<div>
## Target
HTML example content.
</div>

{`## Target`}

<!--
## Target
HTML comment content.
-->

## Target

Fetch each page.
""".lstrip(),
    )
    head = _commit(root, "change rendered instructions")

    result = evaluate_review_contract(
        root,
        _markdown_target_contract(),
        base=base,
        head=head,
    )

    assert result.state == "cochanged"
    assert result.targets[0].state == "changed"


def test_markdown_documents_are_parsed_once_per_contract_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    _write(root, "src/delivery.py", 'DELIVERY_MODE = "single"\n')
    _write(
        root,
        "docs/guide.mdx",
        "# Delivery\n\n## Target\n\nFetch one complete result.\n",
    )
    head = _commit(root, "baseline")
    parse_calls = 0
    parse_documents = review_contracts.parse_mdx_documents

    def counted_parse(
        documents: dict[str, str],
    ) -> tuple[
        dict[str, review_contracts.MdxDocument],
        dict[str, str],
    ]:
        nonlocal parse_calls
        parse_calls += 1
        return parse_documents(documents)

    monkeypatch.setattr(
        review_contracts,
        "parse_mdx_documents",
        counted_parse,
    )
    first = _markdown_target_contract()
    second = ReviewContract(
        id="second-delivery-guidance",
        mode=first.mode,
        sources=first.sources,
        targets=first.targets,
    )

    results = evaluate_review_contracts(
        root,
        (first, second),
        base=head,
        head=head,
    )

    assert len(results) == 2
    assert parse_calls == 1


def test_repeated_locators_read_each_ref_path_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    base = _write_pagination_base(root)
    _add_pagination_behavior_test(root)
    head = _commit(root, "add pagination")
    first = _delivery_contract()
    second = ReviewContract(
        id="second-delivery-guidance",
        mode=first.mode,
        sources=first.sources,
        targets=first.targets,
    )
    calls: list[tuple[str, str]] = []
    read_text = RepositorySnapshot.read_text

    def counted_read(
        snapshot: RepositorySnapshot,
        path: Path,
    ) -> str:
        calls.append((snapshot.label, path.as_posix()))
        return read_text(snapshot, path)

    monkeypatch.setattr(RepositorySnapshot, "read_text", counted_read)

    results = evaluate_review_contracts(
        root,
        (first, second),
        base=base,
        head=head,
    )

    assert [result.state for result in results] == [
        "review-recommended",
        "review-recommended",
    ]
    assert len(calls) == 4
    assert len(set(calls)) == len(calls)


def test_oversized_locator_file_is_not_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    _write(root, "tests/test_delivery.py", "x" * (MAX_REVIEW_FILE_BYTES + 1))
    _write(
        root,
        "docs/delivery.md",
        "# Delivery\n\n## Reading large results\n\nFetch once.\n",
    )
    base = _commit(root, "baseline")
    _write(
        root,
        "docs/delivery.md",
        "# Delivery\n\n## Reading large results\n\nFetch each page.\n",
    )
    head = _commit(root, "change instructions")
    read_text = RepositorySnapshot.read_text

    def reject_oversized_read(
        snapshot: RepositorySnapshot,
        path: Path,
    ) -> str:
        if path == Path("tests/test_delivery.py"):
            raise AssertionError("oversized source must not be read")
        return read_text(snapshot, path)

    monkeypatch.setattr(RepositorySnapshot, "read_text", reject_oversized_read)

    result = evaluate_review_contract(
        root,
        _delivery_contract(),
        base=base,
        head=head,
    )

    assert result.state == "unknown"
    assert result.sources[0].state == "unknown"


def test_aggregate_content_budget_resolves_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    base = _write_pagination_base(root)
    _add_pagination_behavior_test(root)
    head = _commit(root, "add pagination")
    monkeypatch.setattr(review_contracts, "MAX_REVIEW_TOTAL_BYTES", 64)

    result = evaluate_review_contract(
        root,
        _delivery_contract(),
        base=base,
        head=head,
    )

    assert result.state == "unknown"


def test_yaml_alias_expansion_resolves_unknown(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    levels = ["leaf: &leaf [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]"]
    previous = "leaf"
    for index in range(6):
        current = f"level{index}"
        levels.append(
            f"{current}: &{current} [{', '.join([f'*{previous}'] * 10)}]"
        )
        previous = current
    levels.append(f"payload: *{previous}")
    _write(root, "config/delivery.yaml", "\n".join(levels) + "\n")
    _write(
        root,
        "docs/delivery.md",
        "# Delivery\n\n## Reading large results\n\nFetch once.\n",
    )
    base = _commit(root, "baseline")
    _write(
        root,
        "docs/delivery.md",
        "# Delivery\n\n## Reading large results\n\nFetch each page.\n",
    )
    head = _commit(root, "change instructions")
    contract = ReviewContract(
        id="structured-guidance",
        mode="observe",
        sources=(
            ReviewLocator(
                id="payload",
                path=Path("config/delivery.yaml"),
                extractor="structured-data",
                locator="/payload",
            ),
        ),
        targets=_delivery_contract().targets,
    )

    result = evaluate_review_contract(root, contract, base=base, head=head)

    assert result.state == "unknown"
    assert result.sources[0].state == "unknown"
