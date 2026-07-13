# clean-docs

clean-docs is a self-driving documentation system that applies one packaged standard and keeps repository documentation current for humans and agents.

Write the standard once; clean-docs does the repository work. The finished product audits each repository, derives its factual spine from source, phrases it to the packaged standard, tests the result, and maintains it on every change. Models may phrase grounded facts; deterministic code owns the facts and gate results.

<!-- clean-docs:begin product-overview -->
Version 1.0rc3 protects Python and TypeScript repository documentation through local, pre-commit, and pull-request workflows. It compares normalized evidence across immutable refs and renders provenance-backed release facts. Optional narrative drafts cannot change, omit, or uncite those facts. Versioned plugins add extractors, discoverers, renderers, and policy checks in disposable snapshots; manifest migration includes a byte-exact rollback. It projects one verified documentation graph into llms.txt, named context bundles, and an accessible static demonstration. It scores human commands and recorded agent responses, reports changed binding drift and coverage gaps, and bootstraps source-bound baselines. Mature repositories can commit an exact existing-debt baseline that fails on new and resolved findings until explicitly refreshed. Static adapters cover Python, TypeScript, OpenAPI, JSON Schema, package metadata, and MCP tools without importing repository code. Declared processes run in disposable copies with bounded I/O and minimal environments. Local outcome, performance, and diagnostic receipts make checks inspectable without telemetry. `derive` previews changes unless you pass `--write`; `audit`, `check`, `verify`, and `release` never change documentation.
<!-- clean-docs:end product-overview -->
## Install and audit

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
clean-docs audit
```

`audit` inventories tracked Markdown without `.clean-docs.yml`, enforces corpus rules, and scans tracked product files for repository residue.

## Protect a repository

Run the deterministic bootstrap once, inspect its patch, and verify the protected baseline:

```bash
clean-docs init --no-model
git diff
clean-docs check
clean-docs verify
```

`init` adds source-bound facts, `.clean-docs.yml`, and a checked `llms.txt` projection. Commit those files with the source they describe. A later source change makes `check` fail until `drive` repairs recognized bindings and `project` refreshes projections.

If existing hygiene findings block adoption, follow the [mature-repository baseline procedure](docs/SUPPORT.md#adopt-an-existing-documentation-corpus). The explicit baseline protects existing debt by exact fingerprint and still fails on new or resolved findings.

## CLI reference

Use the [CLI reference](docs/CLI.md) to look up each command and whether it writes. The [support guide](docs/SUPPORT.md) defines supported runtimes, upgrades, diagnostics, and local outcome receipts.

## Manifest reference

This table is derived from the binding types accepted by the manifest validator:

<!-- clean-docs:begin manifest-reference -->
| binding | required | verifies |
| --- | --- | --- |
| region | id, type, doc, region, extractor, source, renderer | Generated content matches source evidence |
| claim | id, type, doc, anchor, command, assertion | Observed command value matches the assertion |
| symbol | id, type, doc, anchor, source | A source path or Python symbol still exists |
<!-- clean-docs:end manifest-reference -->

Create `.clean-docs.yml` at the repository root and declare the source for each protected fact:

```yaml
version: 1
bindings:
  - id: actions
    type: region
    doc: README.md
    region: actions
    extractor: python-literal
    source: {path: src/actions.py, symbol: ACTIONS}
    renderer: markdown-table
    columns: [name, tier]
```

Mark the generated destination in the document:

```markdown
<!-- clean-docs:begin actions -->
<!-- clean-docs:end actions -->
```

The source assignment may be a list of dictionaries or a dictionary whose values are records. Constructor calls are read as keyword records. clean-docs parses the syntax tree and does not execute the module.

Repositories do not configure a standard path. clean-docs bundles a versioned policy pack compiled from [`STANDARD.md`](STANDARD.md). CI fails if the authored standard changes without rebuilding that pack.

## Verify public and self-hosted behavior

Run the pinned public-repository dogfood proof with:

```bash
PYTHONPATH=src python3 scripts/dogfood_public_repos.py
PYTHONPATH=src python3 scripts/dogfood_bootstrap_repos.py
```

The binding proof checks source drift and recovery at two fixed commits; the bootstrap proof initializes pinned Python and TypeScript repositories, verifies each baseline, and requires empty reruns without executing target code.

Self-hosting uses `python3 scripts/trusted_self_check.py`; the verifier pinned in `.clean-docs-trust.json` independently checks candidate code, and updating that pin is a release operation.

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

- Claims consume JSON from an allowlisted command; symbols resolve static paths or Python names.
- Declared commands and plugins run in disposable repository copies with minimal environments, active I/O limits, and timeouts. In an allowlisted `argv`, `{python}` selects the interpreter running clean-docs. Network isolation belongs to the execution environment; the [security model](docs/SECURITY_MODEL.md) defines the remaining OS boundary.
- Coverage ignores must name a detected inventory ID and carry a specific reason; `explain` reports the evidence and repair for gaps.
- Changed checks have published P95 time and peak-memory budgets for small, medium, and monorepo fixtures.
- Destination markers must already exist and cannot nest.
- Evaluation claim boundaries are defined in the [evaluation guide](docs/EVALUATION.md).
- clean-docs reports malformed configuration as exit `2`, drift as exit `1`, and extraction failures as exit `3`.

See the [recorded drift demonstration](https://owieschon.github.io/clean-docs/) and use the [evaluation guide](docs/EVALUATION.md) for task fixtures. The full product contract and version plan live in [`CLEAN_DOCS_SPEC.md`](CLEAN_DOCS_SPEC.md).
