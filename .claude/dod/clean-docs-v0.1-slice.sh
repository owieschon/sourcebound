#!/bin/sh
# DoD: clean-docs Version 0.1 deterministic region-binding vertical slice.
set -eu

root="${HOME}/dev/doc-standard"
cd "$root"

test -f LICENSE
test -f SECURITY.md
test -f .github/workflows/ci.yml
python3 scripts/check_doc_names.py
python3 -m pytest -q
PYTHONPATH=src python3 -m clean_docs --version | grep -q '^0.1.0a1$'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'derive'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'check'
PYTHONPATH=src python3 -m clean_docs --root "$root" check | grep -q '^\[current\] supported-bindings: README.md$'

! rg -n 'requests|httpx|urllib|openai|anthropic' src/clean_docs tests
git diff --check
