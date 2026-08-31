"""Cross-platform serial console access."""

from __future__ import annotations

import subprocess
import time
from typing import Protocol

from scripts.gar_lib.access.channel import ConsoleSession
from scripts.gar_lib.core.errors import GarDomainError


class SerialPatternVerifier(Protocol):
    def wait(
        self,
        port: str,
        *,
        baud: int,
        pattern: str,
        timeout_seconds: float,
    ) -> None: ...


class PySerialPatternVerifier:
    """Wait for a boot marker on either a Windows COM port or a POSIX device."""

    def wait(
        self,
        port: str,
        *,
        baud: int,
        pattern: str,
        timeout_seconds: float,
    ) -> None:
        try:
            import serial
        except ImportError as error:  # pragma: no cover - launcher installs runtime dependencies
            raise GarDomainError("serial確認にはpyserialが必要です。garの依存関係を再導入してください") from error

        deadline = time.monotonic() + timeout_seconds
        expected = pattern.encode("utf-8")
        received = bytearray()
        try:
            with serial.Serial(port=port, baudrate=baud, timeout=0.2) as connection:
                while time.monotonic() < deadline:
                    waiting = int(getattr(connection, "in_waiting", 0) or 0)
                    chunk = connection.read(waiting or 1)
                    if chunk:
                        received.extend(chunk)
                        if expected in received:
                            return
        except (OSError, serial.SerialException) as error:
            raise GarDomainError(f"serial consoleを開けません: {port}: {error}") from error

        raise GarDomainError(f"serial consoleで起動確認文字列を受信できませんでした: {pattern!r}")


def serial_port_candidates() -> list[str]:
    """Return serial device names without assuming COM or ``/dev`` syntax."""

    try:
        from serial.tools import list_ports
    except ImportError:  # pragma: no cover - launcher installs runtime dependencies
        return []
    return sorted({port.device for port in list_ports.comports() if port.device})


class SerialConsoleChannel:
    def __init__(
        self,
        port: str,
        *,
        baud: int = 115200,
        executable: str = "picocom",
    ):
        self.port = port
        self.baud = baud
        self.executable = executable

    def open(self) -> ConsoleSession:
        process = subprocess.Popen((self.executable, "--baud", str(self.baud), self.port))
        return ConsoleSession(process)
