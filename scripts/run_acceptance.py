#!/usr/bin/env python3
"""Run a named release acceptance registry and write one JSON receipt."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "tests/v01-acceptance.yml"
EXPECTED_IDS = {
    "ultra-csm-capability-drift",
    "command-claim",
    "symbol-removal",
    "unrelated-prose-preservation",
    "ref-purity",
    "ci-behavior",
    "version-zero-policy-parity",
    "known-false-positive-regressions",
    "self-hosting-checker-tampering",
}
EXPECTED_IDS_BY_RELEASE = {
    "0.1": EXPECTED_IDS,
    "0.2": {
        "unfamiliar-python-repository-baseline",
        "standard-once-bootstrap",
        "model-boundary",
        "no-model-completeness",
        "idempotent-rerun",
        "multi-language-fixture",
        "hostile-phrasing-context",
    },
    "0.3": {
        "bound-change-blocks-merge",
        "new-public-surface-is-flagged",
        "private-refactor-stays-quiet",
        "declared-ignore-remains-explicit",
        "cache-correctness",
        "monorepo-isolation",
    },
    "0.4": {
        "single-source-projection",
        "stale-projection-gate",
        "human-quickstart-task",
        "agent-configuration-round-trip",
        "limitation-retrieval",
        "recorded-replay",
        "stepwise-skill-projection",
        "static-demonstration",
    },
    "0.5": {
        "factual-release-delta",
        "phrasing-cannot-alter-facts",
        "third-party-extractor",
        "incompatible-plugin",
        "schema-migration",
        "cross-ref-isolation",
    },
    "1.0": {
        "empty-to-protected-repository",
        "full-change-lifecycle",
        "offline-deterministic-operation",
        "malicious-repository",
        "upgrade-compatibility",
        "independent-reader-success",
    },
    "1.1": {
        "public-repository-legibility",
        "tutorial-from-a-clean-room",
        "postmortem-facts-cannot-drift",
        "deterministic-seam-boundary",
        "additive-learning-corpus",
        "fresh-reader-learning-path",
    },
    "1.2A": {
        "coverage-complete-no-impact",
        "implementation-is-not-interface",
        "typescript-interface-fingerprint",
        "line-move-not-public-impact",
        "unknown-cannot-become-no-impact",
        "public-default-obligations",
        "affected-contract-traversal",
        "generated-output-non-recursion",
        "merge-base-history",
        "scope-tension",
        "legacy-overview-compatibility",
        "cross-runtime-receipt-portability",
        "bounded-context-authority",
        "required-context-overflow",
        "provider-failure-receipt",
        "provider-deadline-receipt",
        "provider-write-conflict",
        "effective-mapping-key-semantics",
        "bounded-candidate-ranking",
        "independent-fact-sensitivity",
        "wrong-fact-red-boundary",
        "ambiguous-mutation-unsupported",
        "shared-evaluation-primitive",
        "stable-coverage-verdict",
        "unsupported-change-unknown",
        "bound-drift-not-ready",
        "affected-execution-unknown",
        "legacy-prose-nonclaim",
        "mutation-receipt-pin",
        "json-sarif-finding-parity",
        "verdict-input-state",
        "machine-readable-extraction-failure",
    },
}


@dataclass(frozen=True)
class AcceptanceCase:
    id: str
    test: str


def load_registry(path: Path) -> tuple[str, tuple[AcceptanceCase, ...]]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"version", "release", "scenarios"}:
        raise ValueError("acceptance registry must contain version, release, and scenarios")
    release = raw["release"]
    if (
        raw["version"] != 1
        or not isinstance(release, str)
        or release not in EXPECTED_IDS_BY_RELEASE
    ):
        raise ValueError("acceptance registry names an unsupported release or schema version")
    scenarios = raw["scenarios"]
    if not isinstance(scenarios, list):
        raise ValueError("acceptance scenarios must be a list")
    cases = []
    for index, item in enumerate(scenarios):
        if not isinstance(item, dict) or set(item) != {"id", "test"}:
            raise ValueError(f"acceptance scenario {index} must contain id and test")
        identifier = item["id"]
        node = item["test"]
        if not isinstance(identifier, str) or not isinstance(node, str):
            raise ValueError(f"acceptance scenario {index} fields must be strings")
        if not node.startswith("tests/") or "::" not in node:
            raise ValueError(f"acceptance scenario {identifier} has an invalid pytest node")
        if not (ROOT / node.split("::", 1)[0]).is_file():
            raise ValueError(f"acceptance scenario {identifier} names a missing test file")
        cases.append(AcceptanceCase(identifier, node))
    expected = EXPECTED_IDS_BY_RELEASE[release]
    if {case.id for case in cases} != expected or len(cases) != len(expected):
        raise ValueError(f"acceptance registry must name each Version {release} scenario exactly once")
    return release, tuple(cases)


def load_cases(path: Path) -> tuple[AcceptanceCase, ...]:
    return load_registry(path)[1]


def run_cases(
    cases: tuple[AcceptanceCase, ...], release: str = "0.1"
) -> dict[str, object]:
    results = []
    for case in cases:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", case.test],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        results.append({
            "id": case.id,
            "test": case.test,
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })
    return {
        "schema": "clean-docs.acceptance.v1",
        "release": release,
        "ok": all(result["ok"] for result in results),
        "scenarios": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        release, cases = load_registry(args.registry.resolve())
        receipt = run_cases(cases, release)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"acceptance: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
