# Contributing to Sourcebound

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this guide when changing Sourcebound code, documentation, or generated projections. It keeps each change reviewable by requiring an observed problem, a bounded contract, and evidence that the changed boundary behaves as claimed.
<!-- sourcebound:end purpose -->

**[Read the product contract](SOURCEBOUND_SPEC.md)** before changing a guarantee or authority boundary.

## Prepare one reviewable change

1. State the observed reader or repository problem and the source that establishes it.
2. Change the smallest contract that owns that problem. Do not turn catalog visibility or a model suggestion into gate authority.
3. Add a positive case, a negative boundary case, and a compatibility case when behavior changes.
4. Run `sourcebound project`, then `sourcebound check` and `sourcebound verify --no-exec` so generated outputs and receipts match the source.

## Use AI assistance with review evidence

AI assistance is permitted. The pull request must still identify the human-reviewed evidence, the
tests run, and any uncertainty or unverified claim. Do not add a co-author trailer unless it
accurately records the contribution.

The [pull request template](.github/pull_request_template.md) requests the same evidence. It does
not make an AI-disclosure choice a substitute for review.
