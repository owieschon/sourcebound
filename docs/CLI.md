# CLI reference

This page is the lookup table for every clean-docs command and its write behavior.

The table is generated from the command registry used by the parser:

<!-- clean-docs:begin cli-reference -->
| command | job | writes |
| --- | --- | --- |
| audit | Inventory and check repository documentation | no |
| inventory | List detected repository surfaces and coverage | no |
| init | Write a source-bound documentation baseline | yes |
| explain | Explain a finding or coverage state | no |
| doctor | Check repository and integration readiness | no |
| verify | Write a local deterministic outcome receipt | with --out |
| benchmark | Measure changed-check time and memory budgets | with --out |
| derive | Preview generated region changes | with --write |
| drive | Repair bound regions and enforce policy | yes |
| check | Fail on binding drift or uncovered changed surface | no |
| project | Regenerate configured documentation projections | yes |
| eval | Score human tasks and replayable agent round trips | with --history or live recording |
| release | Render typed release facts between immutable refs | no |
| migrate | Upgrade a prior manifest with rollback backup | with --write or --rollback |
| emit | Project the manifest into another format | yes |
| emit stepwise-skill | Write a manifest-derived stepwise skill package | yes |
| emit llms-txt | Write an index of source-bound documents | yes |
| standard | Build or verify the bundled policy pack | varies |
| standard build | Compile the canonical standard | yes |
| standard check | Fail when the policy pack is stale | no |
<!-- clean-docs:end cli-reference -->

Run `clean-docs <command> --help` for command-specific flags. Return to the [project overview](../README.md) for installation and the supported binding surface.
