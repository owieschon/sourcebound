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
| api-symbol | 202 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 199 more |
| cli-command | 21 | `audit`, `benchmark`, `check`, and 18 more |
| cli-option | 56 | `--accept-hygiene-baseline`, `--base`, `--binding`, and 53 more |
| package | 1 | `clean-docs` |
| runtime-constraint | 1 | `Python >=3.10` |
| test-suite | 53 | `scripts/test_release_lifecycle.py`, `tests/test_audit.py`, `tests/test_changed_check.py`, and 50 more |

<!-- clean-docs:inventory-sha256 5062f9c9023f67876a593cfb2e9ddace997627d1d18de5011beedfa0343019fa -->
<!-- clean-docs:end repository-surface -->
