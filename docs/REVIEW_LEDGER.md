# Keep review candidates append-only

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this reference when a compiled review needs a durable denominator across candidate updates. It
checks that each observed problem keeps one recorded disposition without treating that record as a
gate or authorization to change the repository.
<!-- sourcebound:end purpose -->

**[Compile candidates first](IMPROVEMENTS.md#compile-candidates)**.

## Initialize the denominator

Create the ledger once, before it is protected on the default branch:

```bash
sourcebound review ledger init \
  --input .sourcebound/reviews/repository-review.json \
  --out .sourcebound/reviews/repository-events.json
```

Initialization writes one candidate event for each compiled observation. It refuses to replace an
existing ledger. `--force` is only for a ledger that has not reached a protected branch; published
history must be extended with a new observation and an explicit disposition instead.

## Check the current candidate set

Pass the ledger when you compile, then use `--check` in CI:

```bash
sourcebound review candidates \
  --input .sourcebound/reviews/repository-review.json \
  --ledger .sourcebound/reviews/repository-events.json \
  --out .sourcebound/improvement-candidates.json \
  --check \
  --format text
```

The check exits `1` when the compiled set is stale or when the ledger is missing, duplicates, or
retargets a recorded problem. `merged` and `superseded` events point to the candidate that now owns
the work. The ledger records the review denominator; it does not decide whether a change can merge.

## Protect the base history

In CI, provide the ledger from the protected base commit as `--prior-ledger`. A pull request may
append events, but it cannot alter base-branch events. A version 2 ledger migrated from version 1
binds the version 1 head it replaces; a fresh version 2 ledger has no migration anchor. Record a
changed problem as a new review observation or an explicit `merged` or `superseded` event. Do not
rewrite a prior candidate to make the check green.
