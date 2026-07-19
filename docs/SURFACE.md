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
| api-symbol | 223 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 220 more |
| cli-command | 25 | `audit`, `benchmark`, `binding`, and 22 more |
| cli-option | 67 | `--accept-hygiene-baseline`, `--base`, `--binding`, and 64 more |
| package | 1 | `clean-docs` |
| runtime-constraint | 1 | `Python >=3.10` |
| test-suite | 56 | `scripts/test_release_lifecycle.py`, `tests/test_audit.py`, `tests/test_changed_check.py`, and 53 more |

<!-- clean-docs:inventory-sha256 201b3e7298ab72112b3d287d411c6259d3c4f211fd3b2ea048f5d24ee310536a -->
<!-- clean-docs:end repository-surface -->
