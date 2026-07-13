# clean-docs

clean-docs is a self-driving documentation system that applies one packaged standard and keeps repository documentation current for humans and agents.

Write the standard once; clean-docs does the repository work. The finished product audits each repository, derives its factual spine from source, phrases it to the packaged standard, tests the result, and maintains it on every change. Models may phrase grounded facts; deterministic code owns the facts and gate results.

<!-- clean-docs:begin product-overview -->
Version 0.3 alpha compares normalized public surface across git refs and reports changed binding drift, coverage gaps, and SARIF annotations. It statically inventories package, CLI, API, schema, test, and documentation surfaces and bootstraps a source-bound baseline. It audits documentation without configuration and verifies region, claim, and symbol bindings from static Python, structured data, text files, path globs, and allowlisted JSON commands. It emits manifest-derived stepwise skill packages and llms.txt indexes, and it never imports repository code. `derive` previews changes unless you pass `--write`; `audit` and `check` never write.
<!-- clean-docs:end product-overview -->

## Install and audit

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
clean-docs audit
```

`audit` inventories tracked Markdown without `.clean-docs.yml`, enforces corpus rules, and scans tracked product files for repository residue.

## CLI reference

This table is derived from the command registry used by the parser:

<!-- clean-docs:begin cli-reference -->
| command | job | writes |
| --- | --- | --- |
| audit | Inventory and check repository documentation | no |
| inventory | List detected repository surfaces and coverage | no |
| init | Write a source-bound documentation baseline | yes |
| explain | Explain a finding or coverage state | no |
| doctor | Check repository and integration readiness | no |
| derive | Preview generated region changes | with --write |
| drive | Repair bound regions and enforce policy | yes |
| check | Fail on binding drift or uncovered changed surface | no |
| emit | Project the manifest into another format | yes |
| emit stepwise-skill | Write a manifest-derived stepwise skill package | yes |
| emit llms-txt | Write an index of source-bound documents | yes |
| standard | Build or verify the bundled policy pack | varies |
| standard build | Compile the canonical standard | yes |
| standard check | Fail when the policy pack is stale | no |
<!-- clean-docs:end cli-reference -->

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
    source:
      path: src/actions.py
      symbol: ACTIONS
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
- Command allowlisting and timeouts are enforced; network isolation belongs to the execution environment.
- Coverage ignores must name a detected inventory ID and carry a specific reason; `explain` reports the evidence and repair for gaps.
- Changed checks have a published five-second median budget on each pinned dogfood repository.
- Source constructor calls must use keyword arguments.
- Destination markers must already exist and cannot nest.
- clean-docs reports malformed configuration as exit `2`, drift as exit `1`, and extraction failures as exit `3`.

The full product contract and version plan live in [`CLEAN_DOCS_SPEC.md`](CLEAN_DOCS_SPEC.md).
