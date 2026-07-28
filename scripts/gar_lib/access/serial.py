"""Serial console access."""

from __future__ import annotations

import subprocess

from scripts.gar_lib.access.channel import ConsoleSession


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
