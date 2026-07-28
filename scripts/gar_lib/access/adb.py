"""ADB shell and file channels."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from scripts.gar_lib.access.channel import AccessResult, run_cli
from scripts.gar_lib.core.errors import AccessConnectionError


def _connection_reason(stderr: str) -> str | None:
    lowered = stderr.lower()
    for marker, reason in (
        ("no devices/emulators found", "no_device"),
        ("device offline", "device_offline"),
        ("device unauthorized", "device_unauthorized"),
        ("device not found", "device_not_found"),
    ):
        if marker in lowered:
            return reason
    return None


class _AdbChannel:
    def __init__(self, serial: str | None = None, *, executable: str = "adb"):
        self.serial = serial
        self.executable = executable

    def _prefix(self) -> tuple[str, ...]:
        return (self.executable, "-s", self.serial) if self.serial else (self.executable,)

    def _raise_connection_error(self, returncode: int, stderr: str) -> None:
        reason = _connection_reason(stderr)
        if reason:
            raise AccessConnectionError(
                channel="adb",
                endpoint=self.serial or "default",
                reason=reason,
                returncode=returncode,
            )


class AdbShellChannel(_AdbChannel):
    def run(self, command: str) -> AccessResult:
        argv = (*self._prefix(), "shell", command)
        result = run_cli(argv, runner=subprocess.run)
        self._raise_connection_error(result.returncode, result.stderr)
        return result


class AdbFileChannel(_AdbChannel):
    def __init__(
        self,
        serial: str | None = None,
        *,
        executable: str = "adb",
        local_path_transform: Callable[[Path], str] | None = None,
    ):
        super().__init__(serial, executable=executable)
        self.local_path_transform = local_path_transform or (lambda path: str(path))

    def push(self, source: Path, destination: str) -> AccessResult:
        return self._run("push", self.local_path_transform(source), destination)

    def pull(self, source: str, destination: Path) -> AccessResult:
        return self._run("pull", source, self.local_path_transform(destination))

    def _run(self, action: str, source: str, destination: str) -> AccessResult:
        argv = (*self._prefix(), action, source, destination)
        result = run_cli(argv, runner=subprocess.run)
        self._raise_connection_error(result.returncode, result.stderr)
        return result
