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
| api-symbol | 232 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 229 more |
| cli-command | 26 | `audit`, `benchmark`, `binding`, and 23 more |
| cli-option | 71 | `--accept-hygiene-baseline`, `--base`, `--binding`, and 68 more |
| package | 1 | `clean-docs` |
| runtime-constraint | 1 | `Python >=3.10` |
| test-suite | 59 | `scripts/test_readme_quickstart.py`, `scripts/test_release_lifecycle.py`, `tests/test_audit.py`, and 56 more |

<!-- clean-docs:inventory-sha256 e58f6413ac12ba1c2a9e26098bbc035931f502030089a1d32f4985cd3e8a4c43 -->
<!-- clean-docs:end repository-surface -->
