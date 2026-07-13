#!/bin/sh
# DoD: clean-docs Version 0.2 repository bootstrap release.
set -eu

root="${HOME}/dev/doc-standard"
cd "$root"

sh .claude/dod/clean-docs-v0.1-slice.sh
PYTHONPATH=src python3 -m clean_docs --version | grep -q '^0.2.0$'
python3 scripts/run_acceptance.py \
  --registry tests/v02-acceptance.yml \
  --out /tmp/clean-docs-v02-acceptance.json >/dev/null
python3 -c 'import json; assert json.load(open("/tmp/clean-docs-v02-acceptance.json"))["ok"]'
PYTHONPATH=src python3 scripts/dogfood_bootstrap_repos.py \
  >/tmp/clean-docs-v02-bootstrap-dogfood.json
python3 -c 'import json; assert json.load(open("/tmp/clean-docs-v02-bootstrap-dogfood.json"))["ok"]'
git diff --check
