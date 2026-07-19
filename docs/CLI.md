# CLI reference

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Choose a command here after you know the repository task. The index names each write boundary, so
you can select the read or repair path without letting a preview change documentation.
<!-- sourcebound:end purpose -->
<!-- sourcebound:allow audience reason="This reference names agent-facing commands and receipt fields as product surfaces" -->

**[Choose from the generated command index](#cli-reference)**.

`sourcebound <command> --help` is the proof for exact flags; every example below must pass the same
argument validator as the executable.

The table is generated from the command registry used by the parser:

<!-- sourcebound:begin cli-reference -->
| command | job | writes | example |
| --- | --- | --- | --- |
| audit | Assess documentation and enforce adopted scopes | with --update-baseline | sourcebound audit --format json |
| residue | Manage private cross-project residue matching | with init-local | sourcebound residue status |
| residue status | Report whether private residue matching is active | no | sourcebound residue status |
| residue init-local | Create a permission-restricted private residue template | yes | sourcebound residue init-local |
| inventory | List detected repository surfaces and coverage | no | sourcebound inventory --format json |
| claims | Rank and verify static count and column claims | no | sourcebound claims --format json |
| binding | Inspect one proposed source relationship | no | sourcebound binding --help |
| binding sensitivity | Test whether one static check depends on a frozen source fact | no | sourcebound binding sensitivity --help |
| context | Compile provider-neutral evidence packets | no | sourcebound context --help |
| context compile | Compile a bounded source-addressed context bundle | no | sourcebound context compile --request context-request.json |
| review | Turn review observations into testable improvement candidates | with --out | sourcebound review --help |
| review candidates | Compile documentation and product test candidates from one review | with --out | sourcebound review candidates --input review-observations.json |
| review lifecycle | Track assessment-only candidate status with typed evidence | with init or transition | sourcebound review lifecycle --help |
| review lifecycle init | Initialize a lifecycle record for one candidate set | yes | sourcebound review lifecycle init --input review.json --out lifecycle.json |
| review lifecycle transition | Apply one evidence-backed candidate transition | yes | sourcebound review lifecycle transition --help |
| review lifecycle check | Check a lifecycle record against its candidate set | no | sourcebound review lifecycle check --input review.json --state lifecycle.json |
| init | Write a source-bound documentation baseline | yes | sourcebound init --no-model |
| explain | Explain a finding or coverage state | no | sourcebound explain purpose-contract --format json |
| doctor | Check repository and integration readiness | with --bundle | sourcebound doctor --bundle doctor.json |
| verify | Write a local deterministic outcome receipt | with --out | sourcebound verify --out outcome.json |
| benchmark | Measure changed-check time and memory budgets | with --out | sourcebound benchmark --base HEAD~1 --head HEAD |
| derive | Preview or write generated region changes | with --write | sourcebound derive --check |
| drive | Repair bound regions after deterministic policy checks | yes | sourcebound drive |
| plan | Build an immutable read-only documentation impact plan | no | sourcebound plan --base origin/main --head HEAD --format json |
| verdict | Compose one coverage-stating static PR verdict | no | sourcebound verdict --base origin/main --head HEAD --format json |
| check | Fail on binding drift or uncovered changed surface | no | sourcebound check --changed --base origin/main --head HEAD |
| project | Regenerate configured documentation projections | unless --check | sourcebound project --check |
| eval | Score human tasks and replayable agent round trips | with --history or live recording | sourcebound eval --fixtures .sourcebound/eval.yml |
| release | Render typed release facts between immutable refs | no | sourcebound release --from v0.9.0 --to HEAD |
| migrate | Upgrade a prior manifest with rollback backup | with --write or --rollback | sourcebound migrate --write |
| feedback | Manage opt-in operational feedback | yes | sourcebound feedback status |
| feedback enable | Consent to a named feedback sink | yes | sourcebound feedback enable --sink local |
| feedback status | Show feedback consent and pending counts | no | sourcebound feedback status |
| feedback preview | Print exact pending envelope bytes | no | sourcebound feedback preview |
| feedback flush | Deliver pending feedback envelopes | yes | sourcebound feedback flush |
| feedback disable | Remove feedback delivery authority | yes | sourcebound feedback disable |
| feedback rotate | Replace the feedback installation identifier | yes | sourcebound feedback rotate |
| feedback purge | Delete local feedback state | yes | sourcebound feedback purge |
| feedback signal | Validate or ingest aggregate behavior signals | varies | sourcebound feedback signal validate --input signal.json |
| feedback signal prepare | Add a canonical content-derived signal ID | no | sourcebound feedback signal prepare --input signal-body.json |
| feedback signal validate | Validate one aggregate behavior signal | no | sourcebound feedback signal validate --input signal.json |
| feedback signal ingest | Create an observed improvement case | yes | sourcebound feedback signal ingest --input signal.json |
| feedback case | Advance a verified improvement case | yes | sourcebound feedback case transition --case ID --to reproduced --receipt receipt.json |
| feedback case transition | Apply one adjacent evidence-backed state transition | yes | sourcebound feedback case transition --case ID --to reproduced --receipt receipt.json |
| emit | Project the manifest into another format | yes | sourcebound emit --help |
| emit stepwise-skill | Write a manifest-derived stepwise skill package | yes | sourcebound emit stepwise-skill --out skill |
| emit llms-txt | Write an index of source-bound documents | yes | sourcebound emit llms-txt --out llms.txt |
| standard | Build or verify the bundled policy pack | varies | sourcebound standard --help |
| standard build | Compile the canonical standard | yes | sourcebound standard build |
| standard check | Fail when the policy pack is stale | no | sourcebound standard check |
<!-- sourcebound:end cli-reference -->

## Impact plans

Use `plan` before a repair when you need to know which documentation contracts a branch can affect.
The command compares the merge base with the requested head, traverses accepted bindings,
projections, and evaluations, and writes nothing to the worktree:

```bash
sourcebound plan --base origin/main --head HEAD --format json
```

The JSON records the sourcebound producer version and every changed path with its base and head blob,
adapter decision, coverage state, and graph roots. Its digest binds that producer and those inputs
to the resulting findings. `sourcebound.impact-plan.v2` also lists
`unsupported_documents`. Structurally valid MDX uses the `mdx-static` adapter and counts as a direct
document change. Malformed MDX or a missing Node.js 20 runtime uses `mdx-static:failed`, enters the
unsupported list, and makes coverage unknown.

| `impact` | Meaning |
| --- | --- |
| `required` | An accepted contract creates documentation work. |
| `recommended` | A known downstream task deserves review but has no gate authority. |
| `none` | Every changed artifact is classified, and the affected graph creates no documentation obligation. |
| `unknown` | A plausible public surface lacks enough adapter or relationship coverage. This is never reported as no impact. |

Observe-only `review_contracts` appear in the plan's `review_contracts` evidence. A
`review-recommended` or unresolved contract also adds an advisory entry to
`findings.recommended`; it never enters `findings.required`. Each observation names the contract,
source and target locator states and digests, and `semantic_correctness_checked: false`. The
pull-request verdict preserves the same observations and reports their state counts under
`mechanisms.review-contract`. Its `affects` and `requests-review` graph edges describe observation
topology. They do not add artifact roots, make an artifact covered, change `coverage_complete`, or
authorize repair. An observation can make the impact summary `recommended`; it does not change the
gate result.

Use `plan --project PATH` when a repository contains independently owned projects. The selected
project scopes the manifest, changed paths, inventory, and static impact evidence. Immutable
materialization includes that project plus transitive repository-internal targets required by its
symlinks. Read the receipt's `project` field before reusing `impact: none`; sibling projects remain
outside that conclusion.

A valid plan exits zero even when `impact` is `required` or `unknown`; the exit code says the receipt
was built, not that the branch is documentation-complete. Use `check --changed` for the existing
blocking gate. A projection output is evidence of prior work, so changing only that generated file
does not recursively make it an impact root.

When a GitHub Actions workflow limits an event with `paths`, the plan reports changed paths outside
that filter as `ci-path-filter-unverified`. The static result is `unknown`: a workflow-level success
does not prove that its specialized job ran. Attach a run receipt before treating that job as
evidence; missing credentials or run data remain unknown rather than a passing check.

## Pull-request verdicts

Use `verdict` when a pull-request runner or agent needs one decision instead of interpreting audit,
binding, projection, and changed-surface outputs independently:

```bash
sourcebound verdict \
  --base origin/main \
  --head HEAD \
  --format json > sourcebound-verdict.json
```

The caller worktree must be clean, and `--head` must resolve to the checked-out commit. The command
uses static first-party adapters only. It does not run repository commands or plugins, write cache
entries, or change the worktree.

`sourcebound.pr-verdict.v1` is the canonical agent integration receipt. It includes:

- producer version, requested base, merge base, and head commit;
- manifest and impact-plan digests;
- audit and accepted-baseline state;
- separate region, command-pin, symbol, plugin, source-claim, and projection counts;
- changed files, required work, gaps, ignores, unsupported documents, and impact state;
- inventory totals split into direct bindings, catalog-only records, ignores, and unknowns;
- every skipped binding, command, and plugin ID;
- stable findings with a repair action; and
- six explicit non-claims covering unbound prose, judgment prose, mutation sensitivity,
  review-contract co-change, catalog coverage, and observation completeness.

The receipt separates the blocking decision from advisory review evidence:

| axis | states | effect |
| --- | --- | --- |
| `gate` | `ready`, `not_ready`, `unknown` | Controls the command exit code. |
| `observations` | `clear`, `review-recommended`, `unknown` | Reports review-contract evidence without changing the exit code. |

Top-level `state` and `ready` are compatibility aliases for `gate.state` and `gate.ready`. A ready
gate can coexist with `observations.complete: false`; gate readiness is not observation
completeness.

| `state` | Exit | Meaning |
| --- | --- | --- |
| `ready` | `0` | The branch passes within `required-gates-and-changed-surface`. Read coverage, skips, observations, and non-claims before reusing the result. |
| `not_ready` | `1` | Deterministic drift or an enforced integrity defect blocks the branch. |
| `unknown` | `1` | A plausible obligation lacks supported evidence, or affected declared execution was skipped. |
| `invalid` | `2` or `3` | A ref, caller state, manifest, or supplied receipt failed validation (`2`), or static extraction failed (`3`). |

`--format sarif` reports the same finding IDs and verdict digest as JSON. A valid verdict with no
findings still emits a complete JSON receipt; SARIF remains an annotation projection of that
receipt.

Repeat `--mutation-receipt PATH` to summarize a
`sourcebound.binding-sensitivity.v1` receipt. sourcebound checks its commit and mutation-plan digest
before including its byte digest and state. The receipt cannot change the verdict and must keep
`semantic_relationship_authorized` false. A `sensitive` result only shows that the check went stale
after the frozen fact changed. It does not let sourcebound accept the relationship.

## Static-only pull-request checks

Add `--no-exec` to `inventory`, `plan`, `check`, or `verify` when the repository revision is
untrusted. Static first-party extractors continue to run. Static inventory lists skipped discoverer
plugin IDs. The other commands report each skipped command pin or plugin result as
`skipped-untrusted-execution` and do not start that process.

An unscoped `check --no-exec` can pass its static findings while returning `complete: false`.
`check --changed --no-exec` fails when the pull request affects a skipped relationship because its
state is unknown. `verdict` is unconditionally static-only; the reusable pull-request workflow uses
that one receipt as its result and exposes no execution switch. Run trusted command and plugin
checks in a separately configured default-branch or scheduled job.

Run `sourcebound <command> --help` for command-specific flags. Return to the [project overview](../README.md) for installation and the supported binding surface.
