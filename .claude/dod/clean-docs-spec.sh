#!/bin/sh
# DoD: clean-docs final-product specification and versioned build plan.
set -eu

spec="${HOME}/dev/doc-standard/CLEAN_DOCS_SPEC.md"

test -f "$spec"
grep -q '^# clean-docs product specification$' "$spec"
grep -q '^## 4\. Existing foundation$' "$spec"
grep -q '^### Version 0: Proven local foundation, complete$' "$spec"

for version in 0.1 0.2 0.3 0.4 0.5 1.0; do
  grep -q "^### Version ${version}:" "$spec"
done

test "$(grep -c '^#### Functional E2E tests$' "$spec")" -eq 6
test "$(grep -c '^#### Definition of done$' "$spec")" -eq 7

grep -q 'quality-gate.py.*inherited product inputs' "$spec"
grep -q 'Humans and agents consume the same canonical documentation' "$spec"
grep -q 'They do not decide whether CI passes' "$spec"
grep -q 'Any repository.*core can inspect files' "$spec"

! grep -q 'Sourcebound' "$spec"
! grep -q '—' "$spec"
! grep -Eq '(^|[^[:alnum:]-])(load.?bearing|utiliz(e|es|ed|ing)|seamlessly|powerful|simply|leverage)([^[:alnum:]-]|$)' "$spec"
