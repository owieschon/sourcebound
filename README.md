# clean-docs

clean-docs is a self-driving documentation system that applies one packaged standard and keeps repository documentation current for humans and agents.

Write the standard once; clean-docs does the repository work. The finished product audits each repository, derives its factual spine from source, phrases it to the packaged standard, tests the result, and maintains it on every change. Models may phrase grounded facts; deterministic code owns the facts and gate results.

The current alpha implements the first deterministic slice. It reads a static Python assignment or JSON Pointer, renders a marked Markdown table, and checks the committed table against the source. It never imports repository code. `derive` previews changes unless you pass `--write`; `check` never writes.

## Install the alpha

Install the package in an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run its tests:

```bash
pytest
```

## Declare a binding

Create `.clean-docs.yml` at the repository root:

```yaml
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: python-literal
    source:
      path: src/actions.py
      symbol: ACTIONS
    renderer: markdown-table
    columns: [name, tier]
```

The source assignment may be a list of dictionaries or a dictionary whose values are records. Constructor calls are read as keyword records. clean-docs parses the syntax tree and does not execute the module.

## Mark the destination

Mark the generated region in the destination document:

```markdown
<!-- clean-docs:begin actions -->
<!-- clean-docs:end actions -->
```

Preview the derived diff:

```bash
clean-docs derive
```

Write the region atomically:

```bash
clean-docs derive --write
```

Repair every bound region and run the implemented checks from the bundled default standard:

```bash
clean-docs drive
```

Fail when the committed region is stale:

```bash
clean-docs check
```

Use `--format json` for machine-readable results and `--ref <git-ref>` to read sources from an immutable commit.

Repositories do not configure a standard path. clean-docs bundles a versioned policy pack compiled from [`STANDARD.md`](STANDARD.md). CI fails if the authored standard changes without rebuilding that pack.

Run the pinned public-repository dogfood proof with:

```bash
PYTHONPATH=src python3 scripts/dogfood_public_repos.py
```

The proof clones two fixed commits, derives documentation from Python and JSON sources,
detects deliberate source drift, repairs the generated regions, and verifies each final
state. It never executes code from either target repository.

Self-hosting uses `python3 scripts/trusted_self_check.py`. Candidate code checks its own
tree, then the verifier pinned in `.clean-docs-trust.json` independently checks the same
files. Updating that pin is a release operation, not part of documentation generation.

## Supported binding surface

This table is derived from `src/clean_docs/capabilities.py` by clean-docs itself:

<!-- clean-docs:begin supported-bindings -->
| binding | source | output | check |
| --- | --- | --- | --- |
| region | Static Python assignment or JSON Pointer | Markdown table | Re-render and compare |
<!-- clean-docs:end supported-bindings -->

## Current limits

- Manifest version 1 alpha accepts `region` bindings only.
- The alpha supports `python-literal` and `json` extractors with the `markdown-table` renderer.
- Source constructor calls must use keyword arguments.
- Destination markers must already exist and cannot nest.
- clean-docs reports malformed configuration as exit `2`, drift as exit `1`, and extraction failures as exit `3`.

The full product contract and version plan live in [`CLEAN_DOCS_SPEC.md`](CLEAN_DOCS_SPEC.md).
