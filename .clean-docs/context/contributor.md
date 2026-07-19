# Context bundle: contributor

- Source ref: `WORKTREE`
- Corpus sha256: `e52076a9889bab17e140dd918295375d7093fed936c485144bc6e9a153efc619`
- Content: exact canonical document bytes

## Canonical document: README.md

- Source: [README.md](../../README.md)
- Content sha256: `bfb909516e8e4b06c4e25c18efd3591850201764add8f9362f1afeb8ef1adff7`

<!-- clean-docs:canonical README.md begin -->
# clean-docs

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
clean-docs is a source-bound documentation engine and CLI for maintainers who need code and prose to change together. It turns selected source facts into checked documentation, so stale claims fail in local workflows and CI.
<!-- clean-docs:end purpose -->

[![CI](https://github.com/owieschon/clean-docs/actions/workflows/ci.yml/badge.svg)](https://github.com/owieschon/clean-docs/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/owieschon/clean-docs?display_name=tag&sort=semver)](https://github.com/owieschon/clean-docs/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-25225f.svg)](LICENSE)

**[Install the stable release and catch your first stale claim](docs/learn/tutorial-catch-a-lying-doc.md)**.

The final `clean-docs verify` command prints a [`clean-docs.outcome.v2` receipt](docs/SUPPORT.md#record-local-outcomes) with `"ok": true`.

Before adoption, `audit` reports bounded repository-neutral advisories. A manifest turns integrity checks into gates; policy markers opt compatible writing rules into specific documents. Neither authorizes clean-docs to flatten repository-native forms.

| If you need to... | Start with | You will leave with... |
| --- | --- | --- |
| Try the repair loop | [Runnable tutorial](docs/learn/tutorial-catch-a-lying-doc.md) | A failed drift check and a repaired page |
| Choose a command | [CLI reference](docs/CLI.md) | The command and its write boundary |
| Configure a binding | [Manifest reference](docs/REFERENCE.md) | A source-bound fact with the right depth |
| Investigate an unbound count or column claim | [Source claim checks](docs/REFERENCE.md#source-claim-checks) | A ranked candidate or accepted deterministic relationship |
| Review a pull request | [Coverage-stating verdict](docs/CLI.md#pull-request-verdicts) | One pinned state with gaps, skips, and non-claims visible |
| Measure recurring operational problems | [Opt-in feedback loop](docs/FEEDBACK.md) | Bounded envelopes and a receipted improvement case |
| Understand trust boundaries | [Security model](docs/SECURITY_MODEL.md) | The process and host guarantees |

## Why clean-docs exists

<!-- clean-docs:begin product-overview -->
A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, and reviewers have no mechanical way to identify the false claim. clean-docs gives each protected fact a source, then checks that relationship again in CI.

Declared sources own the protected facts. A packaged policy enforces the deterministic form floor; authored judgment still owns motivation, pedagogy, and voice. Static adapters read common code and schema formats, while declared commands run under explicit process controls. The engine can repair bound regions, rank static count and column candidates, enforce accepted source-claim relationships, and publish context such as `llms.txt` with local receipts.
<!-- clean-docs:end product-overview -->

Human review can improve a sentence. It cannot make the sentence fail when its defining source changes. The [deterministic seam](docs/learn/deep-dive-the-deterministic-seam.md) explains how clean-docs separates source evidence, optional phrasing, and gate authority.

## Install in the repository you want to protect

From that repository, download the latest stable wheel, install it in an isolated environment, and run the manifest-free audit:

```bash
release_dir="$(mktemp -d)"
gh release download --repo owieschon/clean-docs \
  --pattern 'clean_docs-*-py3-none-any.whl' --dir "$release_dir"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "$release_dir"/clean_docs-*.whl
clean-docs audit
```

After reviewing the assessment, inspect the files that `init` proposes before accepting its gate:

```bash
clean-docs init --no-model
git diff -- .clean-docs.yml .clean-docs/repository-surface.md README.md llms.txt
clean-docs check
clean-docs verify
```

An established, unregistered README stays byte-for-byte authored. Init writes its detected catalog to `.clean-docs/repository-surface.md`; a new README or one that adopted the register may own that region directly.

After a bound source changes, run `check`, then use `drive` for a declared repair. Run `project` when a declared projection depends on the repaired document, then run `verify`. The [tutorial](docs/learn/tutorial-catch-a-lying-doc.md) shows the failure before the repair; the [support guide](docs/SUPPORT.md) covers mature-repository adoption.

## How the pieces fit

Three inputs stay separate before the deterministic core:

- **Authored intent** records why a surface matters. clean-docs preserves that purpose; it does not infer its priority or turn judgment into gate authority.
- **Repository contract** declares sources, binding mechanisms, process limits, and projections. Policy markers scope compatible form checks; they do not certify voice.
- **Change state** combines base and head refs with that contract to produce an immutable impact plan. Static adapters and bounded commands produce typed evidence. Each mechanism proves only its declared relationship; accepted source-claim checks are separate, and unbound prose stays visibly unknown.

The core exposes four job-specific exits:

1. **Repair bounded prose.** `drive` writes only planned regions. `project` runs separately when a declared output depends on changed documentation.
2. **Reject stale changes.** `check` and `verdict` are read-only. The verdict names changed, bound, unbound, and skipped surfaces.
3. **Publish agent context.** `project` writes declared outputs such as `llms.txt` and context bundles.
4. **Record local state.** `verify` emits its own outcome receipt.

`verdict` and `verify` produce independent receipts. Neither certifies unbound or judgment prose. The [product contract](CLEAN_DOCS_SPEC.md) defines each authority boundary.

## Current boundaries

- Catalog coverage detects source additions, removals, and replacements; it does not validate prose.
- Source-claim discovery ranks static count and identifier-set candidates. A candidate remains advisory until the repository accepts its exact document and source relationship.
- Declared processes use time, I/O, and environment controls. The host owns network isolation; see the [security model](docs/SECURITY_MODEL.md).
- The manifest decides what clean-docs evaluates. Authored purpose records goals; clean-docs does not infer or certify them.
- Feedback is off by default. Enabled runs queue bounded local envelopes; only an explicit `feedback flush` contacts the configured sink, and delivery cannot change a gate result.

Use the [learning path](docs/learn/index.md) for examples. The [product contract](CLEAN_DOCS_SPEC.md) owns parser, write-boundary, and exit-code details.
<!-- clean-docs:canonical README.md end -->

## Canonical document: docs/EVALUATION.md

- Source: [docs/EVALUATION.md](../../docs/EVALUATION.md)
- Content sha256: `d4364212c28b5f8b9bc715e54a3b55152ad5ec09ef96d69d0802ea9b048c518c`

<!-- clean-docs:canonical docs/EVALUATION.md begin -->
# Evaluate documentation tasks

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
A documentation task earns evidence only when the intended person or agent can finish it from the
declared context. This guide lets maintainers build replayable evaluations and bind each result to
the exact task, corpus, response, and scorer.
<!-- clean-docs:end purpose -->

**[Run the recorded tasks](#run-recorded-tasks)**.

A passing run prints the attempted and passed counts for each audience. Those counts are the proof
for that run; a history file binds them to the corpus, prompt, response, model, and scorer digests.

A passing evaluation is a receipt for one task, not a halo around the whole corpus. It records who
attempted what, which context they saw, how the result was scored, and whether it passed.

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
| mutation-red | Provider proposal, frozen fact, and disposable static repository | The sensitivity state matches without authorizing the relationship |
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
      citation: README.md#current-boundaries
      forbidden: [unsupported inference]
```

## Run a live provider

Live execution is explicit. Declare a bounded deadline with the command adapter; fixtures that
omit it retain the 120-second compatibility default:

```yaml
model:
  adapter: command
  name: local-provider
  argv: [provider-cli, --json]
  timeout_seconds: 300
```

Then retain the live response and its run record:

```bash
clean-docs eval --mode live --record-dir .clean-docs/evaluation/live
```

The task's command adapter receives a deterministic JSON prompt on standard input. Before invoking
it, clean-docs writes `<task>.run.json` with the repository, worktree, corpus, prompt, scorer, and
provider-configuration digests, plus the prompt byte count and deadline. Completion adds the
response digest. A provider error or deadline preserves the input receipt and records a hashed error
identity without copying provider output or credentials into the record.
If the provider changes repository bytes outside the record directory, the run becomes a conflict
and evaluation stops.

The result is labeled `model-specific-live`. Move an accepted response into a recorded fixture
before relying on it in offline CI.

## Score dependency sensitivity

Use `mutation-red` when a provider proposes one `clean-docs.binding-proposal.v1` object and the
evaluator owns a separate frozen fact. Point the scorer at a disposable Git repository rather than
letting the provider select its own mutation target:

```yaml
scorer:
  type: mutation-red
  repository: fixtures/pinned-repository
  fact: .clean-docs/evaluation/mutation-target.json
  fact_sha256: 0000000000000000000000000000000000000000000000000000000000000000
  expected_state: sensitive
```

Replace the zero digest with the exact SHA-256 of the frozen target file when the fixture is
created. A digest mismatch is a configuration error, not a failed model task.

The scorer calls the same static sensitivity primitive as
`clean-docs binding sensitivity`. Its task passes when the observed state matches
`expected_state`; that pass does not accept the relationship. The task detail records the complete
sensitivity-receipt digest and says that semantic authority remains false. Score semantic precision
and recall against a separately frozen gold relationship set.

## Compile bounded context

Use `context compile` when a provider should receive selected source evidence instead of whole
documents. The request pins the repository commit, byte budget, source path and line range, evidence
authority, relationship, rank, and whether the item is required:

```bash
clean-docs context compile \
  --request .clean-docs/context-request.json \
  --format json
```

The `clean-docs.context-bundle.v1` result lists included and excluded items with reasons. Direct
evidence outranks repository prose. An accepted policy can carry instruction authority; ordinary
documentation remains data even when its text resembles a prompt. If required evidence does not
fit, the bundle is `unknown` and the command exits `2`.

## Limits

- Scorers are deterministic; live provider output is model-specific.
- Replay proves the saved response against the named corpus digest, not current behavior of the named model.
- Provider commands run only in live mode. The execution environment owns their network isolation.
- Command-provider deadlines accept one to 3,600 seconds. The deadline bounds one process attempt;
  it does not predict how long a model needs for a given prompt.
- Provider-run receipts detect repository byte changes; they do not sandbox the provider process.
- Context compilation is lexical and source-addressed. It does not use semantic retrieval or a
  vector index.
- Configuration scoring writes the response only inside a temporary copy of the fixture repository.

## Next step

Run `clean-docs project` before evaluation when a task consumes a generated context bundle, then commit the bundle and evaluation history with the canonical documentation change.
<!-- clean-docs:canonical docs/EVALUATION.md end -->
