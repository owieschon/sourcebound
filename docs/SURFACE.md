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
| api-symbol | 292 | `AcceptanceCase`, `Assertion`, `AuditFinding`, and 289 more |
| cli-command | 42 | `audit`, `benchmark`, `binding`, and 39 more |
| cli-option | 86 | `--accept-hygiene-baseline`, `--base`, `--binding`, and 83 more |
| package | 2 | `clean-docs`, `clean-docs-mdx-parser-build` |
| package-script | 1 | `build` |
| runtime-constraint | 3 | `ES modules`, `Python >=3.10`, `node >=20` |
| test-suite | 66 | `scripts/test_readme_quickstart.py`, `scripts/test_release_lifecycle.py`, `tests/test_accessibility.py`, and 63 more |

<!-- clean-docs:inventory-sha256 94e3f91e2d88f031bf6d0e19a225ce1ea6309d93089de8c9bef82825d8c0108e -->
<!-- clean-docs:end repository-surface -->
