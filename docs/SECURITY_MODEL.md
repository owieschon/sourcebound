# Security model

This page defines which repository inputs clean-docs treats as data, which declared processes it executes, and where the host must add isolation.

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

Static commands remain useful when no declared process is trusted. `audit`, `inventory`, static `init`, static bindings, projections, recorded evaluation, and release extraction require no repository code execution unless the manifest explicitly adds a command or plugin.

## Adversarial checks

Required CI covers prompt injection, escaping symlinks, shell metacharacters, secret output, oversized output, hanging processes, extension identity collisions, and attempts to change files through relative paths. Each test asserts the exit contract and verifies that no caller-owned file changed.

Report a new bypass through the private channel in the [security policy](../SECURITY.md).
