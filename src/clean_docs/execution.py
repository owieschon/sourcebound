"""Resolve explicit runtime tokens in allowlisted command arrays."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from clean_docs.errors import ConfigurationError


PYTHON_EXECUTABLE_TOKEN = "{python}"


class ExecutionPolicy(str, Enum):
    TRUSTED = "trusted"
    STATIC_ONLY = "static-only"


def resolve_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    if argv and argv[0] == PYTHON_EXECUTABLE_TOKEN:
        return (sys.executable, *argv[1:])
    return argv


@dataclass(frozen=True)
class BoundedCommandResult:
    stdout: bytes
    stderr: bytes
    duration_seconds: float


def run_bounded_command(
    argv: tuple[str, ...],
    *,
    environment: dict[str, str],
    input_bytes: bytes,
    timeout_seconds: int,
    max_input_bytes: int,
    max_output_bytes: int,
    prefix: str,
) -> BoundedCommandResult:
    """Run an operator-selected command in a disposable directory with bounded I/O."""
    if len(input_bytes) > max_input_bytes:
        raise ConfigurationError(f"{prefix} input exceeds {max_input_bytes} bytes")
    with tempfile.TemporaryDirectory(prefix=f"{prefix}-") as temporary:
        start = time.monotonic()
        try:
            process = subprocess.Popen(
                resolve_argv(argv),
                cwd=Path(temporary),
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            raise ConfigurationError(f"{prefix} failed to start: {exc}") from exc
        stdout = bytearray()
        stderr = bytearray()
        total = 0
        lock = threading.Lock()
        exceeded = threading.Event()

        def stop_process() -> None:
            if process.poll() is not None:
                return
            try:
                # The configured command can start children. Killing its process group
                # keeps an inherited pipe from outliving the deadline and temp directory.
                os.killpg(process.pid, signal.SIGKILL)
            except (AttributeError, OSError):
                process.kill()

        def drain(stream: object, destination: bytearray) -> None:
            nonlocal total
            while True:
                chunk = stream.read(64 * 1024)  # type: ignore[attr-defined]
                if not chunk:
                    return
                with lock:
                    total += len(chunk)
                    if total > max_output_bytes:
                        exceeded.set()
                        stop_process()
                        return
                    destination.extend(chunk)

        def supply_input() -> None:
            try:
                assert process.stdin is not None
                process.stdin.write(input_bytes)
                process.stdin.close()
            except (BrokenPipeError, OSError):
                # A nonzero exit is reported from the process status below. The writer
                # must not hide that status or block the timeout path.
                return

        assert process.stdin is not None and process.stdout is not None and process.stderr is not None
        readers = (
            threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
        )
        for reader in readers:
            reader.start()
        writer = threading.Thread(target=supply_input, daemon=True)
        writer.start()
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            stop_process()
            process.wait()
            raise ConfigurationError(f"{prefix} timed out after {timeout_seconds} seconds") from exc
        except OSError as exc:
            stop_process()
            process.wait()
            raise ConfigurationError(f"{prefix} failed during execution: {exc}") from exc
        finally:
            writer.join(timeout=5)
            for reader in readers:
                reader.join(timeout=5)
        if exceeded.is_set():
            raise ConfigurationError(f"{prefix} output exceeds {max_output_bytes} bytes")
        if process.returncode != 0:
            raise ConfigurationError(f"{prefix} exited {process.returncode}")
        return BoundedCommandResult(
            stdout=bytes(stdout),
            stderr=bytes(stderr),
            duration_seconds=time.monotonic() - start,
        )
