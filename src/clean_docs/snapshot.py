from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from clean_docs.errors import ExtractionError


@dataclass(frozen=True)
class RepositorySnapshot:
    root: Path
    ref: str | None = None

    @property
    def label(self) -> str:
        if self.ref is None:
            return "WORKTREE"
        proc = self._git("rev-parse", "--verify", f"{self.ref}^{{commit}}")
        return proc.stdout.strip()

    def read_text(self, path: Path) -> str:
        if path.is_absolute() or ".." in path.parts:
            raise ExtractionError(f"source path escapes repository: {path}")
        if self.ref is None:
            target = self.root / path
            try:
                return target.read_text(encoding="utf-8")
            except OSError as exc:
                raise ExtractionError(f"cannot read source {path}: {exc}") from exc
        proc = self._git("show", f"{self.ref}:{path.as_posix()}")
        return proc.stdout

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.root), *args],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExtractionError(f"git {' '.join(args)} failed: {exc}") from exc
        if proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip() or "unknown git error"
            raise ExtractionError(f"git {' '.join(args)} failed: {message}")
        return proc
