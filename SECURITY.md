# Security policy

This policy explains how to report a clean-docs vulnerability and which trust boundaries the current alpha supports.

## Report a vulnerability

Use the repository host's private security-advisory channel. Do not open a public issue with exploit details, repository contents, credentials, or affected user data.

Include:

- The clean-docs version and operating system.
- The command and minimal configuration needed to reproduce the issue.
- The expected and observed behavior.
- Whether the issue reads files outside the repository, executes repository code, changes author-owned prose, or exposes secrets.

You should receive an acknowledgement within seven days. A fix, mitigation, or status update follows after the report is reproduced and scoped.

## Supported alpha boundary

The Version 0.1 alpha parses YAML and Python syntax. It does not import bound Python modules or run repository commands. Manifest paths cannot be absolute or contain parent-directory segments. Generated content may change only the body between one declared marker pair.

The alpha does not yet claim sandboxed plugin or command execution. Do not add command extractors until the execution policy and adversarial E2E suite in the product specification are implemented.
