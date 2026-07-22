# Security model

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this model before allowing sourcebound to run a repository command or plugin. It separates static data from declared execution, names the controls sourcebound enforces, and tells operators where the host must provide stronger isolation.
<!-- sourcebound:end purpose -->

**[Review the enforced process controls](#process-controls)**.

The [adversarial checks](#adversarial-checks) are the proof; the host boundary names what those
tests do not claim.

## Trust tiers

| Tier | Input | sourcebound behavior |
| --- | --- | --- |
| Static repository data | Source, manifests, Markdown, MDX, schemas, and package metadata | Parse without importing repository modules or evaluating source expressions |
| Declared command | One exact `argv` array named under `execution.allowed_commands` | Run without a shell in a disposable repository copy |
| Declared plugin | One exact `argv` array with API version and interfaces | Exchange versioned JSON in a disposable repository copy |
| Optional phrasing response | Recorded JSON selected by the caller | Validate against deterministic facts before any prose is accepted |

Repository text cannot turn static inventory into process execution. A command or plugin runs only after the manifest names its argument array and compatible interface.

The MDX adapter is a bundled, pinned parser running in a temporary directory with a reduced
environment. It parses the document to a source-positioned syntax tree. It does not compile or
evaluate the document, resolve ESM imports, load JSX components, or invoke repository package
scripts. Node.js is an implementation runtime for this first-party parser, not a repository-declared
process.

## Process controls

Every declared process receives a copied repository, temporary home, temporary directory, `PATH`, and `NO_COLOR`. sourcebound does not pass other environment variables. It rejects repository symlinks before execution, passes arguments directly without a shell, stops the process at its timeout or 1 MB combined input/output limit, rejects secret-like output, and discards the copy after the result is parsed.

Secret rules are a best-effort denylist that biases toward over-redaction, not an exhaustive detector; they provide defense in depth behind the host sandbox.

Core code validates response schemas, computes evidence IDs and digests, rejects duplicate identities, and owns coverage state. A plugin cannot replace first-party evidence or write generated documentation directly.

## Host boundary

The process controls are not an operating-system sandbox. A declared executable can open a network connection or address an absolute host path if the surrounding runner permits it. Run untrusted declared code in a network-blocked container or equivalent OS sandbox. Keep local manifests limited to commands and plugins you would run directly.

The sandbox inherits the host `PATH`, so a bare command name resolves against host binaries. Pin an absolute `argv[0]` path or run in a container with a controlled `PATH` when the command identity matters.

You can still use `audit`, `inventory --no-exec`, static `init`, static bindings, projections,
recorded task scoring, and release facts when no declared process is trusted. Those paths do not
run repository code. Plain `inventory` may start an explicitly declared discoverer plugin, so use
its static flag for an untrusted revision.

Context compilation reads both its request and selected source bytes from the current repository
commit. It rejects an external, untracked, or modified request. A request label cannot promote
ordinary prose into instructions: `accepted-policy` requires an active policy marker in the pinned
source document before the bundle sets `instruction_allowed`.

Live evaluation is different: its explicit command provider is a process selected by the operator.
sourcebound records repository bytes before launch and rejects an unexpected change afterward, but
it does not sandbox the process or revoke host access. Use an execution environment that enforces
the provider's filesystem and network boundary.

The optional init proposer runs in a disposable directory with only `PATH`, `NO_COLOR`, and
operator-declared environment-variable names. Its prompt is sanitized before launch and its
transcript redacts secret-like response values. `_draft_text` still renders raw `fact.name` values
after selection; that pre-existing, model-independent output path remains outside prompt sanitization.

## Feedback transport

Feedback is off by default. A disabled run does not create an identifier, envelope, outbox record,
or network request. `feedback enable` writes a visible configuration with a named sink and a
pseudonymous installation identifier. Credentials stay in an operator-selected environment
variable and are read only by an explicit `feedback flush`.

The outgoing envelope contains bounded operational classes and digests. It excludes source, prose,
paths, remotes, command arguments, prompts, model responses, environment values, credentials, and
unbounded errors. `preview` exposes the exact pending envelope bytes before delivery. Connected
adapters may wrap those bytes in a transport-specific request.

Capture failures are swallowed after the original command result is known. Transport failures make
only `feedback flush` non-zero and leave the envelope queued for a bounded retry. Neither path can
turn a failed documentation gate green or a passing gate red.

Incoming behavior signals are aggregate, schema-closed evidence. They can create an observed
improvement case, but they cannot authorize purpose, policy, scorers, safety boundaries, source
relationships, or repository writes. The [feedback contract](FEEDBACK.md) owns the required
state transitions in the [behavior-signal contract](BEHAVIOR_SIGNALS.md).

For an untrusted pull request, run `inventory`, `plan`, `check`, and `verify` with `--no-exec`.
sourcebound skips manifest commands and plugins, labels the missing assurance, and fails a
changed-surface check when the pull request affects that skipped relationship. `verdict` is always
static-only. The reusable workflow runs one verdict and exposes no input that can turn trusted
execution on. It starts Python in isolated mode and writes evidence under the runner's trusted
temporary directory, not the inspected checkout. An unsafe repository symlink fails the verdict
instead of redirecting a receipt write.

## Private residue rules

The tracked `.sourcebound-residue.yml` policy is public and contains exclusions only. Do not put a
token, a token digest, or a private rule in it; an unsalted digest can reveal a low-entropy token.

To enable local cross-project residue matching, run `sourcebound residue init-local`. It creates the
ignored `.sourcebound-residue.local.yml` with mode `0600` on POSIX. Add plaintext rules only there.
`sourcebound residue status` reports whether matching is active without printing rule values or
digests. CI has no local policy and reports inactive matching honestly.

The residue scanner also checks tracked policy labels, patterns, and reasons against active
restricted terms. It does not interpret a digest as text and returns a redacted finding when policy
metadata repeats restricted context.

## Adversarial checks

Required CI covers prompt injection, escaping symlinks, shell metacharacters, secret output, oversized output, hanging processes, extension identity collisions, and attempts to change files through relative paths. Each test asserts the exit contract and verifies that no caller-owned file changed.

Report a new bypass through the private channel in the [security policy](../SECURITY.md).
