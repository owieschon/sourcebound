#!/usr/bin/env python3
"""Prove clean-docs against pinned snapshots of public repositories."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from clean_docs.engine import drive, evaluate


@dataclass(frozen=True)
class DogfoodCase:
    name: str
    url: str
    commit: str
    manifest: str
    document: str
    source: Path
    before: str
    after: str


CASES = (
    DogfoodCase(
        name="ultra-csm",
        url="https://github.com/owieschon/ultra-csm.git",
        commit="d1592058558e82ee8d9ab7073d2cf872f8ad58e3",
        manifest="""\
version: 1
bindings:
  - id: csm-actions
    type: region
    doc: docs/CLEAN_DOCS_DOGFOOD.md
    region: csm-actions
    extractor: python-literal
    source:
      path: src/ultra_csm/governance/csm_actions.py
      symbol: CSM_ACTION_SPECS
    renderer: markdown-table
    columns: [action, autonomy_tier, required_permission, release_condition]
""",
        document="""\
# CSM action registry

This page is generated from the repository's action registry.

<!-- clean-docs:begin csm-actions -->
Not generated yet.
<!-- clean-docs:end csm-actions -->
""",
        source=Path("src/ultra_csm/governance/csm_actions.py"),
        before='autonomy_tier=1,\n        required_permission="csm.recommend"',
        after='autonomy_tier=4,\n        required_permission="csm.recommend"',
    ),
    DogfoodCase(
        name="agent-governance-lab",
        url="https://github.com/owieschon/agent-governance-lab.git",
        commit="207caf4ecd6575f9096777e0e8246e51780f5882",
        manifest="""\
version: 1
bindings:
  - id: comparison-cases
    type: region
    doc: docs/CLEAN_DOCS_DOGFOOD.md
    region: comparison-cases
    extractor: json
    source:
      path: experiment/corpus.json
      pointer: /cases
    renderer: markdown-table
    columns: [id, title, family, expected_label, enforced_mechanism]
""",
        document="""\
# Comparison case registry

This page is generated from the repository's comparison corpus.

<!-- clean-docs:begin comparison-cases -->
Not generated yet.
<!-- clean-docs:end comparison-cases -->
""",
        source=Path("experiment/corpus.json"),
        before='"title": "Unchanged clean candidate"',
        after='"title": "Changed clean candidate"',
    ),
)


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, timeout=60, check=False
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _run_case(case: DogfoodCase, parent: Path) -> dict[str, object]:
    root = parent / case.name
    _git("init", "-q", str(root))
    _git("remote", "add", "origin", case.url, cwd=root)
    _git("fetch", "-q", "--depth", "1", "origin", case.commit, cwd=root)
    _git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=root)
    resolved = _git("rev-parse", "HEAD", cwd=root)
    _require(resolved == case.commit, f"{case.name}: expected {case.commit}, got {resolved}")

    manifest = root / ".clean-docs.yml"
    document = root / "docs/CLEAN_DOCS_DOGFOOD.md"
    manifest.write_text(case.manifest, encoding="utf-8")
    document.write_text(case.document, encoding="utf-8")

    initial = evaluate(root, manifest)
    _require(any(result.changed for result in initial), f"{case.name}: initial drift missing")
    repaired, findings = drive(root, manifest)
    _require(not findings, f"{case.name}: policy rejected baseline repair")
    _require(any(result.changed for result in repaired), f"{case.name}: baseline was not repaired")
    immutable = evaluate(root, manifest, ref=case.commit)
    _require(not any(result.changed for result in immutable), f"{case.name}: ref check drifted")

    source = root / case.source
    source_text = source.read_text(encoding="utf-8")
    _require(source_text.count(case.before) == 1, f"{case.name}: mutation target changed")
    source.write_text(source_text.replace(case.before, case.after), encoding="utf-8")
    changed = evaluate(root, manifest)
    _require(any(result.changed for result in changed), f"{case.name}: source drift was missed")
    repaired_again, findings = drive(root, manifest)
    _require(not findings, f"{case.name}: policy rejected change repair")
    current = evaluate(root, manifest)
    _require(not any(result.changed for result in current), f"{case.name}: repair left drift")

    result = repaired_again[0]
    return {
        "repository": case.name,
        "commit": case.commit,
        "extractor": result.provenance.extractor,
        "source": result.provenance.path,
        "locator": result.provenance.locator,
        "initial_drift_detected": True,
        "baseline_repaired": True,
        "immutable_ref_current": True,
        "source_change_detected": True,
        "source_change_repaired": True,
        "final_check_current": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", choices=[case.name for case in CASES], action="append")
    args = parser.parse_args()
    selected = set(args.repository or [case.name for case in CASES])
    with tempfile.TemporaryDirectory(prefix="clean-docs-dogfood-") as temporary:
        parent = Path(temporary)
        reports = [_run_case(case, parent) for case in CASES if case.name in selected]
    print(json.dumps({"ok": True, "repositories": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
