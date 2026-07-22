# Context bundle: evaluation

- Source ref: `WORKTREE`
- Corpus sha256: `c354b38fc5776613fc48c2795a2565cfe6bb721c1a367a9f6262383968f96d44`
- Content: exact canonical document bytes

## Canonical document: README.md

- Source: [README.md](../../README.md)
- Content sha256: `5f2b8db9861eb0b5e09bc98aa8dfedfba9fde1bc2c63e4a4c08e03191675565a`

<!-- sourcebound:canonical README.md begin -->
# Sourcebound

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Sourcebound is a documentation engine and CLI for maintainers who need code and prose to change together. It binds selected claims to their defining sources, so drifted documentation fails locally and in CI instead of reaching readers.
<!-- sourcebound:end purpose -->

[![CI](https://github.com/owieschon/sourcebound/actions/workflows/ci.yml/badge.svg)](https://github.com/owieschon/sourcebound/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/owieschon/sourcebound?display_name=tag&sort=semver)](https://github.com/owieschon/sourcebound/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-25225f.svg)](LICENSE)

**[Install the stable release and catch your first stale claim](docs/learn/tutorial-catch-a-lying-doc.md)**.

The final `sourcebound verify` command prints a [`sourcebound.outcome.v2` receipt](docs/SUPPORT.md#record-local-outcomes) with `"ok": true`.

Before adoption, `audit` reports bounded repository-neutral advisories. A manifest turns integrity checks into gates; policy markers opt compatible writing rules into specific documents. Neither authorizes Sourcebound to flatten repository-native forms.

| If you need to... | Start with | You will leave with... |
| --- | --- | --- |
| Try the repair loop | [Runnable tutorial](docs/learn/tutorial-catch-a-lying-doc.md) | A failed drift check and a repaired page |
| Adopt Sourcebound in an existing repository | [Support guide](docs/SUPPORT.md) | A narrow, reviewable first gate |
| Configure a binding | [Manifest reference](docs/REFERENCE.md) | A source-bound fact with the right depth |
| Choose a command | [CLI reference](docs/CLI.md) | The command and its write boundary |
| Review a pull request | [Coverage-stating verdict](docs/CLI.md#pull-request-verdicts) | One pinned state with gaps, skips, and non-claims visible |
| Choose the right documentation tool | [Ecosystem fit](docs/ECOSYSTEM.md) | One owner for each kind of defect |
| Understand trust boundaries | [Security model](docs/SECURITY_MODEL.md) | The process and host guarantees |

## Why Sourcebound exists

<!-- sourcebound:begin product-overview -->
A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, and reviewers have no mechanical way to identify the false claim. Sourcebound gives each protected fact a source, then checks that relationship again in CI.

Declared sources own the protected facts. A packaged policy enforces the deterministic form floor; authored judgment still owns motivation, pedagogy, and voice. Static adapters read common code and schema formats, while declared commands run under explicit process controls. The engine can repair bound regions, rank static count and column candidates, enforce accepted source-claim relationships, and project canonical text and visual records into purpose-built human and agent surfaces with local receipts.
<!-- sourcebound:end product-overview -->

Human review can improve a sentence. It cannot make the sentence fail when its defining source changes. The [deterministic seam](docs/learn/deep-dive-the-deterministic-seam.md) explains how Sourcebound separates source evidence, optional phrasing, and gate authority.

## Use Sourcebound when

Use Sourcebound when an authored explanation contains a selected fact with a stable owner in code, configuration, a schema, or a registry. For example, a public action table can derive from `ACTIONS` in `src/actions.py`; a source-only rename makes `check` fail, and `drive` updates only the declared table region. The [tutorial](docs/learn/tutorial-catch-a-lying-doc.md) runs that exact loop.

Use another tool when it owns the job better. Vale can own prose mechanics. Doc Detective can own whether a consequential procedure still works. A generator can own an entire API or schema reference. If those tools already cover the facts you need, Sourcebound may not justify another gate. The [ecosystem guide](docs/ECOSYSTEM.md) names the boundary.

## Install in the repository you want to protect

Install the stable CLI in an isolated environment, then run the manifest-free audit from the
repository you want to protect:

```bash
pipx install sourcebound
sourcebound audit
```

Use `uv tool install sourcebound` instead when `uv` owns your command-line tools. The
[installation guide](docs/INSTALL.md) covers offline wheelhouses, upgrades, and rollback. The
[release verification guide](docs/VERIFY_RELEASE.md) checks published bytes and provenance.

After reviewing the assessment, inspect the files that `init` proposes before accepting its gate:

<!-- sourcebound:allow-inline-document target=".sourcebound/repository-surface.md" reason="Init conditionally creates this reserved output for an established unregistered README" -->

```bash
sourcebound init --no-model
git diff -- .sourcebound.yml .sourcebound/repository-surface.md README.md llms.txt
sourcebound check
sourcebound verify
```

An established, unregistered README stays byte-for-byte authored. Init writes its detected catalog to `.sourcebound/repository-surface.md`; a new README or one that adopted the register may own that region directly. Its plan also reports zero directly protected prose after catalog-only setup and lists bounded advisory source-claim candidates when static ownership evidence supports them. Review a candidate, then add its exact relationship manually or reject it.

After a bound source changes, run `check`, then use `drive` for a declared repair. Run `project` when a declared projection depends on the repaired document, then run `verify`. The [tutorial](docs/learn/tutorial-catch-a-lying-doc.md) shows the failure before the repair; the [support guide](docs/SUPPORT.md) covers mature-repository adoption.

## How the pieces fit

`authored intent + repository contract + change state → typed evidence → bounded check, repair, projection, and receipt`

**Authored intent** states what the maintainers want readers to know. Sourcebound does not infer its priority, completeness, or editorial quality. **Repository contract** selects the facts and relationships that earn deterministic treatment. Each mechanism proves only its declared relationship: accepted source-claim checks are separate from generated regions, and unbound prose stays visibly unknown.

An immutable impact plan fixes the changed scope before a check reports on it. This gives the repository four job-specific exits: `drive` writes only planned regions; `check` and `verdict` are read-only; `project` writes declared outputs; and `verify` emits its own outcome receipt. `verdict` and `verify` produce independent receipts. Neither certifies unbound or judgment prose.

The [architecture reference](docs/ARCHITECTURE.md#documentation-flow) and [product contract](SOURCEBOUND_SPEC.md)
name each boundary in detail.

## Current boundaries

- Catalog coverage detects source additions, removals, and replacements; it does not validate prose.
- Source-claim discovery ranks static count and identifier-set candidates. A candidate remains advisory until the repository accepts its exact document and source relationship.
- Declared processes use time, I/O, and environment controls. The host owns network isolation; see the [security model](docs/SECURITY_MODEL.md).
- The manifest decides what Sourcebound evaluates. Authored purpose records goals; Sourcebound does not infer or certify them.
- Feedback is off by default. Enabled runs queue bounded local envelopes; only an explicit `feedback flush` contacts the configured sink, and delivery cannot change a gate result.

Use the [learning path](docs/learn/index.md) for examples. The [product contract](SOURCEBOUND_SPEC.md) owns parser, write-boundary, and exit-code details.
<!-- sourcebound:canonical README.md end -->

## Canonical document: docs/EVALUATION.md

- Source: [docs/EVALUATION.md](../../docs/EVALUATION.md)
- Content sha256: `f0dcfd5c7a3a821636b7a29d49f764d5ecee3a2221b91761b3f00e552b393fc1`

<!-- sourcebound:canonical docs/EVALUATION.md begin -->
# Evaluate documentation tasks

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
A documentation task earns evidence only when the intended person or agent can finish it from the
declared context. This guide lets maintainers build replayable evaluations and bind each result to
the exact task, corpus, response, and scorer.
<!-- sourcebound:end purpose -->

**[Run the recorded tasks](#run-recorded-tasks)**.

A passing run prints the attempted and passed counts for each audience. Those counts are the proof
for that run; a history file binds them to the corpus, prompt, response, model, and scorer digests.

A passing evaluation is a receipt for one task, not a halo around the whole corpus. It records who
attempted what, which context they saw, how the result was scored, and whether it passed. Cover the
reader jobs a consequential corpus promises. Test retrieval, action, verification, recovery from
drift, and stating a documented limit instead of guessing past it.

## Prerequisites

- A valid `.sourcebound.yml`.
- Context files that contain every fact required by the task.
- Recorded response files for agent replay tasks.
- Manifest-allowlisted commands for human command tasks.

## Run recorded tasks

Store a version 1 fixture at `.sourcebound/eval.yml`, then run:

```bash
sourcebound eval --history .sourcebound/evaluation-history.json
```

Replay is the default. It reads recorded responses without invoking a provider. The history is content-addressed and records the corpus, prompt, response, model, scorer, and result for each task.

## Fixture contract

Every task names an audience, prompt, context paths, and scorer. Agent tasks also name either a recorded response adapter or an explicit live command adapter.

<!-- sourcebound:begin evaluation-scorers -->
| scorer | input | passes when |
| --- | --- | --- |
| command | Allowlisted command and documented excerpt | Exit code and required output match |
| configuration | Recorded manifest and fixture repository | Schema validation and check pass |
| structured-output | Recorded JSON and expected value | Parsed values match exactly |
| cited-limit | Recorded answer, canonical citation, and forbidden inferences | The answer cites the declared limit without inferring support |
| mutation-red | Provider proposal, frozen fact, and disposable static repository | The sensitivity state matches without authorizing the relationship |
<!-- sourcebound:end evaluation-scorers -->

A human command expectation must include `documented_as`. sourcebound first finds that exact excerpt in the supplied context, then runs the named allowlisted command and compares its exit code and required output.

This recorded limitation task contains no provider command:

```yaml
version: 1
tasks:
  - id: limitation-retrieval
    audience: agent
    prompt: Does the documented limit permit this behavior?
    context: [.sourcebound/context/evaluation.md]
    model:
      adapter: recorded
      name: recorded-fixture
      response: .sourcebound/evaluation/responses/limitation.txt
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
sourcebound eval --mode live --record-dir .sourcebound/evaluation/live
```

The task's command adapter receives a deterministic JSON prompt on standard input. Before invoking
it, sourcebound writes `<task>.run.json` with the repository, worktree, corpus, prompt, scorer, and
provider-configuration digests, plus the prompt byte count and deadline. Completion adds the
response digest. A provider error or deadline preserves the input receipt and records a hashed error
identity without copying provider output or credentials into the record.
If the provider changes repository bytes outside the record directory, the run becomes a conflict
and evaluation stops.

The result is labeled `model-specific-live`. Move an accepted response into a recorded fixture
before relying on it in offline CI.

## Score dependency sensitivity

Use `mutation-red` when a provider proposes one `sourcebound.binding-proposal.v1` object and the
evaluator owns a separate frozen fact. Point the scorer at a disposable Git repository rather than
letting the provider select its own mutation target:

```yaml
scorer:
  type: mutation-red
  repository: fixtures/pinned-repository
  fact: .sourcebound/evaluation/mutation-target.json
  fact_sha256: 0000000000000000000000000000000000000000000000000000000000000000
  expected_state: sensitive
```

Replace the zero digest with the exact SHA-256 of the frozen target file when the fixture is
created. A digest mismatch is a configuration error, not a failed model task.

The scorer calls the same static sensitivity primitive as
`sourcebound binding sensitivity`. Its task passes when the observed state matches
`expected_state`; that pass does not accept the relationship. The task detail records the complete
sensitivity-receipt digest and says that semantic authority remains false. Score semantic precision
and recall against a separately frozen gold relationship set.

## Adjacent provider paths

Evaluation scores a bounded task. Two separate pages own the provider inputs around that task:

- [Init proposer](INIT_PROPOSER.md) covers optional, allowlisted draft selection during bootstrap.
- [Context compilation](CONTEXT_COMPILATION.md) covers source-addressed evidence packets and budget
  failure.

## Limits

- Scorers are deterministic; live provider output is model-specific.
- Replay proves the saved response against the named corpus digest, not current behavior of the named model.
- Provider commands run only in live mode. The execution environment owns their network isolation.
- Command-provider deadlines accept one to 3,600 seconds. The deadline bounds one process attempt;
  it does not predict how long a model needs for a given prompt.
- Provider-run receipts detect repository byte changes; they do not sandbox the provider process.
- Configuration scoring writes the response only inside a temporary copy of the fixture repository.

## Next step

Run `sourcebound project` before evaluation when a task consumes a generated context bundle, then commit the bundle and evaluation history with the canonical documentation change.
<!-- sourcebound:canonical docs/EVALUATION.md end -->

## Canonical document: docs/INIT_PROPOSER.md

- Source: [docs/INIT_PROPOSER.md](../../docs/INIT_PROPOSER.md)
- Content sha256: `242959cbd97bb63e9eeb7f6146c1deec56db69399753e261f7dbd50a1356ff32`

<!-- sourcebound:canonical docs/INIT_PROPOSER.md begin -->
# Configure the optional init proposer

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this task when deterministic discovery has found candidate facts but a bounded provider should
choose draft inputs for the generated reference. It gives the provider proposal authority only, so
malformed or unsupported selections fail before Sourcebound writes the baseline.
<!-- sourcebound:end purpose -->

**[Configure a contained provider](#configure-the-provider)**.

Without `--model-config`, `sourcebound init` follows the deterministic bootstrap path. Enabling a
provider changes draft selection, not source authority, parsing, or the gate.

## Configure the provider

Save an explicit provider configuration as `.sourcebound/init-provider.yml`. Set `argv[0]` to the
absolute path of an operator-selected command so PATH lookup cannot change the executable. For a
Python provider, `{python}` is the only supported runtime token and is valid only as `argv[0]`; it
resolves to the interpreter running Sourcebound. `env` names only the credentials that command
needs. Do not add `PATH`; Sourcebound supplies a fixed default:

```yaml
adapter: command
name: local-provider
argv: [/absolute/path/to/provider-cli, --json]
timeout_seconds: 300
env: [SOURCEBOUND_PROVIDER_TOKEN]
```

Run init with that configuration:

```bash
sourcebound init --model-config .sourcebound/init-provider.yml
```

## Return bounded selections

The command receives deterministic JSON on standard input and may return only known fact IDs with
allowlisted templates. Its standard output must be one JSON object in this shape:

```json
{
  "drafts": [
    {
      "fact_id": "a fact id copied from the request",
      "template": "provides"
    }
  ]
}
```

The request lists the allowed templates for each fact kind. An empty `drafts` list is valid.
Sourcebound does not pass the repository path, repository working directory, or a write API to the
provider. The command still runs as the caller and can reach absolute host paths or the network when
the host permits it; the [host boundary](SECURITY_MODEL.md#host-boundary) owns that limit.

## Inspect the disclosure receipt

Sourcebound writes `.sourcebound/init-proposer-transcript.json` unless
`--model-transcript` selects another repository-relative path. Absolute paths and paths containing
`..` are rejected. The transcript records the sanitized request, result, and one of three proposer
outcomes: `accept`, `parser-reject`, or `provider-failed`. The separate
`state` is `bootstrap-failed` when the parser accepted the response but repository discovery,
planning, or writing failed afterward. This preserves the parser result while the command exit and
feedback `result_class` record the later failure.

Verify the observed outcome after `init` returns:

```bash
python3 - <<'PY'
import json
from pathlib import Path

receipt = json.loads(
    Path(".sourcebound/init-proposer-transcript.json").read_text(encoding="utf-8")
)
assert receipt["schema"] == "sourcebound.init-proposer-transcript.v1"
assert receipt["state"] == "accepted"
assert receipt["outcome"] == "accept"
assert receipt["model_record"] is not None
print(receipt["outcome"])
PY
```

If that check fails, read `detail` and `state`. `rejected` names a parser refusal,
`provider-failed` names command execution failure, and `bootstrap-failed` names a later repository
failure after an accepted response.

## Failure contract

The parser rejects unknown facts, duplicate selections, unsupported templates, malformed output,
and more than five drafts. A missing, failed, or timed-out provider leaves generated documentation
unwritten. Sourcebound does not block network access; run the selected command in a sandbox when it
must not reach the network.

Return to [evaluation](EVALUATION.md) when the resulting reader task needs a replayable score.
<!-- sourcebound:canonical docs/INIT_PROPOSER.md end -->

## Canonical document: docs/CONTEXT_COMPILATION.md

- Source: [docs/CONTEXT_COMPILATION.md](../../docs/CONTEXT_COMPILATION.md)
- Content sha256: `5f0d1ce2bcbe64254006d1b7134eb70b32dcf112ca406aa10ad6bb91a0fd13e2`

<!-- sourcebound:canonical docs/CONTEXT_COMPILATION.md begin -->
# Compile bounded provider context

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this task when a provider needs selected source facts instead of whole documents. It produces a
content-addressed bundle that says why each item was kept or omitted, so a tight budget returns
unknown rather than silently dropping a required fact.
<!-- sourcebound:end purpose -->

**[Create the request](#create-the-request)**.

## Create the request

<!-- sourcebound:allow section-length reason="The field reference is linked; the complete request builder remains one runnable unit" -->

The request pins its own bytes and every selected source to one repository commit. It also records
the byte budget, source path and line range, evidence authority, relationship, rank, and whether
each item is required. Create `.sourcebound/context-request.json` from the repository's current
README:

```bash
mkdir -p .sourcebound
python3 - <<'PY'
import json
import subprocess
from pathlib import Path

readme = subprocess.check_output(
    ["git", "show", "HEAD:README.md"], text=True
).splitlines()
if not readme:
    raise SystemExit("README.md must be tracked and nonempty")
request = {
    "schema": "sourcebound.context-request.v2",
    "budget_bytes": 4096,
    "items": [{
        "id": "repository-opener",
        "kind": "fact",
        "path": "README.md",
        "start_line": 1,
        "end_line": min(12, len(readme)),
        "authority": "repository-doc",
        "relationship": "repository orientation",
        "reason": "defines the repository for this task",
        "rank": 10,
        "required": True,
        "instruction": False,
    }],
}
Path(".sourcebound/context-request.json").write_text(
    json.dumps(request, indent=2) + "\n",
    encoding="utf-8",
)
PY
```

The request is data. `instruction: false` prevents README prose from gaining instruction authority.
Review and commit it with the source state it selects:

```bash
git diff -- .sourcebound/context-request.json
git add .sourcebound/context-request.json
git commit -m "docs: pin context request"
```

Compilation rejects an untracked or modified request. An `accepted-policy` item can receive
instruction authority only when its pinned source document carries an active
`sourcebound:policy register-v2` marker.

## Compile it

Compile the saved request without invoking a provider:

```bash
sourcebound context compile \
  --request .sourcebound/context-request.json \
  --format json
```

Exit `0` returns a `sourcebound.context-bundle.v2` object with `"status": "current"`.

## Verify the bundle

Verify the schema and status from a fresh compilation:

```bash
sourcebound context compile \
  --request .sourcebound/context-request.json \
  --format json |
python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["schema"] == "sourcebound.context-bundle.v2" and p["status"] == "current"'
```

The result records the pinned request path and SHA-256, then lists included and excluded items with
reasons. Required items are selected first; within the required and optional classes, direct
evidence outranks repository prose. A source-verified accepted policy can carry instruction
authority; ordinary documentation remains data even when its text resembles a prompt. The
[context request reference](REFERENCE.md#context-request) owns the full field and authority
contract.

## Budget failure

If required evidence does not fit, the bundle reports `unknown` and the command exits `2`. Optional
items may be excluded only with a recorded reason. Compilation is lexical and source-addressed; it
does not use semantic retrieval or a vector index.

Use [evaluation](EVALUATION.md) to score what a provider does with the compiled context.
<!-- sourcebound:canonical docs/CONTEXT_COMPILATION.md end -->
