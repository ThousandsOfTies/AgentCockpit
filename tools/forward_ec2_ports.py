#!/usr/bin/env python3
"""Manage the SSH process used for GAR simulation port forwarding.

The state file records both a PID and the exact SSH command.  A PID by itself
is not an identity because operating systems reuse PIDs; stop/status therefore
inspect ``/proc/<pid>/cmdline`` before treating a process as GAR-owned.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_VERSION = 1
DEFAULT_HTTP_PORT = 8080
REMOTE_HTTP_PORT = 8080
LEGACY_WS_PORT = 8765
STARTUP_CHECK_SECONDS = 1.0
STOP_WAIT_SECONDS = 3.0


@dataclass(frozen=True)
class PortForwardConfig:
    host: str
    http_port: int

    def ssh_command(self, ssh_executable: str, ssh_config: Path) -> tuple[str, ...]:
        return (
            ssh_executable,
            "-F",
            str(ssh_config),
            "-N",
            "-n",
            "-o",
            "ExitOnForwardFailure=yes",
            "-L",
            f"{self.http_port}:127.0.0.1:{REMOTE_HTTP_PORT}",
            self.host,
        )

    def legacy_ssh_command(self, ssh_executable: str, ssh_config: Path) -> tuple[str, ...]:
        """Return the two-forward command used before WebSocket moved to /ws."""

        command = self.ssh_command(ssh_executable, ssh_config)
        return (
            *command[:-1],
            "-L",
            f"{LEGACY_WS_PORT}:127.0.0.1:{LEGACY_WS_PORT}",
            command[-1],
        )


@dataclass(frozen=True)
class PortForwardState:
    pid: int
    config: PortForwardConfig
    command: tuple[str, ...]
    started_at: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "pid": self.pid,
            "host": self.config.host,
            "http_port": self.config.http_port,
            "command": list(self.command),
            "started_at": self.started_at,
        }

    @classmethod
    def from_payload(cls, payload: object) -> PortForwardState:
        if not isinstance(payload, dict) or payload.get("version") != STATE_VERSION:
            raise ValueError("unsupported state format")
        pid = payload.get("pid")
        host = payload.get("host")
        http_port = payload.get("http_port")
        command = payload.get("command")
        started_at = payload.get("started_at")
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError("invalid pid")
        if not isinstance(host, str) or not host:
            raise ValueError("invalid host")
        if not isinstance(http_port, int):
            raise ValueError("invalid port")
        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            raise ValueError("invalid command")
        if not isinstance(started_at, str):
            raise ValueError("invalid started_at")
        return cls(
            pid=pid,
            config=PortForwardConfig(host, http_port),
            command=tuple(command),
            started_at=started_at,
        )


@dataclass(frozen=True)
class PortForwardStateStore:
    state_path: Path

    def load(self) -> PortForwardState | None:
        if not self.state_path.exists():
            return None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return PortForwardState.from_payload(payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Ignoring invalid port-forward state {self.state_path}: {exc}", file=sys.stderr)
            self.remove()
            return None

    def save(self, state: PortForwardState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(state.to_payload(), ensure_ascii=False, indent=2) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            suffix=".tmp",
            dir=self.state_path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(serialized)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(self.state_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def remove(self) -> None:
        self.state_path.unlink(missing_ok=True)


def parse_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def read_process_command(pid: int) -> tuple[str, ...] | None:
    try:
        raw_command = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    parts = tuple(part.decode("utf-8", errors="replace") for part in raw_command.split(b"\0") if part)
    return parts or None


def commands_identify_same_process(expected: tuple[str, ...], actual: tuple[str, ...] | None) -> bool:
    if actual is None or len(expected) != len(actual):
        return False
    if Path(expected[0]).name != Path(actual[0]).name:
        return False
    return expected[1:] == actual[1:]


def process_is_owned(state: PortForwardState) -> bool:
    return commands_identify_same_process(state.command, read_process_command(state.pid))


def state_directory() -> Path:
    explicit_directory = os.environ.get("GAR_PORT_FORWARD_STATE_DIR")
    if explicit_directory:
        return Path(explicit_directory).expanduser()
    runtime_directory = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_directory:
        return Path(runtime_directory) / "Gapless Agent Runtime"
    return Path.home() / ".cache" / "Gapless Agent Runtime"


def selected_ssh_executable() -> str:
    explicit_executable = os.environ.get("GAR_SSH_EXECUTABLE")
    if explicit_executable:
        return explicit_executable
    return shutil.which("ssh") or "ssh"


def print_connection(state: PortForwardState) -> None:
    print(f"Host: {state.config.host}")
    print(f"Panel: http://127.0.0.1:{state.config.http_port}")


def migrate_legacy_pid_file(
    *,
    legacy_pid_path: Path,
    store: PortForwardStateStore,
    config: PortForwardConfig,
    expected_command: tuple[str, ...],
    alternative_commands: tuple[tuple[str, ...], ...] = (),
) -> PortForwardState | None:
    if store.state_path.exists() or not legacy_pid_path.exists():
        return store.load()
    try:
        pid = int(legacy_pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        legacy_pid_path.unlink(missing_ok=True)
        return None

    legacy_pid_path.unlink(missing_ok=True)
    for command in (expected_command, *alternative_commands):
        candidate = PortForwardState(
            pid=pid,
            config=config,
            command=command,
            started_at="migrated-from-pid-file",
        )
        if process_is_owned(candidate):
            store.save(candidate)
            return candidate
    return None


def start_forward(
    *,
    config: PortForwardConfig,
    store: PortForwardStateStore,
    log_path: Path,
    command: tuple[str, ...],
) -> int:
    existing = store.load()
    if existing is not None and process_is_owned(existing):
        if existing.config == config:
            print(f"EC2 port forward already running: pid {existing.pid}")
            print_connection(existing)
            return 0
        print("Another GAR port forward is already running. Stop it first.", file=sys.stderr)
        print_connection(existing)
        return 1
    if existing is not None:
        print("Removed stale port-forward state; its PID is not owned by GAR.", file=sys.stderr)
        store.remove()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as exc:
        print(f"Failed to launch SSH port forward: {exc}", file=sys.stderr)
        return 1

    state = PortForwardState(
        pid=process.pid,
        config=config,
        command=command,
        started_at=datetime.now(UTC).isoformat(),
    )
    store.save(state)

    deadline = time.monotonic() + STARTUP_CHECK_SECONDS
    while time.monotonic() < deadline and process.poll() is None:
        time.sleep(0.05)
    if process.poll() is not None:
        store.remove()
        print(f"Failed to start EC2 port forward. Log: {log_path}", file=sys.stderr)
        try:
            print(log_path.read_text(encoding="utf-8"), file=sys.stderr, end="")
        except OSError:
            pass
        return process.returncode or 1

    print(f"Started EC2 port forward: pid {state.pid}")
    print_connection(state)
    return 0


def stop_forward(*, requested_config: PortForwardConfig, store: PortForwardStateStore) -> int:
    state = store.load()
    if state is None:
        print("EC2 port forward is not running.")
        return 0
    if not process_is_owned(state):
        store.remove()
        print("EC2 port forward is not running. Removed stale state without signalling its PID.")
        return 0
    if state.config != requested_config:
        print("The active GAR port forward belongs to a different host or port:", file=sys.stderr)
        print_connection(state)
        return 1

    try:
        os.kill(state.pid, signal.SIGTERM)
    except OSError as exc:
        print(f"Failed to stop EC2 port forward pid {state.pid}: {exc}", file=sys.stderr)
        return 1
    deadline = time.monotonic() + STOP_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not process_is_owned(state):
            store.remove()
            print("Stopped EC2 port forward.")
            return 0
        time.sleep(0.05)

    print(f"Timed out while stopping EC2 port forward pid {state.pid}.", file=sys.stderr)
    return 1


def status_forward(*, requested_config: PortForwardConfig, store: PortForwardStateStore) -> int:
    state = store.load()
    if state is None or not process_is_owned(state):
        if state is not None:
            store.remove()
        print("EC2 port forward is not running.")
        return 1
    if state.config != requested_config:
        print("A GAR port forward is running, but for a different host or port:", file=sys.stderr)
        print_connection(state)
        return 1

    print(f"EC2 port forward is running: pid {state.pid}")
    print_connection(state)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/forward_ec2_ports.sh",
        description="Create a WSL-side SSH port forward for the EC2 hardware panel.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    default_host = os.environ.get("EC2")
    parser.add_argument(
        "--host",
        default=default_host,
        required=default_host is None,
        help="SSH config host used for the remote simulation machine (or EC2 environment variable)",
    )
    parser.add_argument(
        "--http",
        type=parse_port,
        default=os.environ.get("HTTP_PORT", str(DEFAULT_HTTP_PORT)),
        help=f"local port forwarded to remote HTTP port {REMOTE_HTTP_PORT}",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stop", action="store_true", help="stop the matching GAR-owned forward")
    mode.add_argument("--status", action="store_true", help="show the matching forward state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = PortForwardConfig(args.host, args.http)
    directory = state_directory()
    store = PortForwardStateStore(directory / "ec2-port-forward.json")
    log_path = directory / "ec2-port-forward.log"
    ssh_executable = selected_ssh_executable()
    ssh_config = Path.home() / ".ssh" / "config"
    command = config.ssh_command(ssh_executable, ssh_config)
    legacy_command = config.legacy_ssh_command(ssh_executable, ssh_config)
    migrate_legacy_pid_file(
        legacy_pid_path=directory / "ec2-port-forward.pid",
        store=store,
        config=config,
        expected_command=command,
        alternative_commands=(legacy_command,),
    )

    if args.stop:
        return stop_forward(requested_config=config, store=store)
    if args.status:
        return status_forward(requested_config=config, store=store)
    return start_forward(config=config, store=store, log_path=log_path, command=command)


if __name__ == "__main__":
    raise SystemExit(main())
