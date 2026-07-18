# Context bundle: contributor

- Source ref: `WORKTREE`
- Corpus sha256: `84c6873c3ebc61a921d781d7f2ca15c29cc0a20895475ebd2e765fde01d12475`
- Content: exact canonical document bytes

## Canonical document: README.md

- Source: [README.md](../../README.md)
- Content sha256: `1618f85c133cad92337b7f7b99ba7cfdfc17768c6ee8612a90a43af8116ff8d7`

<!-- clean-docs:canonical README.md begin -->
# clean-docs

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
clean-docs is a source-bound documentation engine and CLI for maintainers who need code and prose to change together. It turns selected source facts into checked documentation, so stale claims fail in local workflows and CI.
<!-- clean-docs:end purpose -->

[![CI](https://github.com/owieschon/clean-docs/actions/workflows/ci.yml/badge.svg)](https://github.com/owieschon/clean-docs/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/owieschon/clean-docs?display_name=tag&sort=semver)](https://github.com/owieschon/clean-docs/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-25225f.svg)](LICENSE)

**[Install clean-docs and catch your first stale claim](docs/learn/tutorial-catch-a-lying-doc.md)**.

The final `clean-docs verify` command prints a [`clean-docs.outcome.v1` receipt](docs/SUPPORT.md#record-local-outcomes) with `"ok": true`.

| If you need to... | Start with | You will leave with... |
| --- | --- | --- |
| Try the repair loop | [Runnable tutorial](docs/learn/tutorial-catch-a-lying-doc.md) | A failed drift check and a repaired page |
| Choose a command | [CLI reference](docs/CLI.md) | The command and its write boundary |
| Configure a binding | [Manifest reference](docs/REFERENCE.md) | A source-bound fact with the right depth |
| Understand trust boundaries | [Security model](docs/SECURITY_MODEL.md) | The process and host guarantees |

## Why clean-docs exists

<!-- clean-docs:begin product-overview -->
A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, and reviewers have no mechanical way to identify the false claim. clean-docs gives each protected fact a source, then checks that relationship again in CI.

Source owns the facts. A packaged writing standard owns their form. Static adapters read common code and schema formats, while declared commands run under explicit process controls. The verified result can repair bound regions, reject drift, and publish context such as `llms.txt` with local receipts.
<!-- clean-docs:end product-overview -->

Human review can improve a sentence. It cannot make the sentence fail when its defining source changes. The [deterministic seam](docs/learn/deep-dive-the-deterministic-seam.md) explains how clean-docs separates source evidence, optional phrasing, and gate authority.

## Install and prove the loop

```bash
git clone https://github.com/owieschon/clean-docs.git && cd clean-docs
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
clean-docs audit
```

Protect a repository after the audit passes:

```bash
clean-docs init --no-model
git diff
clean-docs check
clean-docs verify
```

After a bound source changes, run `check`, then `drive`, then `project`, then `verify`. The [tutorial](docs/learn/tutorial-catch-a-lying-doc.md) shows the failure before the repair. The [support guide](docs/SUPPORT.md) covers release wheels and mature-repository adoption.

## How the pieces fit

![Architecture diagram showing repository evidence flowing through source bindings and the writing standard into repair, CI, and context outputs](docs/assets/clean-docs-system-map.svg)

Repository sources become typed evidence. Bindings assign that evidence to document regions, claims, and symbols. The engine applies the packaged standard, then repairs documentation, rejects drift, or publishes verified context. The [manifest page](docs/REFERENCE.md) lists each binding and projected output.

## Current boundaries

- Catalog coverage detects source additions, removals, and replacements. Protect a specific prose claim with a binding.
- `drive` repairs bound regions. Run `project` afterward when a projection includes the repaired document.
- Declared processes use time, I/O, and environment controls. The host owns network isolation; see the [security model](docs/SECURITY_MODEL.md).
- `audit`, `check`, `verify`, and `release` do not change documentation.
- Exit `1` means drift, exit `2` means invalid configuration, and exit `3` means extraction failed.

Use the [learning path](docs/learn/index.md) for the product map and evidence-backed examples. The [product contract](CLEAN_DOCS_SPEC.md) holds the complete behavior and version plan.
<!-- clean-docs:canonical README.md end -->

## Canonical document: docs/EVALUATION.md

- Source: [docs/EVALUATION.md](../../docs/EVALUATION.md)
- Content sha256: `863e849cb7063a0054ffd4e5e0c7e7de7b2fa7a5605bbcc17749bcd7164f8947`

<!-- clean-docs:canonical docs/EVALUATION.md begin -->
# Evaluate documentation tasks

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this guide when repository docs must prove that a person or agent can finish a declared task from published pages alone. It shows you how to build replayable evaluations and record a content-addressed result tied to the declared task.
<!-- clean-docs:end purpose -->

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
