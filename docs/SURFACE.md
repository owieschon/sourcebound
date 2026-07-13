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
| test-suite | 46 | `scripts/test_release_lifecycle.py`, `tests/test_audit.py`, `tests/test_changed_check.py`, and 43 more |

<!-- clean-docs:inventory-sha256 742b6b2362b1cb304d121e6aab5afc41920572b2939b41d75952e9faa275a637 -->
<!-- clean-docs:end repository-surface -->
