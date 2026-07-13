#!/bin/sh
# DoD: clean-docs Version 0.3 changed-surface vertical slice.
set -eu

root="${HOME}/dev/doc-standard"
cd "$root"

git show v0.3.0:pyproject.toml | grep -q '^version = "0.3.0"$'
python3 scripts/run_acceptance.py \
  --registry tests/v03-acceptance.yml \
  --out /tmp/clean-docs-v03-acceptance.json >/dev/null
python3 -c 'import json; assert json.load(open("/tmp/clean-docs-v03-acceptance.json"))["ok"]'
PYTHONPATH=src python3 scripts/dogfood_bootstrap_repos.py \
  >/tmp/clean-docs-v03-dogfood.json
python3 - <<'PY'
import json

report = json.load(open("/tmp/clean-docs-v03-dogfood.json"))
assert report["ok"]
for repository in report["repositories"]:
    assert repository["changed_check_median_seconds"] <= repository["changed_check_budget_seconds"]
    assert repository["cached_report_identical"]
PY
python3 -m pytest -q tests/test_doctor_integrations.py
git diff --check
