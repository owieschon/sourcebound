"""Run declared processes in disposable repository copies with bounded I/O."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from clean_docs.errors import ExtractionError
from clean_docs.snapshot import RepositorySnapshot
from clean_docs.write_gate import redact_secrets


MAX_PROCESS_IO_BYTES = 1_000_000
COPY_IGNORES = (".git", ".venv", "node_modules", "__pycache__")


@dataclass(frozen=True)
class IsolatedProcessResult:
    returncode: int
    stdout: str
    stderr: str


def _isolated_copy(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        symlinks=True,
        ignore=shutil.ignore_patterns(*COPY_IGNORES),
    )
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise ExtractionError(
                "process snapshot contains a symbolic link: "
                f"{path.relative_to(destination)}"
            )


def _safe_output(label: str, stdout: bytes, stderr: bytes) -> IsolatedProcessResult:
    rendered_stdout = stdout.decode("utf-8", errors="replace")
    rendered_stderr = stderr.decode("utf-8", errors="replace")
    _, stdout_flags = redact_secrets(rendered_stdout)
    _, stderr_flags = redact_secrets(rendered_stderr)
    flags = (*stdout_flags, *stderr_flags)
    if flags:
        raise ExtractionError(
            f"{label} output contains secret-like data ({flags[0]})"
        )
    return IsolatedProcessResult(0, rendered_stdout, rendered_stderr)


def run_isolated_process(
    snapshot: RepositorySnapshot,
    argv: tuple[str, ...],
    *,
    label: str,
    timeout_seconds: int,
    input_text: str = "",
) -> IsolatedProcessResult:
    request = input_text.encode("utf-8")
    if len(request) > MAX_PROCESS_IO_BYTES:
        raise ExtractionError(
            f"{label} input exceeds {MAX_PROCESS_IO_BYTES} bytes"
        )
    with snapshot.materialized_root() as source, tempfile.TemporaryDirectory(
        prefix="clean-docs-process-"
    ) as temporary:
        sandbox = Path(temporary)
        worktree = sandbox / "repository"
        _isolated_copy(source, worktree)
        home = sandbox / "home"
        temp = sandbox / "tmp"
        home.mkdir()
        temp.mkdir()
        environment = {
            "HOME": str(home),
            "TMPDIR": str(temp),
            "PATH": os.environ.get("PATH", ""),
            "NO_COLOR": "1",
        }
        try:
            process = subprocess.Popen(
                argv,
                cwd=worktree,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise ExtractionError(f"{label} failed to run: {exc}") from exc

        stdout = bytearray()
        stderr = bytearray()
        total = 0
        lock = threading.Lock()
        exceeded = threading.Event()

        def drain(stream: object, destination: bytearray) -> None:
            nonlocal total
            reader = stream
            while True:
                chunk = reader.read(64 * 1024)  # type: ignore[attr-defined]
                if not chunk:
                    return
                with lock:
                    total += len(chunk)
                    if total > MAX_PROCESS_IO_BYTES:
                        exceeded.set()
                        process.kill()
                        return
                    destination.extend(chunk)

        assert process.stdout is not None
        assert process.stderr is not None
        readers = (
            threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
        )
        for reader in readers:
            reader.start()
        try:
            assert process.stdin is not None
            process.stdin.write(request)
            process.stdin.close()
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise ExtractionError(
                f"{label} timed out after {timeout_seconds} seconds"
            ) from exc
        except OSError as exc:
            process.kill()
            process.wait()
            raise ExtractionError(f"{label} failed during execution: {exc}") from exc
        finally:
            for reader in readers:
                reader.join(timeout=5)
        if exceeded.is_set():
            raise ExtractionError(
                f"{label} output exceeds {MAX_PROCESS_IO_BYTES} bytes"
            )
        result = _safe_output(label, bytes(stdout), bytes(stderr))
        return IsolatedProcessResult(process.returncode, result.stdout, result.stderr)
