# Security model

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Use this model before allowing clean-docs to run a repository command or plugin. It separates static data from declared execution, names the controls clean-docs enforces, and tells operators where the host must provide stronger isolation.
<!-- clean-docs:end purpose -->

**[Review the enforced process controls](#process-controls)**.

The [adversarial checks](#adversarial-checks) are the proof; the host boundary names what those
tests do not claim.

## Trust tiers

| Tier | Input | clean-docs behavior |
| --- | --- | --- |
| Static repository data | Source, manifests, Markdown, schemas, and package metadata | Parse without importing repository modules or evaluating source expressions |
| Declared command | One exact `argv` array named under `execution.allowed_commands` | Run without a shell in a disposable repository copy |
| Declared plugin | One exact `argv` array with API version and interfaces | Exchange versioned JSON in a disposable repository copy |
| Optional phrasing response | Recorded JSON selected by the caller | Validate against deterministic facts before any prose is accepted |

Repository text cannot turn static inventory into process execution. A command or plugin runs only after the manifest names its argument array and compatible interface.

## Process controls

Every declared process receives a copied repository, temporary home, temporary directory, `PATH`, and `NO_COLOR`. clean-docs does not pass other environment variables. It rejects repository symlinks before execution, passes arguments directly without a shell, stops the process at its timeout or 1 MB combined input/output limit, rejects secret-like output, and discards the copy after the result is parsed.

Core code validates response schemas, computes evidence IDs and digests, rejects duplicate identities, and owns coverage state. A plugin cannot replace first-party evidence or write generated documentation directly.

## Host boundary

The process controls are not an operating-system sandbox. A declared executable can open a network connection or address an absolute host path if the surrounding runner permits it. Run untrusted declared code in a network-blocked container or equivalent OS sandbox. Keep local manifests limited to commands and plugins you would run directly.

You can still use `audit`, `inventory`, static `init`, static bindings, projections, recorded task
scoring, and release facts when no declared process is trusted. Those paths do not run repository
code unless the manifest explicitly adds a command or plugin.

For an untrusted pull request, run `plan`, `check`, and `verify` with `--no-exec`. clean-docs skips
manifest commands and plugins, labels the missing assurance, and fails a changed-surface check when
the pull request affects that skipped relationship. The reusable workflow fixes this policy for
pull-request events; a pull request cannot turn trusted execution back on.

## Adversarial checks

Required CI covers prompt injection, escaping symlinks, shell metacharacters, secret output, oversized output, hanging processes, extension identity collisions, and attempts to change files through relative paths. Each test asserts the exit contract and verifies that no caller-owned file changed.

Report a new bypass through the private channel in the [security policy](../SECURITY.md).
