#!/bin/sh
# DoD: clean-docs Version 0.4 projection and task-evaluation slice.
set -eu

root="${HOME}/dev/doc-standard"
cd "$root"

git show v0.4.0:pyproject.toml | grep -q '^version = "0.4.0"$'
test "$(git rev-parse 'v0.4.0^{}')" = "715b91f01f67d519993f5aa23640867b76178e1a"
PYTHONPATH=src python3 scripts/record_demo.py --out /tmp/clean-docs-demo-evidence.json >/dev/null
cmp .clean-docs/demo/evidence.json /tmp/clean-docs-demo-evidence.json
PYTHONPATH=src python3 -m clean_docs --root . project --check >/dev/null
PYTHONPATH=src python3 -m clean_docs --root . eval --format json >/tmp/clean-docs-v04-eval.json
python3 - <<'PY'
import json

report = json.load(open("/tmp/clean-docs-v04-eval.json"))
assert report["ok"]
assert report["scores"] == {
    "human": {"passed": 1, "attempted": 1},
    "agent": {"passed": 3, "attempted": 3},
}
assert {task["scorer"] for task in report["agent_tasks"]} == {
    "configuration", "structured-output", "cited-limit",
}
assert {task["claim"] for task in report["agent_tasks"]} == {"deterministic-replay"}
PY
python3 scripts/run_acceptance.py \
  --registry tests/v04-acceptance.yml \
  --out /tmp/clean-docs-v04-acceptance.json >/dev/null
python3 -c 'import json; assert json.load(open("/tmp/clean-docs-v04-acceptance.json"))["ok"]'
! grep -q '<script' docs/demo/index.html
! grep -Eq '<(link|img|iframe)[^>]+(src|href)="https?://' docs/demo/index.html
grep -q 'live provider output is model-specific' docs/EVALUATION.md
git diff --check
