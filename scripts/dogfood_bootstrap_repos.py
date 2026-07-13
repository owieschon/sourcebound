#!/usr/bin/env python3
"""Prove repository bootstrap on pinned Python and TypeScript projects."""

from __future__ import annotations

import json
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from clean_docs.audit import audit
from clean_docs.bootstrap import apply_bootstrap_plan, build_bootstrap_plan
from clean_docs.changed import CHANGED_CHECK_BUDGET_SECONDS, check_changed
from clean_docs.engine import evaluate
from clean_docs.inventory import scan_inventory
from clean_docs.manifest import load_manifest
from clean_docs.models import RegionBinding

if __package__:
    from scripts.dogfood_public_repos import require, run_git
else:
    from dogfood_public_repos import require, run_git


@dataclass(frozen=True)
class BootstrapDogfoodCase:
    name: str
    url: str
    commit: str
    language: str
    evidence_adapter: str
    readme: str
    mutation_path: str
    mutation: str


CASES = (
    BootstrapDogfoodCase(
        name="sampleproject",
        url="https://github.com/pypa/sampleproject.git",
        commit="621e4974ca25ce531773def586ba3ed8e736b3fc",
        language="Python",
        evidence_adapter="python-package",
        readme="README.md",
        mutation_path="src/sample/simple.py",
        mutation="\n\ndef clean_docs_dogfood():\n    return True\n",
    ),
    BootstrapDogfoodCase(
        name="yocto-queue",
        url="https://github.com/sindresorhus/yocto-queue.git",
        commit="b07eac099753833b29d06c614149904445739776",
        language="TypeScript",
        evidence_adapter="typescript-static",
        readme="readme.md",
        mutation_path="index.d.ts",
        mutation="\nexport interface CleanDocsDogfood {}\n",
    ),
)


def _run_case(case: BootstrapDogfoodCase, parent: Path) -> dict[str, object]:
    root = parent / case.name
    run_git("init", "-q", str(root))
    run_git("remote", "add", "origin", case.url, cwd=root)
    run_git("fetch", "-q", "--depth", "1", "origin", case.commit, cwd=root)
    run_git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=root)
    require(run_git("rev-parse", "HEAD", cwd=root) == case.commit, f"{case.name}: ref drift")

    inventory = scan_inventory(root)
    require(case.language in inventory.languages, f"{case.name}: language was not detected")
    require(
        any(item.adapter == case.evidence_adapter for item in inventory.items),
        f"{case.name}: {case.evidence_adapter} produced no evidence",
    )
    plan = build_bootstrap_plan(root)
    require(not plan.gaps, f"{case.name}: bootstrap reported gaps")
    require(plan.model is None, f"{case.name}: bootstrap called a model")
    require(plan.facts, f"{case.name}: bootstrap produced no grounded facts")
    apply_bootstrap_plan(root, plan)

    manifest = load_manifest(root / ".clean-docs.yml")
    binding = manifest.bindings[0]
    require(isinstance(binding, RegionBinding), f"{case.name}: baseline binding is not a region")
    require(binding.doc.as_posix() == case.readme, f"{case.name}: README path changed")
    require(not any(result.changed for result in evaluate(root, manifest.path)), f"{case.name}: check drifted")
    require(not audit(root).findings, f"{case.name}: generated baseline failed audit")

    rerun = build_bootstrap_plan(root)
    require(not rerun.writes and not rerun.moves, f"{case.name}: rerun was not idempotent")
    require(
        {(fact.id, fact.digest) for fact in rerun.facts}
        == {(fact.id, fact.digest) for fact in plan.facts},
        f"{case.name}: evidence changed after bootstrap",
    )
    run_git("add", "-A", cwd=root)
    run_git(
        "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
        "commit", "-qm", "clean-docs baseline", cwd=root,
    )
    base = run_git("rev-parse", "HEAD", cwd=root)
    mutation_path = root / case.mutation_path
    mutation_path.write_text(mutation_path.read_text(encoding="utf-8") + case.mutation)
    run_git("add", case.mutation_path, cwd=root)
    run_git(
        "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
        "commit", "-qm", "public surface change", cwd=root,
    )
    head = run_git("rev-parse", "HEAD", cwd=root)
    durations = []
    normalized = None
    for _index in range(3):
        started = time.perf_counter()
        changed = check_changed(root, manifest.path, base=base, head=head, use_cache=False)
        durations.append(time.perf_counter() - started)
        require(changed.required, f"{case.name}: changed binding did not fail")
        require(not changed.gaps, f"{case.name}: bound surface became a coverage gap")
        if normalized is None:
            normalized = changed.as_dict()
        else:
            require(changed.as_dict() == normalized, f"{case.name}: changed report varied")
    cached_first = check_changed(root, manifest.path, base=base, head=head)
    cached_second = check_changed(root, manifest.path, base=base, head=head)
    require(cached_first.as_dict() == normalized, f"{case.name}: cached report varied")
    require(cached_second.as_dict() == normalized, f"{case.name}: cache hit report varied")
    require(cached_second.cache_hits == 2, f"{case.name}: immutable refs missed cache")
    median_seconds = statistics.median(durations)
    require(
        median_seconds <= CHANGED_CHECK_BUDGET_SECONDS,
        f"{case.name}: changed check exceeded {CHANGED_CHECK_BUDGET_SECONDS}s budget",
    )
    return {
        "repository": case.name,
        "commit": case.commit,
        "language": case.language,
        "readme": case.readme,
        "facts": len(plan.facts),
        "content_plan_sha256": plan.digest,
        "operations": len(plan.writes) + len(plan.moves),
        "model_calls": 0,
        "check_current": True,
        "audit_clean": True,
        "idempotent": True,
        "changed_check_median_seconds": round(median_seconds, 6),
        "changed_check_budget_seconds": CHANGED_CHECK_BUDGET_SECONDS,
        "cached_report_identical": True,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="clean-docs-bootstrap-dogfood-") as temporary:
        parent = Path(temporary)
        reports = [_run_case(case, parent) for case in CASES]
    print(json.dumps({"ok": True, "repositories": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
