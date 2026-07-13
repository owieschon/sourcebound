# clean-docs

clean-docs binds factual documentation to repository sources and fails when the two drift apart.

The current alpha reads a static Python assignment, renders a marked Markdown table, and checks the committed table against the source. It never imports repository code. `derive` previews changes unless you pass `--write`; `check` never writes.

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

Fail when the committed region is stale:

```bash
clean-docs check
```

Use `--format json` for machine-readable results and `--ref <git-ref>` to read sources from an immutable commit.

## Supported binding surface

This table is derived from `src/clean_docs/capabilities.py` by clean-docs itself:

<!-- clean-docs:begin supported-bindings -->
| binding | source | output | check |
| --- | --- | --- | --- |
| region | Static Python assignment | Markdown table | Re-render and compare |
<!-- clean-docs:end supported-bindings -->

## Current limits

- Manifest version 1 alpha accepts `region` bindings only.
- The alpha supports the `python-literal` extractor and `markdown-table` renderer only.
- Source constructor calls must use keyword arguments.
- Destination markers must already exist and cannot nest.
- clean-docs reports malformed configuration as exit `2`, drift as exit `1`, and extraction failures as exit `3`.

The full product contract and version plan live in [`CLEAN_DOCS_SPEC.md`](CLEAN_DOCS_SPEC.md).
