# clean-docs

clean-docs is a self-driving documentation system that applies one packaged standard and keeps repository documentation current for humans and agents.

Write the standard once; clean-docs does the repository work. The finished product audits each repository, derives its factual spine from source, phrases it to the packaged standard, tests the result, and maintains it on every change. Models may phrase grounded facts; deterministic code owns the facts and gate results.

The current alpha audits documentation without configuration, reads a static Python assignment or JSON Pointer, renders a marked Markdown table, and checks the committed table against the source. It never imports repository code. `derive` previews changes unless you pass `--write`; `audit` and `check` never write.

## Install and audit

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
clean-docs audit
clean-docs doctor
pytest
```

`audit` inventories tracked Markdown without requiring `.clean-docs.yml`.

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

## Preview, repair, and check

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

## Verify public and self-hosted behavior

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
| claim | Allowlisted JSON command | Assertion at a document anchor | Compare typed expected and observed values |
| region | Static Python, structured data, text, or paths | Table, list, scalar, or fenced text | Re-render and compare |
| symbol | Static path or Python symbol | Reference at a document anchor | Resolve the cited locator |
<!-- clean-docs:end supported-bindings -->

## Current limits

- Manifest version 1 accepts `region`, `claim`, and `symbol` bindings.
- Regions support static Python, JSON, YAML, TOML, text files, and path globs with typed renderers.
- Claims consume JSON from an allowlisted command; symbols resolve static paths or Python names.
- Command allowlisting and timeouts are enforced; network isolation belongs to the execution environment.
- Source constructor calls must use keyword arguments.
- Destination markers must already exist and cannot nest.
- clean-docs reports malformed configuration as exit `2`, drift as exit `1`, and extraction failures as exit `3`.

The full product contract and version plan live in [`CLEAN_DOCS_SPEC.md`](CLEAN_DOCS_SPEC.md).
