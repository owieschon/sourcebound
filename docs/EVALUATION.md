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
