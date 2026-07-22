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
| api-symbol | 314 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 311 more |
| cli-command | 43 | `audit`, `benchmark`, `binding`, and 40 more |
| cli-option | 91 | `--accept-hygiene-baseline`, `--attempts`, `--base`, and 88 more |
| package | 2 | `sourcebound`, `sourcebound-mdx-parser-build` |
| package-script | 1 | `build` |
| runtime-constraint | 3 | `ES modules`, `Python >=3.10`, `node >=20` |
| test-suite | 75 | `scripts/test_readme_quickstart.py`, `scripts/test_release_lifecycle.py`, `tests/contracts/test_core_clarity_contract.py`, and 72 more |

<!-- sourcebound:inventory-sha256 c36b61805770ac9c3d2b061d392e22a8fcd95c8dc49a9441c50ac5ddcb344efe -->
<!-- sourcebound:end repository-surface -->
