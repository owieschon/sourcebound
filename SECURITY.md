# Security policy

This policy explains how to report a clean-docs vulnerability and what support to expect.

## Report a vulnerability

Use the repository host's private security-advisory channel. Do not open a public issue with exploit details, repository contents, credentials, or affected user data.

Include:

- The clean-docs version and operating system.
- The command and minimal configuration needed to reproduce the issue.
- The expected and observed behavior.
- Whether the issue reads files outside the repository, executes repository code, changes author-owned prose, or exposes secrets.

You should receive an acknowledgement within seven days. A fix, mitigation, or status update follows after the report is reproduced and scoped.

## Supported boundary

Static adapters parse source without importing repository modules. Manifest paths cannot be absolute or contain parent-directory segments. Generated content may change only the body between one declared marker pair.

Declared commands and plugins run in disposable repository copies with minimal environments, timeouts, active combined-I/O limits, symlink rejection, and secret-output rejection. These controls contain repository-relative writes. The execution environment still owns operating-system and network isolation for untrusted declared code.

Read the [security model](docs/SECURITY_MODEL.md) for the trust tiers, enforced controls, and explicit non-goals.
