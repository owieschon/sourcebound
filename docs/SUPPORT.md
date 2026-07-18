# Support and lifecycle

<!-- clean-docs:policy register-v2 -->
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

`init` is strict by default. It rolls back every bootstrap write when the current corpus has a hygiene finding. It also stops before writing when a page has no substantive authored opening that can be marked as its purpose contract. Metadata, status labels, feature fragments, and generated title boilerplate do not satisfy that boundary. A mature repository can preserve strict future checks while recording its current debt:

```bash
clean-docs init --no-model --accept-hygiene-baseline
git diff -- .clean-docs/audit-baseline.json
clean-docs audit
```

The committed baseline records each exact rule, path, line, detail, and fingerprint, including unresolved purpose-contract findings. Adoption mode does not archive or move existing documents. Ambiguous names such as `DEPLOYMENT_PLAN.md` and `ARCHITECTURE_NOTES.md` remain active documentation; only unambiguous process artifacts and exact duplicates are archive candidates outside adoption mode. Files named `*.fixture.md` are explicit test inputs rather than reader documentation. Hidden configuration trees are outside the documentation corpus. `audit` fails when a new finding appears. It also fails with `stale-baseline` when a recorded finding is resolved, because the baseline must shrink to match current debt.

The JSON content plan emits at most 100 representative facts and 4,000 bytes of diff per operation. `fact_count`, `facts_omitted`, `diff_truncated`, the full-plan digest, and the proposed `canonical_documents` preserve the review boundary without printing a repository-sized response. `llms.txt` indexes those declared canonical documents and distinguishes pages with bindings from declared context.

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

Create an isolated environment in a directory containing exactly one clean-docs wheel. A release
bundle also contains a `wheelhouse` directory with supported runtime dependencies, so this procedure
does not contact a package index:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --no-index --find-links ./wheelhouse ./clean_docs-*.whl
clean-docs --version
```

The version output must match the wheel filename. The clean-docs wheel declares PyYAML as a runtime
dependency. A general release download does not bundle dependencies; create `wheelhouse`, place a
compatible PyYAML wheel inside it, and use the same command. For an online installation, omit
`--no-index --find-links ./wheelhouse` and let `pip` use the configured package index.

Upgrade by installing the newer wheel and preview any requested schema migration before writing:

```bash
python -m pip install --upgrade ./clean_docs-*.whl
clean-docs migrate
clean-docs migrate --write
```

The migration writes `.clean-docs.yml.v0.bak`. Restore those exact prior bytes with `clean-docs migrate --rollback`. To roll back the executable, reinstall the prior wheel. Remove the package with `python -m pip uninstall clean-docs`; repository manifests and docs remain in place.

### Verify release artifacts

Verify the one downloaded wheel against its published checksum without requiring every release asset to be present:

```bash
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path

wheels = list(Path(".").glob("clean_docs-*.whl"))
if len(wheels) != 1:
    raise SystemExit(f"expected one wheel, found {len(wheels)}")
expected = {
    filename: digest
    for digest, filename in (
        line.split(maxsplit=1) for line in Path("SHA256SUMS").read_text().splitlines()
    )
}
actual = sha256(wheels[0].read_bytes()).hexdigest()
if expected.get(wheels[0].name) != actual:
    raise SystemExit("wheel checksum mismatch")
print(f"{wheels[0].name}: {actual}")
PY
gh attestation verify ./clean_docs-*.whl \
  --repo owieschon/clean-docs
```

The checksum step is local. The attestation step needs GitHub access and can be completed outside a network-blocked execution environment. Each release publishes the wheel, its SPDX 2.3 software bill of materials, checksums, and GitHub artifact attestations. The release gate installs Version 0.5, upgrades to the candidate, rolls the executable back, upgrades again, and uninstalls it.

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
