# Context bundle: contributor

- Source ref: `WORKTREE`
- Corpus sha256: `1e75ee32b2c39516008a31f0c01336290801039d39133c6372bc267b91585c55`
- Content: exact canonical document bytes

## Canonical document: README.md

- Source: [README.md](../../README.md)
- Content sha256: `96532e29b1d73f493fde801d9a372fca92a3e3a93d049dce6d6e059a25b226e3`

<!-- clean-docs:canonical README.md begin -->
# clean-docs

clean-docs is a self-driving documentation system that applies one packaged standard and keeps repository documentation current for humans and agents.

Write the standard once; clean-docs does the repository work. The finished product audits each repository, derives its factual spine from source, phrases it to the packaged standard, tests the result, and maintains it on every change. Models may phrase grounded facts; deterministic code owns the facts and gate results.

<!-- clean-docs:begin product-overview -->
clean-docs protects Python and TypeScript repository documentation through local, pre-commit, and pull-request workflows. It compares normalized evidence across immutable refs and renders provenance-backed release facts. Optional narrative drafts cannot change, omit, or uncite those facts. Versioned plugins add extractors, discoverers, renderers, and policy checks in disposable snapshots; manifest migration includes a byte-exact rollback. It projects one verified documentation graph into llms.txt, named context bundles, and an accessible static demonstration. It scores human commands and recorded agent responses, reports changed binding drift and coverage gaps, and bootstraps source-bound baselines. Mature repositories can commit an exact existing-debt baseline that fails on new and resolved findings until explicitly refreshed. Static adapters cover Python, TypeScript, OpenAPI, JSON Schema, package metadata, and MCP tools without importing repository code. Declared processes run in disposable copies with bounded I/O and minimal environments. Local outcome, performance, and diagnostic receipts make checks inspectable without telemetry. `derive` previews changes unless you pass `--write`; `audit`, `check`, `verify`, and `release` never change documentation.
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

`init` adds a compact source-surface summary, `.clean-docs.yml`, and a checked `llms.txt` projection. Run `clean-docs inventory` for the full detected catalog. The summary carries a hidden catalog digest, so `check` catches a source replacement even when its surface count stays the same. Commit the generated files with the source they describe. Use `drive` to repair recognized binding drift and `project` to refresh projections.

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
<!-- clean-docs:canonical README.md end -->

## Canonical document: docs/EVALUATION.md

- Source: [docs/EVALUATION.md](../../docs/EVALUATION.md)
- Content sha256: `4f7d56256d3d7d3fe72cad2cfb42517c610ee52ef10d0321a28f363d41916eba`

<!-- clean-docs:canonical docs/EVALUATION.md begin -->
# Evaluate documentation tasks

This guide shows how to score observable human tasks and replayable agent responses.

## Intended reader

Use this guide when repository documentation must prove that a person or agent can complete a specific task from declared pages alone.

## Value

`clean-docs eval` reports human task success, agent task success, and hygiene findings separately. A passing task proves its configured observable result. It does not turn one model response into a general quality score.

## Prerequisites

- A valid `.clean-docs.yml`.
- Context files that contain every fact required by the task.
- Recorded response files for agent replay tasks.
- Manifest-allowlisted commands for human command tasks.

## Run recorded tasks

Store a version 1 fixture at `.clean-docs/eval.yml`, then run:

```bash
clean-docs eval --history .clean-docs/evaluation-history.json
```

Replay is the default. It reads recorded responses without invoking a provider. The history is content-addressed and records the corpus, prompt, response, model, scorer, and result for each task.

## Fixture contract

Every task names an audience, prompt, context paths, and scorer. Agent tasks also name either a recorded response adapter or an explicit live command adapter.

<!-- clean-docs:begin evaluation-scorers -->
| scorer | input | passes when |
| --- | --- | --- |
| command | Allowlisted command and documented excerpt | Exit code and required output match |
| configuration | Recorded manifest and fixture repository | Schema validation and check pass |
| structured-output | Recorded JSON and expected value | Parsed values match exactly |
| cited-limit | Recorded answer, canonical citation, and forbidden inferences | The answer cites the declared limit without inferring support |
<!-- clean-docs:end evaluation-scorers -->

A human command expectation must include `documented_as`. clean-docs first finds that exact excerpt in the supplied context, then runs the named allowlisted command and compares its exit code and required output.

This recorded limitation task contains no provider command:

```yaml
version: 1
tasks:
  - id: limitation-retrieval
    audience: agent
    prompt: Does the documented limit permit this behavior?
    context: [.clean-docs/context/contributor.md]
    model:
      adapter: recorded
      name: recorded-fixture
      response: .clean-docs/evaluation/responses/limitation.txt
    scorer:
      type: cited-limit
      answer: The canonical limitation text
      citation: README.md#current-limits
      forbidden: [unsupported inference]
```

## Run a live provider

Live execution is explicit and must retain its response:

```bash
clean-docs eval --mode live --record-dir .clean-docs/evaluation/live
```

The task's command adapter receives a deterministic JSON prompt on standard input. Its result is labeled `model-specific-live`. Move an accepted response into a recorded fixture before relying on it in offline CI.

## Limits

- Scorers are deterministic; live provider output is model-specific.
- Replay proves the saved response against the named corpus digest, not current behavior of the named model.
- Provider commands run only in live mode. The execution environment owns their network isolation.
- Configuration scoring writes the response only inside a temporary copy of the fixture repository.

## Next step

Run `clean-docs project` before evaluation when a task consumes a generated context bundle, then commit the bundle and evaluation history with the canonical documentation change.
<!-- clean-docs:canonical docs/EVALUATION.md end -->
