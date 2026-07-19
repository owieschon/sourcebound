# Keep review candidates append-only

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this reference when a compiled review needs a durable denominator across candidate updates. It
checks that each observed problem keeps one recorded disposition without treating that record as a
gate or authorization to change the repository.
<!-- sourcebound:end purpose -->

**[Compile candidates first](IMPROVEMENTS.md#compile-candidates)**.

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
append events, but it cannot alter base-branch events. The first version 2 record binds the version
1 head it replaces; later records preserve that anchor. Record a changed problem as a new review
observation or an explicit `merged` or `superseded` event. Do not rewrite a prior candidate to make
the check green.
