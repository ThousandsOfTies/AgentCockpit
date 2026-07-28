"""SSH command and scp file channels."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.gar_lib.access.channel import AccessResult, run_cli
from scripts.gar_lib.core.errors import AccessConnectionError

SSH_CONNECTION_OPTIONS = (
    "-o",
    "ConnectTimeout=10",
    "-o",
    "ConnectionAttempts=1",
    "-o",
    "ServerAliveInterval=15",
    "-o",
    "ServerAliveCountMax=3",
    "-o",
    "StrictHostKeyChecking=accept-new",
)


def _connection_reason(stderr: str) -> str:
    lowered = stderr.lower()
    if "host key verification failed" in lowered:
        return "host_key_verification"
    if "permission denied" in lowered:
        return "ssh_authentication"
    if "connection refused" in lowered:
        return "connection_refused"
    if "timed out" in lowered or "operation timed out" in lowered:
        return "timeout"
    return "connection_or_authentication"


class SshCommandChannel:
    def __init__(self, host: str, *, config_path: Path | None = None):
        self.host = host
        self.config_path = config_path or Path.home() / ".ssh" / "config"

    def run(self, command: str) -> AccessResult:
        argv = (
            "ssh",
            "-F",
            str(self.config_path),
            *SSH_CONNECTION_OPTIONS,
            "-o",
            f"HostKeyAlias={self.host}",
            self.host,
            command,
        )
        result = run_cli(argv, runner=subprocess.run)
        if result.returncode == 255:
            raise AccessConnectionError(
                channel="ssh",
                endpoint=self.host,
                reason=_connection_reason(result.stderr),
                returncode=result.returncode,
            )
        return result


class ScpFileChannel:
    def __init__(self, host: str, *, config_path: Path | None = None):
        self.host = host
        self.config_path = config_path or Path.home() / ".ssh" / "config"

    def push(self, source: Path, destination: str) -> AccessResult:
        return self._run(("-r", str(source), f"{self.host}:{destination}"))

    def pull(self, source: str, destination: Path) -> AccessResult:
        return self._run(("-r", f"{self.host}:{source}", str(destination)))

    def _run(self, arguments: tuple[str, ...]) -> AccessResult:
        argv = (
            "scp",
            "-F",
            str(self.config_path),
            *SSH_CONNECTION_OPTIONS,
            "-o",
            f"HostKeyAlias={self.host}",
            *arguments,
        )
        result = run_cli(argv, runner=subprocess.run)
        if result.returncode == 255:
            raise AccessConnectionError(
                channel="scp",
                endpoint=self.host,
                reason=_connection_reason(result.stderr),
                returncode=result.returncode,
            )
        return result
