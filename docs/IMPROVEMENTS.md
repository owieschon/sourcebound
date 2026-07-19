# Turn review findings into testable candidates

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this guide after a human, agent, audit, or external standard review finds a documentation
problem that does not yet have gate authority. It records the observation once, then produces
separate documentation and product test candidates without treating either proposal as an
authorized change.
<!-- clean-docs:end purpose -->

**[Compile the repository's recorded review](#compile-candidates)**.

The output indexes proposed work: every candidate has a content-derived ID, evidence fields, two
proposed tests, and explicit `gate_authority: false` and `change_authority: false` fields.
Compilation validates shape. `--check` validates projection freshness. Neither mode resolves an
evidence locator, judges whether a proposed test is adequate, or proves that the observation set is
complete.

## Review observations

Store review evidence outside the reader-facing documentation surface. A
`clean-docs.review-observations.v1` file contains the reviewed repository commit, source URLs, and
one or more observations. The schema requires:

- a stable kebab-case ID and a nonempty summary;
- at least one repository, receipt, or external evidence locator;
- a documentation change with a test setup, action, and passing condition; and
- a product change with its own test setup, action, and passing condition.

Keep summaries to one sentence and use real source URLs as authoring conventions. The current
schema accepts any nonempty source string and does not enforce sentence count.

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
  --input .clean-docs/reviews/repository-review.json \
  --out .clean-docs/improvement-candidates.json \
  --format text
```

The command writes candidate content only to the explicit output path. It creates missing parent
directories and replaces the file atomically. It rejects missing evidence, a missing documentation
or product track, unsupported test kinds, duplicate observation IDs, and output paths outside the
repository.

Check that the committed candidate set still matches its observations:

```bash
clean-docs review candidates \
  --input .clean-docs/reviews/repository-review.json \
  --out .clean-docs/improvement-candidates.json \
  --check \
  --format text
```

The check exits `1` when an observation changed without regenerating its candidate set. It compares
the input projection with the committed output; deleting an observation and regenerating produces a
smaller current set. An independent issue or review ledger must prove the denominator until the
product receipts observation history directly. The repository CI runs the freshness check after
installing the current checkout.

## Track candidate lifecycle

Initialize one lifecycle record from the review. It binds every observation ID and candidate ID to
the exact candidate-set digest, starts every record at `proposed`, and remains assessment-only:

```bash
clean-docs review lifecycle init --input .clean-docs/reviews/repository-review.json --out .clean-docs/improvement-lifecycle.json --format text
```

Initialization refuses to replace an existing record. Use `--force` only when intentionally
discarding its history.

This lifecycle protects one frozen candidate set. It cannot reconcile a changed set or prove that
all review events were recorded, so the independent issue or review ledger remains the denominator.
`--force` resets history rather than migrating it.

Advance one candidate only through adjacent states: `proposed` → `reproduced` → `implemented` →
`verified`, or `declined` from any non-terminal state. Every transition needs a typed reference.
To mark a candidate reproduced or verified, point to a `test-receipt`. To mark one implemented,
point to a commit or issue. To decline one, point to an issue or decision:

```bash
clean-docs review lifecycle transition --input .clean-docs/reviews/repository-review.json --state .clean-docs/improvement-lifecycle.json --observation accepted-writing-debt --to reproduced --evidence-kind test-receipt --reference tests/test_improvements.py --detail "The fixture reproduces the accepted finding." --format text
```

Check the lifecycle before relying on it. The check fails if the review changed, a candidate ID no
longer matches, or any history skips a state:

```bash
clean-docs review lifecycle check --input .clean-docs/reviews/repository-review.json --state .clean-docs/improvement-lifecycle.json --format text
```

The lifecycle validates state-compatible evidence kinds and records reference strings. It does not
resolve a commit, issue, decision, or test receipt, accept the linked work, or change an ordinary
gate result.

## Move from candidate to verified change

Use this sequence for each candidate:

1. Reproduce the observation against its pinned evidence.
2. Implement the smallest documentation or product test that fails for the observed reason.
3. Make the change that passes that test without weakening an existing boundary.
4. Run the ordinary clean-docs and repository gates.
5. Record the verified change in the repository's issue or pull-request system.

The lifecycle compiler records these transitions but never performs the linked work. Aggregate
operational behavior belongs in the separately governed [feedback and behavior-signal
path](BEHAVIOR_SIGNALS.md); a qualitative review must not masquerade as a metric or establish
causality.

Use the [evaluation guide](EVALUATION.md) when a proposed test needs a recorded human or agent task,
and the [CLI reference](CLI.md) for the command's exact write boundary.
