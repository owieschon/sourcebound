# Context bundle: contributor

- Source ref: `WORKTREE`
- Corpus sha256: `5102f4791393bc57bab507ca04a5fe9ffe1a834b1783a91fb31d6018757eb6b8`
- Content: exact canonical document bytes

## Canonical document: README.md

- Source: [README.md](../../README.md)
- Content sha256: `d352943d308f9178c9e543b527afe3bc867aecd78b4594ea9d38ef3a78b13120`

<!-- clean-docs:canonical README.md begin -->
# clean-docs

clean-docs is a self-driving documentation system that applies one packaged standard and keeps repository documentation current for humans and agents.

Write the standard once; clean-docs does the repository work. The finished product audits each repository, derives its factual spine from source, phrases it to the packaged standard, tests the result, and maintains it on every change. Models may phrase grounded facts; deterministic code owns the facts and gate results.

<!-- clean-docs:begin product-overview -->
Version 0.4a1 projects one verified documentation graph into llms.txt and named context bundles, with source refs, content digests, link verification, and freshness checks. It scores documented human commands and agent responses with replayable task fixtures and generates one accessible static demonstration from recorded drift evidence. It compares normalized public surface across git refs and reports changed binding drift, coverage gaps, and SARIF annotations. It statically inventories package, CLI, API, schema, test, and documentation surfaces and bootstraps a source-bound baseline. It audits documentation without configuration and verifies region, claim, and symbol bindings from static Python, structured data, text files, path globs, and allowlisted JSON commands. It emits manifest-derived stepwise skill packages and llms.txt indexes, and it never imports repository code. `derive` previews changes unless you pass `--write`; `audit` and `check` never write.
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
| project | Regenerate configured documentation projections | yes |
| eval | Score human tasks and replayable agent round trips | with --history or live recording |
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
- Command allowlisting and timeouts are enforced. In an allowlisted `argv`, `{python}` selects the interpreter running clean-docs. Network isolation belongs to the execution environment.
- Coverage ignores must name a detected inventory ID and carry a specific reason; `explain` reports the evidence and repair for gaps.
- Changed checks have a published five-second median budget on each pinned dogfood repository.
- Source constructor calls must use keyword arguments.
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
