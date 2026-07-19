# Turn review findings into testable candidates

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this guide after a human, agent, audit, or external standard review finds a documentation
problem that does not yet have gate authority. It records the observation once, then produces
separate documentation and product test candidates without treating either proposal as an
authorized change.
<!-- clean-docs:end purpose -->

**[Compile the repository's recorded review](#compile-candidates)**.

The output is the proof surface: every candidate has a content-derived ID, evidence, two proposed
tests, and explicit `gate_authority: false` and `change_authority: false` fields.

## Review observations

Store review evidence outside the reader-facing documentation surface. A
`clean-docs.review-observations.v1` file contains the reviewed repository commit, source URLs, and
one or more observations. Each observation requires:

- a stable kebab-case ID and one-sentence summary;
- at least one repository, receipt, or external evidence locator;
- a documentation change with a test setup, action, and passing condition; and
- a product change with its own test setup, action, and passing condition.

The compiler accepts `command`, `fixture`, `integration`, `reader-task`, `release`, and
`static-analysis` tests. The [security model](SECURITY_MODEL.md) owns process execution. These
labels describe proposed evidence, not an allowed command or an accepted test.

This separation prevents two common category errors. A prose problem does not prove that a new
lint rule is safe, and a missing product mechanism cannot be closed by adding a caveat to the
documentation. The two tracks may converge in one change only after each proposed test has a real
fixture and assertion.

## Compile candidates

Compile the observations and write the deterministic candidate set:

```bash
clean-docs review candidates \
  --input .clean-docs/reviews/wizard-docs-context-mill.json \
  --out .clean-docs/improvement-candidates.json \
  --format text
```

The command writes only the explicit output path. It rejects missing evidence, a missing
documentation or product track, unsupported test kinds, duplicate observation IDs, and output
paths outside the repository.

Check that the committed candidate set still matches its observations:

```bash
clean-docs review candidates \
  --input .clean-docs/reviews/wizard-docs-context-mill.json \
  --out .clean-docs/improvement-candidates.json \
  --check \
  --format text
```

The check exits `1` when an observation changed without regenerating its candidate set.
The repository CI runs this check after installing the current checkout.

## Move from candidate to verified change

Use this sequence for each candidate:

1. Reproduce the observation against its pinned evidence.
2. Implement the smallest documentation or product test that fails for the observed reason.
3. Make the change that passes that test without weakening an existing boundary.
4. Run the ordinary clean-docs and repository gates.
5. Record the verified change in the repository's issue or pull-request system.

The candidate compiler never performs these transitions. Aggregate operational behavior belongs
in the separately governed [feedback and behavior-signal path](BEHAVIOR_SIGNALS.md); a qualitative
review must not masquerade as a metric or establish causality.

Use the [evaluation guide](EVALUATION.md) when a proposed test needs a recorded human or agent task,
and the [CLI reference](CLI.md) for the command's exact write boundary.
