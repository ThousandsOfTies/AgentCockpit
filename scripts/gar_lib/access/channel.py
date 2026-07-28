"""Shared access channel contracts and process execution."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AccessResult:
    """Result of invoking an external access command."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class ConsoleSession:
    process: subprocess.Popen[bytes]


class CommandChannel(Protocol):
    def run(self, command: str) -> AccessResult: ...


class FileChannel(Protocol):
    def push(self, source: Path, destination: str) -> AccessResult: ...

    def pull(self, source: str, destination: Path) -> AccessResult: ...


class ConsoleChannel(Protocol):
    def open(self) -> ConsoleSession: ...


CompletedProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


def run_cli(
    argv: Sequence[str],
    *,
    runner: CompletedProcessRunner = subprocess.run,
) -> AccessResult:
    """Run a CLI command with the options shared by access adapters."""

    normalized_argv = tuple(argv)
    completed = runner(normalized_argv, check=False, capture_output=True, text=True)
    return AccessResult(
        normalized_argv,
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )
