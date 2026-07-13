#!/bin/sh
# DoD: clean-docs Version 0.5 release and extension slice.
set -eu

root="${HOME}/dev/doc-standard"
cd "$root"

grep -q '^version = "0.5.0"$' pyproject.toml
PYTHONPATH=src python3 -m clean_docs --root . project --check >/dev/null
PYTHONPATH=src python3 -m clean_docs --root . eval --format json >/tmp/clean-docs-v05-eval.json
PYTHONPATH=src python3 -m clean_docs --root . release \
  --from v0.4.0 --to HEAD --format json >/tmp/clean-docs-v05-release-a.json
PYTHONPATH=src python3 -m clean_docs --root . release \
  --from v0.4.0 --to HEAD --format json >/tmp/clean-docs-v05-release-b.json
cmp /tmp/clean-docs-v05-release-a.json /tmp/clean-docs-v05-release-b.json
python3 scripts/run_acceptance.py \
  --registry tests/v05-acceptance.yml \
  --out /tmp/clean-docs-v05-acceptance.json >/dev/null
python3 -c 'import json; assert json.load(open("/tmp/clean-docs-v05-acceptance.json"))["ok"]'
grep -q 'clean-docs.plugin-request.v1' docs/EXTENSIONS.md
grep -q 'clean-docs.release-delta.v1' docs/RELEASES.md
git diff --check
