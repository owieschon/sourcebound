# CLI reference

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Choose a command here after you know the repository task. The index names each write boundary, so
you can select the read or repair path without letting a preview change documentation.
<!-- clean-docs:end purpose -->
<!-- clean-docs:allow audience reason="This reference names agent-facing commands and receipt fields as product surfaces" -->

**[Choose from the generated command index](#cli-reference)**.

`clean-docs <command> --help` is the proof for exact flags; every example below must pass the same
argument validator as the executable.

The table is generated from the command registry used by the parser:

<!-- clean-docs:begin cli-reference -->
| command | job | writes | example |
| --- | --- | --- | --- |
| audit | Assess documentation and enforce adopted scopes | with --update-baseline | clean-docs audit --format json |
| inventory | List detected repository surfaces and coverage | no | clean-docs inventory --format json |
| claims | Rank and verify static count and column claims | no | clean-docs claims --format json |
| init | Write a source-bound documentation baseline | yes | clean-docs init --no-model |
| explain | Explain a finding or coverage state | no | clean-docs explain purpose-contract --format json |
| doctor | Check repository and integration readiness | with --bundle | clean-docs doctor --bundle doctor.json |
| verify | Write a local deterministic outcome receipt | with --out | clean-docs verify --out outcome.json |
| benchmark | Measure changed-check time and memory budgets | with --out | clean-docs benchmark --base HEAD~1 --head HEAD |
| derive | Preview or write generated region changes | with --write | clean-docs derive --check |
| drive | Repair bound regions after deterministic policy checks | yes | clean-docs drive |
| plan | Build an immutable read-only documentation impact plan | no | clean-docs plan --base origin/main --head HEAD --format json |
| check | Fail on binding drift or uncovered changed surface | no | clean-docs check --changed --base origin/main --head HEAD |
| project | Regenerate configured documentation projections | unless --check | clean-docs project --check |
| eval | Score human tasks and replayable agent round trips | with --history or live recording | clean-docs eval --fixtures .clean-docs/eval.yml |
| release | Render typed release facts between immutable refs | no | clean-docs release --from v0.9.0 --to HEAD |
| migrate | Upgrade a prior manifest with rollback backup | with --write or --rollback | clean-docs migrate --write |
| emit | Project the manifest into another format | yes | clean-docs emit --help |
| emit stepwise-skill | Write a manifest-derived stepwise skill package | yes | clean-docs emit stepwise-skill --out skill |
| emit llms-txt | Write an index of source-bound documents | yes | clean-docs emit llms-txt --out llms.txt |
| standard | Build or verify the bundled policy pack | varies | clean-docs standard --help |
| standard build | Compile the canonical standard | yes | clean-docs standard build |
| standard check | Fail when the policy pack is stale | no | clean-docs standard check |
<!-- clean-docs:end cli-reference -->

## Impact plans

Use `plan` before a repair when you need to know which documentation contracts a branch can affect.
The command compares the merge base with the requested head, traverses accepted bindings,
projections, and evaluations, and writes nothing to the worktree:

```bash
clean-docs plan --base origin/main --head HEAD --format json
```

The JSON records the clean-docs producer version and every changed path with its base and head blob,
adapter decision, coverage state, and graph roots. Its digest binds that producer and those inputs
to the resulting findings. `clean-docs.impact-plan.v2` also lists
`unsupported_documents`. A changed MDX file enters that list and makes coverage unknown; MDX does
not enter the checked Markdown document count.

| `impact` | Meaning |
| --- | --- |
| `required` | An accepted contract creates documentation work. |
| `recommended` | A known downstream task deserves review but has no gate authority. |
| `none` | Every changed artifact is classified, and the affected graph creates no documentation obligation. |
| `unknown` | A plausible public surface lacks enough adapter or relationship coverage. This is never reported as no impact. |

A valid plan exits zero even when `impact` is `required` or `unknown`; the exit code says the receipt
was built, not that the branch is documentation-complete. Use `check --changed` for the existing
blocking gate. A projection output is evidence of prior work, so changing only that generated file
does not recursively make it an impact root.

## Static-only pull-request checks

Add `--no-exec` to `plan`, `check`, or `verify` when the repository revision is untrusted. Static
first-party extractors continue to run. clean-docs reports each command pin or plugin result as
`skipped-untrusted-execution` and does not start that process.

An unscoped `check --no-exec` can pass its static findings while returning `complete: false`.
`check --changed --no-exec` fails when the pull request affects a skipped relationship because its
state is unknown. The reusable pull-request workflow always selects this mode. Run trusted command
and plugin checks in a separately configured default-branch or scheduled job.

Run `clean-docs <command> --help` for command-specific flags. Return to the [project overview](../README.md) for installation and the supported binding surface.
