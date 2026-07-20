# Security policy

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Reporters use this policy to route a suspected sourcebound vulnerability without exposing the
exploit or affected data. It names the evidence the maintainers need, the material that stays
private, and the response window.
<!-- sourcebound:end purpose -->

**[Open a private security advisory](#report-a-vulnerability)**.

The acknowledgement and scoped response are the proof that the report entered the private path.

## Report a vulnerability

Use the repository host's private security-advisory channel. Do not open a public issue with exploit details, repository contents, credentials, or affected user data.

Include:

- The sourcebound version and operating system.
- The command and minimal configuration needed to reproduce the issue.
- The expected and observed behavior.
- Whether the issue reads files outside the repository, executes repository code, changes author-owned prose, or exposes secrets.

You should receive an acknowledgement within seven days. A fix, mitigation, or status update follows after the report is reproduced and scoped.

## Supported boundary

Static adapters parse source without importing repository modules. Manifest paths cannot be absolute or contain parent-directory segments. Generated content may change only the body between one declared marker pair.

Declared commands and plugins run in disposable repository copies. They receive a minimal set of
environment variables, timeouts, and active combined-I/O limits; sourcebound rejects symlinks and
secret-like output. These controls contain repository-relative writes. The host must still block
network access and sandbox untrusted declared code.

Read the [security model](docs/SECURITY_MODEL.md) for the trust tiers, enforced controls, and explicit non-goals.
