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
| api-symbol | 303 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 300 more |
| cli-command | 42 | `audit`, `benchmark`, `binding`, and 39 more |
| cli-option | 89 | `--accept-hygiene-baseline`, `--base`, `--binding`, and 86 more |
| package | 2 | `sourcebound`, `sourcebound-mdx-parser-build` |
| package-script | 1 | `build` |
| runtime-constraint | 3 | `ES modules`, `Python >=3.10`, `node >=20` |
| test-suite | 69 | `scripts/test_readme_quickstart.py`, `scripts/test_release_lifecycle.py`, `tests/test_accessibility.py`, and 66 more |

<!-- sourcebound:inventory-sha256 a27a6653ac94fa5a3c30a52f8e54f9c0454e333e5a2793fc7401610877393eef -->
<!-- sourcebound:end repository-surface -->
