# Keep review candidates append-only

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this reference when a compiled review needs a durable denominator across candidate updates. It
checks that each observed problem keeps one recorded disposition without treating that record as a
gate or authorization to change the repository.
<!-- clean-docs:end purpose -->

**[Compile candidates first](IMPROVEMENTS.md#compile-candidates)**.

## Check the current candidate set

Pass the ledger when you compile, then use `--check` in CI:

```bash
clean-docs review candidates \
  --input .clean-docs/reviews/repository-review.json \
  --ledger .clean-docs/reviews/repository-events.json \
  --out .clean-docs/improvement-candidates.json \
  --check \
  --format text
```

The check exits `1` when the compiled set is stale or when the ledger is missing, duplicates, or
retargets a recorded problem. `merged` and `superseded` events point to the candidate that now owns
the work. The ledger records the review denominator; it does not decide whether a change can merge.

## Append a candidate revision

If the summary, citation coordinates, or proposed tests for an existing problem change, append a
revision instead of rewriting the earlier event:

```bash
clean-docs review candidates \
  --input .clean-docs/reviews/repository-review.json \
  --ledger .clean-docs/reviews/repository-events.json \
  --update-ledger \
  --out .clean-docs/improvement-candidates.json \
  --format text
```

The command preserves old event bytes, records the candidate ID it replaces, and moves the ledger
head. It rejects a missing problem or a candidate removed without a declared disposition. Do not
combine `--update-ledger` with `--check`; append the revision, then run the ordinary freshness check.

Ledgers using version 1 remain readable. The first appended revision writes version 2 while keeping
the earlier chained events unchanged.
