# Detected repository surface

<!-- clean-docs:purpose -->
Use this reference when deciding whether clean-docs directly documents a detected source locator or only tracks it through the repository catalog. It prevents catalog coverage from being mistaken for a source-specific reader claim and gives maintainers the current detected surface behind the coverage receipt.
<!-- clean-docs:end purpose -->

The catalog binding catches additions, removals, and replacements across the detected surface. It does not assert that every symbol or option needs a reader-facing explanation. `clean-docs verify` reports source-specific bindings as `bound` and the remaining catalog entries as `cataloged`.

<!-- clean-docs:begin repository-surface -->
| surface | discovered | examples |
| --- | ---: | --- |
| api-symbol | 175 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 172 more |
| cli-command | 19 | `audit`, `benchmark`, `check`, and 16 more |
| cli-option | 50 | `--accept-hygiene-baseline`, `--base`, `--binding`, and 47 more |
| package | 1 | `clean-docs` |
| runtime-constraint | 1 | `Python >=3.10` |
| test-suite | 47 | `scripts/test_release_lifecycle.py`, `tests/test_audit.py`, `tests/test_changed_check.py`, and 44 more |

<!-- clean-docs:inventory-sha256 61e11d87a96877a70108487792853e5c73e9e755a7d69489890d1bbf39942895 -->
<!-- clean-docs:end repository-surface -->
