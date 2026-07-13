from __future__ import annotations

import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from fnmatch import fnmatch
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from collections.abc import Iterator

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

    def matching_files(self, pattern: str) -> list[Path]:
        candidate = Path(pattern)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ExtractionError(f"source glob escapes repository: {pattern}")
        if self.ref is None:
            return sorted(
                path.relative_to(self.root)
                for path in self.root.glob(pattern)
                if path.is_file() and self.root in path.resolve().parents
            )
        proc = self._git("ls-tree", "-r", "--name-only", self.ref)
        return [Path(path) for path in proc.stdout.splitlines() if fnmatch(path, pattern)]

    @contextmanager
    def materialized_root(self) -> Iterator[Path]:
        if self.ref is None:
            yield self.root
            return
        with tempfile.TemporaryDirectory(prefix="clean-docs-snapshot-") as temporary:
            destination = Path(temporary)
            archive = destination / "snapshot.tar"
            self._git(
                "archive",
                "--format=tar",
                f"--output={archive}",
                self.label,
            )
            with tarfile.open(archive) as handle:
                for member in handle.getmembers():
                    path = PurePosixPath(member.name)
                    if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                        raise ExtractionError(f"unsafe path in repository snapshot: {member.name}")
                handle.extractall(destination)
            archive.unlink()
            yield destination

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
