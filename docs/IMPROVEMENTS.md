# Turn review findings into testable candidates

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this guide after a human, agent, audit, or external standard review finds a documentation
problem that does not yet have gate authority. It records the observation once, then produces
separate documentation and product test candidates without treating either proposal as an
authorized change.
<!-- clean-docs:end purpose -->

**[Compile the repository's recorded review](#compile-candidates)**.

The output lists proposed work: every candidate has a stable content-derived ID, cited material, two
proposed tests, and explicit `gate_authority: false` and `change_authority: false` fields. Its ID
joins the review, observed problem, summary, citation coordinates, and proposed tests. The
candidate-set digest separately records the cited material's current state, so resolving a receipt
cannot retarget the problem. Compilation validates shape and immutable receipt contracts and, when
run in a repository, resolves repository citations at the pinned review commit. It does not validate
external evidence, judge a proposed test, or prove that the observation set is complete.

## Review observations

Store review evidence outside the reader-facing documentation surface. A
`clean-docs.review-observations.v1` file contains the reviewed repository commit, source URLs, and
one or more observations. The schema requires:

- a stable kebab-case ID and a nonempty summary;
- at least one repository, receipt, or external evidence locator;
- a documentation change with a test setup, action, and passing condition; and
- a product change with its own test setup, action, and passing condition.

Keep summaries to one sentence and use real source URLs as authoring conventions. Repository and
external evidence locators remain assessment inputs. A `receipt` evidence item names a tracked
receipt file plus its SHA-256 bytes, producer version, reviewed commit, and exact command array.
When the receipt file is available, compilation verifies its bytes; a missing file remains
`unknown`, while altered bytes or a different reviewed commit fail. The compiler does not treat an
unknown receipt as grounded evidence or gate authority.

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
  --ledger .clean-docs/reviews/repository-events.json \
  --out .clean-docs/improvement-candidates.json \
  --format text
```

The command writes candidate content only to the explicit output path. It creates missing parent
directories and replaces the file atomically. It rejects missing evidence, a missing documentation
or product track, unsupported test kinds, duplicate observation IDs, and output paths outside the
repository.

When the command runs in a repository, it opens each cited file at the pinned review commit and
searches the locator. The output marks the citation `grounded` or `unknown`; remote sources and
command receipts remain `unverified` until immutable records bind them.

Check that the committed candidate set still matches its observations:

```bash
clean-docs review candidates \
  --input .clean-docs/reviews/repository-review.json \
  --ledger .clean-docs/reviews/repository-events.json \
  --out .clean-docs/improvement-candidates.json \
  --check \
  --format text
```

The check exits `1` when an observation changed without regenerating its candidate set. With a
ledger, it also rejects a missing, duplicate, or retargeted review event. The chained ledger keeps
one candidate disposition for every observation; use `merged` or `superseded` only when it points
to the candidate that now owns the work. In CI, also pass the ledger from the protected base commit
as `--prior-ledger`. A pull request can append events but cannot alter base-branch events. The first
v2 record names the v1 head it replaces; every later record keeps the base ledger unchanged.

## Track candidate lifecycle

After compiling candidates, use the [lifecycle-evidence reference](LIFECYCLE_EVIDENCE.md) to record
local proof for each attempted state change. It explains the permitted states, migration boundary,
and failure behavior. The lifecycle remains assessment-only; the review ledger remains the
denominator.

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
