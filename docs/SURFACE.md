# Detected repository surface

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
This generated catalog shows which detected source locators have direct bindings and which remain
catalog-only. Maintainers can inspect the surface behind a coverage receipt without mistaking
change visibility for a validated reader-facing claim.
<!-- sourcebound:end purpose -->

**[Inspect the generated surface](#detected-repository-surface)**.

Run `sourcebound inventory --format json` to reproduce the item-level coverage state behind this
summary.

The catalog binding catches additions, removals, and replacements across the detected surface. It does not assert that every symbol or option needs a reader-facing explanation. `sourcebound verify` reports source-specific bindings as `bound` and the remaining catalog entries as `cataloged`.

<!-- sourcebound:begin repository-surface -->
| surface | discovered | examples |
| --- | ---: | --- |
| api-symbol | 315 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 312 more |
| cli-command | 44 | `audit`, `benchmark`, `binding`, and 41 more |
| cli-option | 92 | `--accept-hygiene-baseline`, `--attempts`, `--base`, and 89 more |
| package | 2 | `sourcebound`, `sourcebound-mdx-parser-build` |
| package-script | 1 | `build` |
| runtime-constraint | 3 | `ES modules`, `Python >=3.10`, `node >=20` |
| test-suite | 78 | `scripts/test_readme_quickstart.py`, `scripts/test_release_lifecycle.py`, `tests/contracts/test_core_clarity_contract.py`, and 75 more |

<!-- sourcebound:inventory-sha256 354ea6d038b9ddf662580139962d91cbe1b33eab5cdc9644941324dc3875e9df -->
<!-- sourcebound:end repository-surface -->
