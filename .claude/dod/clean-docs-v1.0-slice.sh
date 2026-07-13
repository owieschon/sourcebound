#!/bin/sh
# DoD: clean-docs Version 1.0 supported-product release candidate.
set -eu

root="${HOME}/dev/doc-standard"
cd "$root"

grep -q '^version = "1.0.0a1"$' pyproject.toml
python3 scripts/check_doc_names.py
python3 -m pytest -q
python3 -m mypy src/clean_docs
python3 -m ruff check src tests scripts

for registry in tests/v01-acceptance.yml tests/v02-acceptance.yml \
  tests/v03-acceptance.yml tests/v04-acceptance.yml \
  tests/v05-acceptance.yml tests/v10-acceptance.yml; do
  python3 scripts/run_acceptance.py --registry "$registry" >/dev/null
done

PYTHONPATH=src python3 scripts/benchmark_fixtures.py \
  --out /tmp/clean-docs-performance.json >/dev/null
python3 - <<'PY'
import json

report = json.load(open("/tmp/clean-docs-performance.json"))
assert report["ok"]
assert {case["project"] for case in report["cases"]} == {".", "packages/service"}
assert all(case["network_requests"] == 0 for case in report["cases"])
PY

PYTHONPATH=src python3 -m clean_docs --root . verify \
  --out /tmp/clean-docs-outcome.json >/dev/null
python3 - <<'PY'
import json

receipt = json.load(open("/tmp/clean-docs-outcome.json"))
assert receipt["ok"]
assert receipt["network_requests"] == 0
PY

PYTHONPATH=src python3 -m clean_docs --root . doctor --format json \
  --bundle /tmp/clean-docs-diagnostic.json >/dev/null
PYTHONPATH=src python3 -m clean_docs --root . project --check >/dev/null
PYTHONPATH=src python3 -m clean_docs --root . eval --format json >/dev/null
PYTHONPATH=src python3 scripts/record_demo.py \
  --out /tmp/clean-docs-demo-evidence.json >/dev/null
cmp .clean-docs/demo/evidence.json /tmp/clean-docs-demo-evidence.json
python3 scripts/trusted_self_check.py | grep -q '"ok": true'

python3 scripts/build_release.py --out /tmp/clean-docs-v10-dist >/dev/null
python3 scripts/test_release_lifecycle.py \
  --wheel /tmp/clean-docs-v10-dist/*.whl
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("/tmp/clean-docs-v10-dist")
receipt = json.loads((root / "release.json").read_text())
for field in ("artifact", "sbom"):
    item = receipt[field]
    assert hashlib.sha256((root / item["file"]).read_bytes()).hexdigest() == item["sha256"]
assert receipt["sbom"]["format"] == "SPDX-2.3"
PY

PYTHONPATH=src python3 -m clean_docs --root . audit >/dev/null
git diff --check
