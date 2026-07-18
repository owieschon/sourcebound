# CLI reference

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Choose a command here after you know the repository task. The index names each write boundary, so
you can select the read or repair path without letting a preview change documentation.
<!-- clean-docs:end purpose -->

**[Choose from the generated command index](#cli-reference)**.

`clean-docs <command> --help` is the proof for exact flags; every example below must pass the same
argument validator as the executable.

The table is generated from the command registry used by the parser:

<!-- clean-docs:begin cli-reference -->
| command | job | writes | example |
| --- | --- | --- | --- |
| audit | Assess documentation and enforce adopted scopes | with --update-baseline | clean-docs audit --format json |
| inventory | List detected repository surfaces and coverage | no | clean-docs inventory --format json |
| init | Write a source-bound documentation baseline | yes | clean-docs init --no-model |
| explain | Explain a finding or coverage state | no | clean-docs explain purpose-contract --format json |
| doctor | Check repository and integration readiness | with --bundle | clean-docs doctor --bundle doctor.json |
| verify | Write a local deterministic outcome receipt | with --out | clean-docs verify --out outcome.json |
| benchmark | Measure changed-check time and memory budgets | with --out | clean-docs benchmark --base HEAD~1 --head HEAD |
| derive | Preview or write generated region changes | with --write | clean-docs derive --check |
| drive | Repair bound regions after deterministic policy checks | yes | clean-docs drive |
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

Run `clean-docs <command> --help` for command-specific flags. Return to the [project overview](../README.md) for installation and the supported binding surface.
