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
