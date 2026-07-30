"""Local process capability shared by simulation environment implementations."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ManagedProcess:
    """A local process identity that is safe to persist between GAR invocations."""

    pid: int
    argv: tuple[str, ...]
    start_time_ticks: int | None = None

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> ManagedProcess | None:
        pid = state.get("pid")
        raw_argv = state.get("argv")
        start_time_ticks = state.get("start_time_ticks")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return None
        if not isinstance(raw_argv, list):
            return None
        if not raw_argv or not all(isinstance(value, str) for value in raw_argv):
            return None
        if not isinstance(start_time_ticks, int) or isinstance(start_time_ticks, bool):
            start_time_ticks = None
        return cls(pid, tuple(raw_argv), start_time_ticks)

    def to_state(self) -> dict[str, object]:
        return {
            "pid": self.pid,
            "argv": list(self.argv),
            "start_time_ticks": self.start_time_ticks,
        }


class ProcessChannel(Protocol):
    def find_executable(self, name: str, *, candidates: tuple[Path, ...] = ()) -> str | None: ...

    def start(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        log_path: Path,
    ) -> ManagedProcess: ...

    def owns(self, process: ManagedProcess) -> bool: ...

    def terminate_group(self, process: ManagedProcess) -> bool: ...


@dataclass(frozen=True)
class ProcessStateStore:
    """Persist local runtime process identity without partial writes or start races."""

    path: Path

    def read(self) -> dict[str, object]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def write(self, payload: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(serialized)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize state-changing operations from separate GAR processes."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class LocalProcessChannel:
    def find_executable(self, name: str, *, candidates: tuple[Path, ...] = ()) -> str | None:
        executable = shutil.which(name)
        if executable:
            return executable
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return None

    def start(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        log_path: Path,
    ) -> ManagedProcess:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return ManagedProcess(
            process.pid,
            argv,
            start_time_ticks=self._start_time_ticks(process.pid),
        )

    def owns(self, process: ManagedProcess) -> bool:
        """Return true only while *pid* still identifies the process GAR launched."""

        if process.pid <= 0:
            return False
        if not self._is_running(process.pid):
            return False
        current_argv = self._argv(process.pid)
        if current_argv != process.argv:
            return False
        if process.start_time_ticks is None:
            return True
        return self._start_time_ticks(process.pid) == process.start_time_ticks

    def terminate_group(self, process: ManagedProcess) -> bool:
        """Terminate the process group only when the persisted identity still matches."""

        if not self.owns(process):
            return False
        try:
            if os.getpgid(process.pid) != process.pid:
                return False
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return False
        return True

    @staticmethod
    def _is_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _argv(pid: int) -> tuple[str, ...] | None:
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            return None
        values = raw.rstrip(b"\0").split(b"\0") if raw else []
        return tuple(value.decode("utf-8", errors="replace") for value in values)

    @staticmethod
    def _start_time_ticks(pid: int) -> int | None:
        """Read Linux procfs field 22 without being confused by spaces in comm."""

        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            _, separator, remainder = stat.rpartition(")")
            if not separator:
                return None
            # The remainder starts at field 3 (state); starttime is field 22.
            return int(remainder.split()[19])
        except (OSError, ValueError, IndexError):
            return None
