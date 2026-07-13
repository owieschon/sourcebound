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
PYTHONPATH=src python3 -m clean_docs --version | grep -q '^0.2.0a1$'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'derive'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'check'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'drive'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'audit'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'inventory'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'doctor'
PYTHONPATH=src python3 -m clean_docs --help | grep -q 'emit'
PYTHONPATH=src python3 -m clean_docs --root "$root" audit | grep -q '0 finding(s)'
PYTHONPATH=src python3 -m clean_docs --root "$root" doctor | grep -q '^\[ok\] manifest:'
emit_dir=$(mktemp -d)
trap 'rm -rf "$emit_dir"' EXIT
PYTHONPATH=src python3 -m clean_docs --root "$root" emit stepwise-skill --out "$emit_dir" | grep -q 'emit: wrote 5 file(s)'
grep -q '^next_step: null$' "$emit_dir/references/3-verify.md"
PYTHONPATH=src python3 -m clean_docs --root "$emit_dir" audit | grep -q '0 finding(s)'
PYTHONPATH=src python3 -m clean_docs --root "$root" emit llms-txt --out "$emit_dir/llms.txt" >/dev/null
grep -q '^## Source-bound documentation$' "$emit_dir/llms.txt"
PYTHONPATH=src python3 -m clean_docs --root "$root" standard check | grep -q '^\[current\]'
PYTHONPATH=src python3 -m clean_docs --root "$root" check | grep -q '^\[current\] supported-bindings: README.md$'
python3 scripts/trusted_self_check.py | grep -q '"ok": true'
python3 -m pytest -q tests/test_offline_check.py
git diff --check
