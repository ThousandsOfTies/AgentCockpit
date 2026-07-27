"""Docker access channels without simulation-specific decisions."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from scripts.gar_lib.access._base import CommandResult, TransferResult
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError

DAEMON_FAILURE_MARKERS = (
    "cannot connect to the docker daemon",
    "is the docker daemon running",
    "error during connect",
    "permission denied while trying to connect to the docker daemon",
)

CONTAINER_FAILURE_MARKERS = (
    "no such container",
    "no such object",
    "is not running",
    "container is not running",
)


def docker_executable() -> str:
    executable = shutil.which("docker")
    if executable is None:
        raise GarDomainError(
            "docker が見つかりません。Docker Engine または Docker Desktop を導入してください。"
        )
    return executable


def connection_reason(stderr: str) -> str | None:
    lowered = stderr.lower()
    if any(marker in lowered for marker in DAEMON_FAILURE_MARKERS):
        return "daemon"
    if any(marker in lowered for marker in CONTAINER_FAILURE_MARKERS):
        return "container"
    return None


class DockerCliCommandChannel(Protocol):
    def run(self, arguments: tuple[str, ...]) -> CommandResult: ...


class DockerCliChannel:
    """docker CLI自体を実行する。containerが存在しない状態でも使える。"""

    def run(self, arguments: tuple[str, ...]) -> CommandResult:
        argv = (docker_executable(), *arguments)
        completed = subprocess.run(argv, check=False, capture_output=True, text=True)
        if completed.returncode != 0 and connection_reason(completed.stderr) == "daemon":
            raise AccessConnectionError(
                channel="docker",
                endpoint="daemon",
                reason="daemon",
                returncode=completed.returncode,
            )
        return CommandResult(argv, completed.returncode, completed.stdout, completed.stderr)


class DockerCommandChannel:
    """docker exec でcontainer内のシェルコマンドを実行する。"""

    def __init__(self, container: str, *, shell: str = "bash"):
        self.container = container
        self.shell = shell

    def run(self, command: str) -> CommandResult:
        argv = (
            docker_executable(),
            "exec",
            "-i",
            self.container,
            self.shell,
            "-lc",
            command,
        )
        completed = subprocess.run(argv, check=False, capture_output=True, text=True)
        reason = connection_reason(completed.stderr)
        if reason is not None:
            raise AccessConnectionError(
                channel="docker",
                endpoint=self.container,
                reason=reason,
                returncode=completed.returncode,
            )
        return CommandResult(argv, completed.returncode, completed.stdout, completed.stderr)


class DockerFileChannel:
    """docker cp でcontainerとファイルをやり取りする。"""

    def __init__(self, container: str):
        self.container = container

    def push(self, source: Path, destination: str) -> TransferResult:
        return self._run((str(source), f"{self.container}:{destination}"))

    def pull(self, source: str, destination: Path) -> TransferResult:
        return self._run((f"{self.container}:{source}", str(destination)))

    def _run(self, arguments: tuple[str, ...]) -> TransferResult:
        argv = (docker_executable(), "cp", *arguments)
        completed = subprocess.run(argv, check=False, capture_output=True, text=True)
        reason = connection_reason(completed.stderr)
        if reason is not None:
            raise AccessConnectionError(
                channel="docker",
                endpoint=self.container,
                reason=reason,
                returncode=completed.returncode,
            )
        return TransferResult(argv, completed.returncode, completed.stdout, completed.stderr)
