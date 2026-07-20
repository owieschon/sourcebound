#!/usr/bin/env python3
"""Prove Sourcebound against pinned snapshots of public repositories."""

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
    binding_type: str
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
        binding_type="region",
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

<!-- sourcebound:purpose -->
Use this registry when checking which customer-success actions the repository exposes and what each action permits. It gives maintainers a source-bound table that changes when the implementation changes.
<!-- sourcebound:end purpose -->

<!-- sourcebound:begin csm-actions -->
Not generated yet.
<!-- sourcebound:end csm-actions -->
""",
        source=Path("src/ultra_csm/governance/csm_actions.py"),
        before='autonomy_tier=1,\n        required_permission="csm.recommend"',
        after='autonomy_tier=4,\n        required_permission="csm.recommend"',
    ),
    DogfoodCase(
        name="agent-governance-lab",
        url="https://github.com/owieschon/agent-governance-lab.git",
        commit="207caf4ecd6575f9096777e0e8246e51780f5882",
        binding_type="symbol",
        manifest="""\
version: 1
bindings:
  - id: comparison-policy-symbol
    type: symbol
    doc: docs/CLEAN_DOCS_DOGFOOD.md
    anchor: policy-registry
    source:
      path: rails/agl/comparison.py
      symbol: POLICY_IDS
""",
        document="""\
# Comparison policy registry

<!-- sourcebound:purpose -->
Use this registry when checking where comparison policy identifiers are defined. It gives maintainers one source symbol whose removal must fail the documentation gate.
<!-- sourcebound:end purpose -->

## Policy registry

The public policy identifiers are defined by `POLICY_IDS` in `rails/agl/comparison.py`.
""",
        source=Path("rails/agl/comparison.py"),
        before='POLICY_IDS = ("L0", "L1", "SHAM", "L3")',
        after='RENAMED_POLICY_IDS = ("L0", "L1", "SHAM", "L3")',
    ),
)


def run_git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, timeout=60, check=False
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _run_case(case: DogfoodCase, parent: Path) -> dict[str, object]:
    root = parent / case.name
    run_git("init", "-q", str(root))
    run_git("remote", "add", "origin", case.url, cwd=root)
    run_git("fetch", "-q", "--depth", "1", "origin", case.commit, cwd=root)
    run_git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=root)
    resolved = run_git("rev-parse", "HEAD", cwd=root)
    require(resolved == case.commit, f"{case.name}: expected {case.commit}, got {resolved}")

    manifest = root / ".sourcebound.yml"
    document = root / "docs/CLEAN_DOCS_DOGFOOD.md"
    manifest.write_text(case.manifest, encoding="utf-8")
    document.write_text(case.document, encoding="utf-8")

    initial = evaluate(root, manifest)
    if case.binding_type == "region":
        require(any(result.changed for result in initial), f"{case.name}: initial drift missing")
        repaired, findings = drive(root, manifest)
        require(not findings, f"{case.name}: policy rejected baseline repair")
        require(
            any(result.changed for result in repaired),
            f"{case.name}: baseline was not repaired",
        )
        baseline_state = "repaired"
    else:
        require(not any(result.changed for result in initial), f"{case.name}: baseline drifted")
        baseline_state = "current"
    immutable = evaluate(root, manifest, ref=case.commit)
    require(not any(result.changed for result in immutable), f"{case.name}: ref check drifted")

    source = root / case.source
    source_text = source.read_text(encoding="utf-8")
    require(source_text.count(case.before) == 1, f"{case.name}: mutation target changed")
    source.write_text(source_text.replace(case.before, case.after), encoding="utf-8")
    changed = evaluate(root, manifest)
    require(any(result.changed for result in changed), f"{case.name}: source drift was missed")
    if case.binding_type == "region":
        repaired_again, findings = drive(root, manifest)
        require(not findings, f"{case.name}: policy rejected change repair")
        recovery = "documentation-derived"
    else:
        source.write_text(source_text, encoding="utf-8")
        repaired_again = evaluate(root, manifest)
        recovery = "source-restored"
    current = evaluate(root, manifest)
    require(not any(result.changed for result in current), f"{case.name}: repair left drift")

    result = repaired_again[0]
    return {
        "repository": case.name,
        "commit": case.commit,
        "binding_type": result.binding_type,
        "extractor": result.provenance.extractor,
        "source": result.provenance.path,
        "locator": result.provenance.locator,
        "baseline_state": baseline_state,
        "immutable_ref_current": True,
        "source_change_detected": True,
        "recovery": recovery,
        "final_check_current": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", choices=[case.name for case in CASES], action="append")
    args = parser.parse_args()
    selected = set(args.repository or [case.name for case in CASES])
    with tempfile.TemporaryDirectory(prefix="sourcebound-dogfood-") as temporary:
        parent = Path(temporary)
        reports = [_run_case(case, parent) for case in CASES if case.name in selected]
    print(json.dumps({"ok": True, "repositories": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
