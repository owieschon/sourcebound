# Support and lifecycle

<!-- clean-docs:purpose -->
Use this guide when adopting, upgrading, rolling back, diagnosing, or requesting help for clean-docs. It prevents unsupported assumptions from entering a production gate and gives operators the exact compatibility, evidence, and recovery procedures for a supported installation.
<!-- clean-docs:end purpose -->
## Supported environments

| Surface | Supported contract |
| --- | --- |
| Python runtime | CPython 3.10, 3.12, and 3.14 |
| Operating system | Current GitHub-hosted Ubuntu and macOS runners |
| Repository adapters | Static Python, TypeScript, JavaScript, OpenAPI, JSON Schema, package metadata, config schemas, and MCP tool discovery |
| Local workflow | CLI and pre-commit hooks |
| Pull-request workflow | Reusable GitHub Actions gate with read-only repository permission |
| Manifest | Version `1` |
| Plugin process API | Version `1` |

TypeScript and JavaScript support is static. clean-docs does not require Node.js and does not execute project modules to discover their public surface.

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

`init` is strict by default. It rolls back every bootstrap write when the current corpus has a hygiene finding. A mature repository can preserve that behavior for future changes while recording its current debt:

```bash
clean-docs init --no-model --accept-hygiene-baseline
git diff -- .clean-docs/audit-baseline.json
clean-docs audit
```

The committed baseline records each exact rule, path, line, detail, and fingerprint. Adoption mode does not archive or move existing documents. It does not ignore a rule or reader-facing directory. Hidden configuration trees are outside the documentation corpus. `audit` fails when a new finding appears. It also fails with `stale-baseline` when a recorded finding is resolved, because the baseline must shrink to match current debt.

After reviewing intentional documentation repairs, replace the baseline with the current exact findings:

```bash
clean-docs audit --update-baseline
git diff -- .clean-docs/audit-baseline.json
clean-docs audit
```

Review and commit the baseline change with the documentation change. A malformed, tampered, duplicated, or symbolic-link baseline exits `2` instead of weakening the gate.

## Compatibility policy

Manifest version `1`, plugin API version `1`, and published machine-readable schemas remain compatible throughout the 1.x line. A minor release may add optional fields. It cannot change the meaning of an existing field or silently change normalized evidence for a supported adapter.

A deprecation appears in release notes and command output for at least one minor release before removal. Removing a stable CLI command, manifest field, evidence field, or plugin interface requires a major release. An incompatible manifest exits `2` with an exact migration action before extraction.

## Install, upgrade, roll back, and uninstall

Create an isolated environment before installing a release wheel:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install ./clean_docs-1.0.0-py3-none-any.whl
clean-docs --version
```

Upgrade by installing the newer wheel and preview any requested schema migration before writing:

```bash
python -m pip install --upgrade ./clean_docs-1.1.0-py3-none-any.whl
clean-docs migrate
clean-docs migrate --write
```

The migration writes `.clean-docs.yml.v0.bak`. Restore those exact prior bytes with `clean-docs migrate --rollback`. To roll back the executable, reinstall the prior wheel. Remove the package with `python -m pip uninstall clean-docs`; repository manifests and docs remain in place.

Verify a downloaded wheel against its published provenance before installation:

```bash
sha256sum --check SHA256SUMS
gh attestation verify clean_docs-1.0.0-py3-none-any.whl \
  --repo owieschon/clean-docs
```

Each release publishes the wheel, its SPDX 2.3 software bill of materials, checksums, and GitHub artifact attestations. The release gate installs Version 0.5, upgrades to the candidate, rolls the executable back, upgrades again, and uninstalls it.

## Record local outcomes

`verify` runs audit, binding, and projection checks and prints `clean-docs.outcome.v1`. Add immutable refs to include pull-request impact, and write the same bytes to a local receipt with:

```bash
clean-docs verify --base origin/main --head HEAD --out .clean-docs/outcome.json
```

The receipt counts current bindings, caught drift, coverage gaps, active and baselined hygiene findings, and projection state. `bound` means a source-specific binding covers the detected locator. `cataloged` means a repository-wide inventory binding tracks the surface but no source-specific documentation claim covers it. `coverage_complete` permits either form; `direct_coverage_complete` requires source-specific bindings or reasoned ignores for the whole detected surface. The receipt records `network_requests: 0` and sends nothing.

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

Return to the [project overview](../README.md) for the first repository setup, or read the [security model](SECURITY_MODEL.md) before declaring a command or plugin.
