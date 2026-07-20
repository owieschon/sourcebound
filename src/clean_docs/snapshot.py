from __future__ import annotations

import ntpath
import posixpath
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath, PureWindowsPath

from clean_docs.errors import ExtractionError


def _archive_path_is_safe(value: str) -> bool:
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    return not (
        posix_path.is_absolute()
        or windows_path.drive
        or windows_path.root
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    )


def _symlink_target_is_safe(member_name: str, link_name: str) -> bool:
    posix_link = PurePosixPath(link_name)
    windows_link = PureWindowsPath(link_name)
    if (
        posix_link.is_absolute()
        or windows_link.drive
        or windows_link.root
        or ("\\" in link_name and ".." in windows_link.parts)
    ):
        return False

    posix_target = posixpath.normpath(
        (PurePosixPath(member_name).parent / posix_link).as_posix()
    )
    windows_target = ntpath.normpath(
        str(PureWindowsPath(member_name).parent / windows_link)
    )
    return _archive_path_is_safe(posix_target) and _archive_path_is_safe(
        windows_target
    )


def _member_is_safe(member: tarfile.TarInfo) -> bool:
    if not _archive_path_is_safe(member.name) or member.islnk():
        return False
    if not member.issym():
        return True
    return _symlink_target_is_safe(member.name, member.linkname)


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
    def materialized_root(
        self,
        *,
        paths: tuple[Path, ...] = (),
    ) -> Iterator[Path]:
        if self.ref is None:
            yield self.root
            return
        archive_paths: list[str] = []
        for path in paths:
            if path == Path("."):
                continue
            if path.is_absolute() or ".." in path.parts:
                raise ExtractionError(
                    f"snapshot path escapes repository: {path}"
                )
            archive_paths.append(path.as_posix().strip("/"))
        archive_paths = self._include_symlink_targets(archive_paths)
        with tempfile.TemporaryDirectory(prefix="sourcebound-snapshot-") as temporary:
            destination = Path(temporary)
            archive = destination / "snapshot.tar"
            arguments = [
                "archive",
                "--format=tar",
                f"--output={archive}",
                self.label,
            ]
            if archive_paths:
                arguments.extend(("--", *archive_paths))
            self._git(*arguments)
            with tarfile.open(archive) as handle:
                for member in handle.getmembers():
                    if not _member_is_safe(member):
                        raise ExtractionError(f"unsafe path in repository snapshot: {member.name}")
                handle.extractall(destination)
            archive.unlink()
            yield destination

    def _include_symlink_targets(self, paths: list[str]) -> list[str]:
        if not paths:
            return paths
        selected = set(paths)
        pending = list(paths)
        while pending:
            candidate = pending.pop()
            entries = self._git(
                "ls-tree",
                "-r",
                "-z",
                self.label,
                "--",
                candidate,
            ).stdout
            for entry in entries.split("\0"):
                if not entry:
                    continue
                header, separator, name = entry.partition("\t")
                if not separator or not header.startswith("120000 "):
                    continue
                link = self._git(
                    "show",
                    f"{self.label}:{name}",
                ).stdout.rstrip("\n")
                link_path = PurePosixPath(link)
                if link_path.is_absolute():
                    raise ExtractionError(
                        f"selected snapshot contains an absolute symlink: {name}"
                    )
                target = PurePosixPath(
                    posixpath.normpath(
                        (PurePosixPath(name).parent / link_path).as_posix()
                    )
                )
                if target.is_absolute() or ".." in target.parts:
                    raise ExtractionError(
                        f"selected snapshot symlink escapes repository: {name}"
                    )
                target_name = target.as_posix()
                if target_name == ".":
                    raise ExtractionError(
                        "selected snapshot symlink expands scope to "
                        f"repository root: {name}"
                    )
                if any(
                    target_name == selected_path
                    or target_name.startswith(selected_path + "/")
                    for selected_path in selected
                ):
                    continue
                target_entry = self._git(
                    "ls-tree",
                    self.label,
                    "--",
                    target_name,
                ).stdout
                if not target_entry:
                    continue
                selected.add(target_name)
                pending.append(target_name)
        return sorted(selected)

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
