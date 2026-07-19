# Context bundle: contributor

- Source ref: `WORKTREE`
- Corpus sha256: `4c77d91cef07309de6c9dd4f79fe6dafd8f822e58ebb1212bd16bfe89a578ee9`
- Content: exact canonical document bytes

## Canonical document: README.md

- Source: [README.md](../../README.md)
- Content sha256: `a039bcfd2ddda9fccb0e728890879bcc51ece7ec6fe4eb5bf550751635ce0468`

<!-- clean-docs:canonical README.md begin -->
# clean-docs

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
clean-docs is a source-bound documentation engine and CLI for maintainers who need code and prose to change together. It turns selected source facts into checked documentation, so stale claims fail in local workflows and CI.
<!-- clean-docs:end purpose -->

[![CI](https://github.com/owieschon/clean-docs/actions/workflows/ci.yml/badge.svg)](https://github.com/owieschon/clean-docs/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/owieschon/clean-docs?display_name=tag&sort=semver)](https://github.com/owieschon/clean-docs/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-25225f.svg)](LICENSE)

**[Install the stable release and catch your first stale claim](docs/learn/tutorial-catch-a-lying-doc.md)**.

The final `clean-docs verify` command prints a [`clean-docs.outcome.v2` receipt](docs/SUPPORT.md#record-local-outcomes) with `"ok": true`.

Audit starts from the document's job. On an untouched repository it is an assessment: broken links,
machine-specific residue, and repository-neutral corpus signals remain bounded advisories. Run
`clean-docs audit --preview-policy` to add compatible house-policy candidates without accepting
them as gates. A manifest accepts repository integrity checks as gates; a policy marker accepts
compatible writing rules for one document. Neither makes an incompatible rule applicable or
authorizes clean-docs to flatten repository-native forms.

| If you need to... | Start with | You will leave with... |
| --- | --- | --- |
| Try the repair loop | [Runnable tutorial](docs/learn/tutorial-catch-a-lying-doc.md) | A failed drift check and a repaired page |
| Choose a command | [CLI reference](docs/CLI.md) | The command and its write boundary |
| Configure a binding | [Manifest reference](docs/REFERENCE.md) | A source-bound fact with the right depth |
| Investigate an unbound count or column claim | [Source claim checks](docs/REFERENCE.md#source-claim-checks) | A ranked candidate or accepted deterministic relationship |
| Understand trust boundaries | [Security model](docs/SECURITY_MODEL.md) | The process and host guarantees |

## Why clean-docs exists

<!-- clean-docs:begin product-overview -->
A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, and reviewers have no mechanical way to identify the false claim. clean-docs gives each protected fact a source, then checks that relationship again in CI.

Declared sources own the protected facts. A packaged policy enforces the deterministic form floor; authored judgment still owns motivation, pedagogy, and voice. Static adapters read common code and schema formats, while declared commands run under explicit process controls. The engine can repair bound regions, rank static count and column candidates, enforce accepted source-claim relationships, and publish context such as `llms.txt` with local receipts.
<!-- clean-docs:end product-overview -->

Human review can improve a sentence. It cannot make the sentence fail when its defining source changes. The [deterministic seam](docs/learn/deep-dive-the-deterministic-seam.md) explains how clean-docs separates source evidence, optional phrasing, and gate authority.

## Install in the repository you want to protect

From that repository, download the latest stable wheel, install it in an isolated environment, and
run the manifest-free audit:

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

An established, unregistered README stays byte-for-byte authored. Init writes its detected catalog
to `.clean-docs/repository-surface.md`; a new README or one that adopted the register may own that
region directly.

After a bound source changes, run `check`, then `drive`, then `project`, then `verify`. The [tutorial](docs/learn/tutorial-catch-a-lying-doc.md) shows the failure before the repair. The [install guide](docs/INSTALL.md) owns release wheels; the [support guide](docs/SUPPORT.md) covers mature-repository adoption.

## How the pieces fit

![Architecture diagram showing repository evidence flowing through source bindings and the writing standard into repair, CI, and context outputs](docs/assets/clean-docs-system-map.svg)

Repository sources become typed evidence. Bindings assign that evidence to generated regions, command pins, and symbols. Accepted source-claim checks compare bounded prose values with static source locators. The engine checks the implemented policy floor, then repairs declared regions, rejects drift, or publishes verified context. The [manifest page](docs/REFERENCE.md) lists each mechanism and projected output.

## Current boundaries

- Catalog coverage detects source additions, removals, and replacements; it does not validate prose.
- Source-claim discovery ranks static count and identifier-set candidates. A candidate remains advisory until the repository accepts its exact document and source relationship.
- `drive` repairs bound regions. Run `project` afterward when a projection includes the repaired document.
- Declared processes use time, I/O, and environment controls. The host owns network isolation; see the [security model](docs/SECURITY_MODEL.md).
- Authored purpose and the manifest decide what matters. clean-docs does not infer product goals or certify judgment prose.
- `audit`, `check`, `verify`, and `release` do not change documentation.
- Exit `1` means drift, exit `2` means invalid configuration, and exit `3` means extraction failed.

Use the [learning path](docs/learn/index.md) for the product map and evidence-backed examples. The [current product contract](CLEAN_DOCS_SPEC.md) states the exact assurance boundary.
<!-- clean-docs:canonical README.md end -->

## Canonical document: docs/EVALUATION.md

- Source: [docs/EVALUATION.md](../../docs/EVALUATION.md)
- Content sha256: `bc1e0d3543ec88db415151b51ef89483c21ee9e034b0e26a37fb9edfb4c3174d`

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
