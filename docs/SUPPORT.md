# Support and lifecycle

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Operators come here to adopt an existing corpus, pin the reusable gate, inspect a receipt, or build
a diagnostic bundle. It routes package lifecycle work to one install guide, so each operational
procedure has one canonical home.
<!-- clean-docs:end purpose -->

**[Check the supported environment](#supported-environments)**.

Run `clean-docs doctor` after installation; each reported check is the local readiness proof.

Install, upgrade, rollback, uninstall, and release verification live in the
[install guide](INSTALL.md).

## Supported environments

| Surface | Supported contract |
| --- | --- |
| Python runtime | CPython 3.10, 3.12, and 3.14 |
| Operating system | Current GitHub-hosted Ubuntu and macOS runners |
| Repository adapters | Static Python, TypeScript, JavaScript, OpenAPI, JSON Schema, package metadata, config schemas, and MCP tool discovery |
| Local workflow | CLI and pre-commit hooks |
| Pull-request workflow | Reusable GitHub Actions gate with read-only repository permission |
| Manifest | Versions `1` and `2`; init writes version `2` |
| Plugin process API | Version `1` |

TypeScript and JavaScript adapters parse source without Node.js. The
[security model](SECURITY_MODEL.md) owns the boundary between static input and declared processes.

## Run the reusable pull-request gate

Pin both the reusable workflow and its package input to the same full commit:

```yaml
jobs:
  clean-docs:
    uses: owieschon/clean-docs/.github/workflows/reusable-clean-docs.yml@FULL_40_CHARACTER_CLEAN_DOCS_COMMIT
    with: {package-ref: FULL_40_CHARACTER_CLEAN_DOCS_COMMIT}
```

The workflow rejects tags, branches, abbreviated commits, and non-hexadecimal input before installation. It requests read-only repository permission. Its `clean-docs-evidence` artifact contains the raw audit, binding, and changed-surface reports plus `clean-docs-run.json`. That receipt identifies the installed clean-docs version and commit, the checked repository ref and commit, the workflow run and attempt, each result state, and the byte count and SHA-256 digest of every accompanying evidence file. Keep the artifact with a release or repair receipt when the run itself may expire.

## Adopt an existing documentation corpus

Before init, `audit` is assessment-only unless documents already carry policy markers. `init` is
strict by default: its manifest accepts repository integrity checks as gates, and init rolls back
every bootstrap write when that configured corpus has a blocking integrity or opted-in policy
finding. Unmarked documents keep their native voice; role-compatible policy candidates and
repository-neutral corpus questions do not become accepted debt. Use `audit --preview-policy` to
inspect the compatible policy candidates as bounded advisories before adopting them. A mature
repository can preserve strict future checks while recording existing blocking debt:

```bash
clean-docs init --no-model --accept-hygiene-baseline
git diff -- .clean-docs/audit-baseline.json
clean-docs audit
```

The committed version 2 baseline records each blocking rule, path, normalized offending content,
section anchor, duplicate ordinal, detail, display-only line hint, and fingerprint. Inserting prose
above the finding does not change its identity. Fixing one of two identical findings leaves one
matched entry and one stale entry. Version 1 baselines remain readable; the next
`audit --update-baseline` writes version 2.

Init does not archive or move existing documents from a filename or similarity heuristic.
Ambiguous plans, package-owned evidence, compatibility aliases, prompt templates, and agent
procedures keep their native form. Files named `*.fixture.md` are explicit test inputs rather than
reader documentation. Git-tracked and non-ignored untracked Markdown files enter the corpus;
`.agents` documentation is active, other hidden configuration trees stay out, and tracked MDX is
disclosed as unsupported. A changed MDX file produces unknown impact until an adapter or manual
review resolves it. `audit` fails when a new blocker appears. It also fails with `stale-baseline`
when a recorded blocker is resolved, because the baseline must shrink to match current debt.

For an established README that has not adopted the policy profile, init writes detected source
facts to `.clean-docs/repository-surface.md` and leaves the README unchanged. The manifest binds
that generated file, while `llms.txt` still indexes the README as canonical context. A new or
registered README may own the generated region directly.

The JSON content plan emits at most 100 representative facts and 4,000 bytes of diff per operation.
Large repositories stay reviewable. `fact_count`, `facts_omitted`, `diff_truncated`, the full-plan
digest, and the proposed `canonical_documents` preserve omitted detail without printing a
repository-sized response. `llms.txt` indexes those declared canonical documents and distinguishes
pages with bindings from declared context.

After reviewing intentional documentation repairs, replace the baseline with the current exact findings:

```bash
clean-docs audit --update-baseline
git diff -- .clean-docs/audit-baseline.json
clean-docs audit
```

Review and commit the baseline change with the documentation change. A malformed, tampered, duplicated, or symbolic-link baseline exits `2` instead of weakening the gate.

## Compatibility policy

Manifest versions `1` and `2`, plugin API version `1`, and published machine-readable schemas
remain compatible throughout the 1.x line. A minor release may add optional fields. It cannot
change the meaning of an existing field or silently change normalized evidence for a supported
adapter.

Before removal, release notes and command output announce a deprecation for at least one minor
release. Removing a stable CLI command, manifest field, evidence field, or plugin interface breaks
compatibility. It requires a major release. An incompatible manifest exits `2` and names the
required manifest change before it reads source evidence.

## Record local outcomes

`verify` runs audit, binding, and projection checks and prints `clean-docs.outcome.v2`. Add immutable refs to include pull-request impact, and write the same bytes to a local receipt with:

```bash
clean-docs verify --base origin/main --head HEAD --out .clean-docs/outcome.json
```

The receipt counts current bindings, caught drift, coverage gaps, active and baselined hygiene findings, and projection state. `bound` means a source-specific binding covers the detected locator. `cataloged` means a repository-wide inventory binding tracks the surface but no source-specific documentation claim covers it. `coverage_complete` permits either form; `direct_coverage_complete` requires source-specific bindings or reasoned ignores for the whole detected surface.

Read the receipt's `assurance` object before interpreting a green result. Its
`command_pin_prose_checked`, `cataloged_surfaces_check_prose`, and
`judgment_prose_certified` fields remain `false`: a passing command pin checks configured output,
not the anchored sentence, and a passing configured contract does not certify unbound prose. The
receipt records an `execution` object with `network_isolation: not-provided` and
`network_observation: not-instrumented`. clean-docs sends no feedback from this command, but an
allowed command can use the host network when the runner permits it.

Measure the changed-check P95 and peak process memory on a repository with:

```bash
clean-docs benchmark --base origin/main --head HEAD --out .clean-docs/performance.json
```

The command exits `1` when either published budget is exceeded.

## Build a diagnostic bundle

Write a support-safe JSON bundle with:

```bash
clean-docs doctor --format json --bundle .clean-docs/diagnostic.json
```

The bundle contains runtime versions, repository ref, manifest counts, plugin IDs, and doctor results. It excludes environment variables, credentials, document and source contents, and command arguments. Review the file before attaching it to a private security advisory or public support issue.

Return to the [project overview](../README.md) for the first repository setup, use the
[install guide](INSTALL.md) to move between versions, or read the
[security model](SECURITY_MODEL.md) before declaring a command or plugin.
