# Record candidate lifecycle evidence

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this reference after compiling review candidates and before relying on a lifecycle transition.
It records which local evidence proves the attempted state change without granting the record gate
or change authority.
<!-- clean-docs:end purpose -->

**[Compile candidates first](IMPROVEMENTS.md#compile-candidates)**.

## State and compatibility

Version 2 freezes the candidate-set digest and reviewed repository commit, starts each candidate at
`proposed`, and permits adjacent transitions: `proposed` → `reproduced` → `implemented` →
`verified`. `declined` is available from every non-terminal state. Each transition records a
`grounded` or `unknown` resolution. An unavailable reference is written as an attempted transition,
then exits `1`; it is never a success receipt.

Version 1 records remain readable. Reinitialize them before any new transition because their events
do not contain persisted resolutions. `--force` discards history; it is not a migration.

## Evidence contracts

Use a repository-local receipt to reproduce or verify a candidate:

```json
{
  "schema": "clean-docs.lifecycle-test-receipt.v1",
  "repository_commit": "<full reviewed commit SHA>",
  "producer_version": "<tool version>",
  "command": ["<program>", "<argument>"],
  "ok": true
}
```

The lifecycle stores its SHA-256, schema, producer version, reviewed commit, and command. If its
bytes later change, `check` returns `resolution-changed`. To mark a candidate implemented, cite a
full commit SHA that exists locally and descends from the reviewed commit.

Issue and decision evidence need an explicit local-file provider:

```json
{
  "schema": "clean-docs.lifecycle-evidence-providers.v1",
  "providers": {
    "issue": {"kind": "local-file", "root": ".clean-docs/issues"},
    "decision": {"kind": "local-file", "root": ".clean-docs/decisions"}
  }
}
```

Store the configuration at `.clean-docs/lifecycle-evidence-providers.json`. Each reference uses a
forward-slash path inside its configured directory. Missing configuration, files, commits, receipts,
or changed receipt bytes resolve `unknown`; clean-docs does not call a network service to fill them.

## Record and check a transition

Initialize the record once:

```bash
clean-docs review lifecycle init --input .clean-docs/reviews/repository-review.json --out .clean-docs/improvement-lifecycle.json --format text
```

Then record a supported transition:

```bash
clean-docs review lifecycle transition --input .clean-docs/reviews/repository-review.json --state .clean-docs/improvement-lifecycle.json --observation accepted-writing-debt --to reproduced --evidence-kind test-receipt --reference .clean-docs/receipts/accepted-writing-debt.json --detail "The fixture reproduces the accepted finding." --format text
```

Initialization refuses to replace an existing record. Check the record before relying on it:

```bash
clean-docs review lifecycle check --input .clean-docs/reviews/repository-review.json --state .clean-docs/improvement-lifecycle.json --format text
```

The check exits `1` if the candidate set changed, a state was skipped, a stored resolution no longer
matches, or a reference is unknown. It does not run the linked test, accept work, fetch an external
provider, or change another gate result.
