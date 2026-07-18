"""Measure changed-check latency and peak process memory against published budgets."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from clean_docs.changed import CHANGED_CHECK_BUDGET_SECONDS, ChangedReport, check_changed
from clean_docs.errors import ConfigurationError


CHANGED_CHECK_MEMORY_BUDGET_MB = 256.0


@dataclass(frozen=True)
class PerformanceReceipt:
    base: str
    head: str
    project: str
    iterations: int
    p95_seconds: float
    peak_memory_mb: float
    time_budget_seconds: float
    memory_budget_mb: float
    result_sha256: str
    required: int
    gaps: int

    @property
    def ok(self) -> bool:
        return (
            self.p95_seconds <= self.time_budget_seconds
            and self.peak_memory_mb <= self.memory_budget_mb
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "clean-docs.performance.v2",
            "ok": self.ok,
            "base": self.base,
            "head": self.head,
            "project": self.project,
            "iterations": self.iterations,
            "p95_seconds": self.p95_seconds,
            "peak_memory_mb": self.peak_memory_mb,
            "budgets": {
                "p95_seconds": self.time_budget_seconds,
                "peak_memory_mb": self.memory_budget_mb,
            },
            "normalized_result_sha256": self.result_sha256,
            "required": self.required,
            "coverage_gaps": self.gaps,
            "execution": {
                "declared_processes": "may-run-when-required-by-changed-scope",
                "network_isolation": "not-provided",
                "network_observation": "not-instrumented",
            },
        }


def _digest(report: ChangedReport) -> str:
    payload = json.dumps(report.as_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def benchmark_changed_check(
    root: Path,
    manifest_path: Path,
    *,
    base: str,
    head: str,
    project: Path = Path("."),
    iterations: int = 7,
    time_budget_seconds: float = CHANGED_CHECK_BUDGET_SECONDS,
    memory_budget_mb: float = CHANGED_CHECK_MEMORY_BUDGET_MB,
) -> PerformanceReceipt:
    if not 3 <= iterations <= 50:
        raise ConfigurationError("benchmark iterations must be 3..50")
    if time_budget_seconds <= 0 or memory_budget_mb <= 0:
        raise ConfigurationError("benchmark budgets must be positive")
    durations: list[float] = []
    reports: list[ChangedReport] = []
    for _index in range(iterations):
        started = time.perf_counter()
        report = check_changed(
            root,
            manifest_path,
            base=base,
            head=head,
            use_cache=False,
            project=project,
        )
        durations.append(time.perf_counter() - started)
        reports.append(report)
    digests = {_digest(report) for report in reports}
    if len(digests) != 1:
        raise ConfigurationError("benchmark changed-check results varied across iterations")
    ordered = sorted(durations)
    p95 = ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_memory_mb = (
        peak_rss / (1024 * 1024) if sys.platform == "darwin" else peak_rss / 1024
    )
    last = reports[-1]
    return PerformanceReceipt(
        last.base,
        last.head,
        project.as_posix(),
        iterations,
        round(p95, 6),
        round(peak_memory_mb, 3),
        time_budget_seconds,
        memory_budget_mb,
        next(iter(digests)),
        len(last.required),
        len(last.gaps),
    )
