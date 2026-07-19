# Detected repository surface

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
This generated catalog shows which detected source locators have direct bindings and which remain
catalog-only. Maintainers can inspect the surface behind a coverage receipt without mistaking
change visibility for a validated reader-facing claim.
<!-- clean-docs:end purpose -->

**[Inspect the generated surface](#detected-repository-surface)**.

Run `clean-docs inventory --format json` to reproduce the item-level coverage state behind this
summary.

The catalog binding catches additions, removals, and replacements across the detected surface. It does not assert that every symbol or option needs a reader-facing explanation. `clean-docs verify` reports source-specific bindings as `bound` and the remaining catalog entries as `cataloged`.

<!-- clean-docs:begin repository-surface -->
| surface | discovered | examples |
| --- | ---: | --- |
| api-symbol | 258 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 255 more |
| cli-command | 37 | `audit`, `benchmark`, `binding`, and 34 more |
| cli-option | 79 | `--accept-hygiene-baseline`, `--base`, `--binding`, and 76 more |
| package | 2 | `clean-docs`, `clean-docs-mdx-parser-build` |
| package-script | 1 | `build` |
| runtime-constraint | 3 | `ES modules`, `Python >=3.10`, `node >=20` |
| test-suite | 62 | `scripts/test_readme_quickstart.py`, `scripts/test_release_lifecycle.py`, `tests/test_audit.py`, and 59 more |

<!-- clean-docs:inventory-sha256 6dd8fa7a154ffbbcc6eddd3cd4f9273f51a8b9276c4ed39a112a492476b70fcb -->
<!-- clean-docs:end repository-surface -->
