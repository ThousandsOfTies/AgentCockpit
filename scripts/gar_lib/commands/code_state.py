"""Persistent connection state used by ``gar code`` commands."""

from __future__ import annotations

import json
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodespaceConnectionState:
    """Connection details shared by start, stop, status, and the terminal launcher."""

    codespace_name: str | None
    ssh_host: str
    remote_path: str
    mount_dir: Path

    def write(self, path: Path) -> None:
        """Atomically replace *path* with a private JSON state file."""

        if not _is_valid_state(self):
            raise ValueError("invalid Codespace connection state")

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "codespace_name": self.codespace_name,
            "ssh_host": self.ssh_host,
            "remote_path": self.remote_path,
            "mount_dir": str(self.mount_dir),
        }
        descriptor = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            output.write(descriptor)
            output.flush()
            os.fsync(output.fileno())

        try:
            temporary_path.chmod(0o600)
            os.replace(temporary_path, path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    @classmethod
    def load(cls, path: Path) -> CodespaceConnectionState | None:
        """Read state from JSON, returning ``None`` for missing or invalid data."""

        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None

        codespace_name = payload.get("codespace_name")
        ssh_host = payload.get("ssh_host")
        remote_path = payload.get("remote_path")
        mount_dir = payload.get("mount_dir")
        if not isinstance(ssh_host, str):
            return None
        if not isinstance(remote_path, str):
            return None
        if not isinstance(mount_dir, str):
            return None
        if codespace_name is not None and not isinstance(codespace_name, str):
            return None

        state = cls(
            codespace_name=codespace_name,
            ssh_host=ssh_host,
            remote_path=remote_path,
            mount_dir=Path(mount_dir).expanduser(),
        )
        return state if _is_valid_state(state) else None


def codespace_state_path(home: Path | None = None) -> Path:
    selected_home = home or Path.home()
    return selected_home / ".config" / "codespace-dev" / "state.json"


def load_connection_state(home: Path | None = None) -> CodespaceConnectionState | None:
    """Load current state and migrate the former shell-style file when needed."""

    selected_home = home or Path.home()
    state_path = codespace_state_path(selected_home)
    state = CodespaceConnectionState.load(state_path)
    if state is not None:
        return state

    legacy_path = selected_home / ".config" / "codespace-dev" / "env"
    legacy_values = load_legacy_codespace_state(legacy_path)
    state = _connection_state_from_legacy_values(legacy_values)
    if state is None:
        return None

    # Keep the old file as a recovery aid. Once JSON has been written, all later
    # reads use it and no longer depend on shell quoting.
    try:
        state.write(state_path)
    except OSError:
        pass
    return state


def load_legacy_codespace_state(state_file: Path) -> dict[str, str]:
    """Parse the previous KEY=VALUE state format without evaluating shell code."""

    if not state_file.is_file():
        return {}

    try:
        lines = state_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    state: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        try:
            parsed = shlex.split(value, comments=False, posix=True)
        except ValueError:
            continue
        if key and len(parsed) == 1:
            state[key] = parsed[0]
    return state


def codespace_terminal_script() -> str:
    """Return the launcher installed as ``~/.local/bin/codespace-terminal``."""

    return '''#!/usr/bin/env python3
"""Open an SSH terminal using state written by ``gar code start``."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

state_file = Path(
    os.environ.get(
        "CODESPACE_DEV_STATE",
        str(Path.home() / ".config" / "codespace-dev" / "state.json"),
    )
)
if not state_file.is_file():
    print(f"codespace-terminal: missing {state_file}", file=sys.stderr)
    print("Run: gar code start", file=sys.stderr)
    raise SystemExit(1)

try:
    state = json.loads(state_file.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    print(f"codespace-terminal: invalid {state_file}: {error}", file=sys.stderr)
    raise SystemExit(1) from error

host = state.get("ssh_host") if isinstance(state, dict) else None
remote_path = state.get("remote_path") if isinstance(state, dict) else None
if not isinstance(host, str) or not host or host.startswith("-"):
    print(f"codespace-terminal: ssh_host is missing or invalid in {state_file}", file=sys.stderr)
    raise SystemExit(1)

command = ["ssh", "-t", host]
if isinstance(remote_path, str) and remote_path:
    command.append(f"cd {shlex.quote(remote_path)} && exec bash -l")
os.execvp(command[0], command)
'''


def _connection_state_from_legacy_values(
    values: dict[str, str],
) -> CodespaceConnectionState | None:
    ssh_host = values.get("CODESPACE_SSH_HOST")
    remote_path = values.get("CODESPACE_REMOTE_PATH")
    mount_dir = values.get("CODESPACE_MOUNT_DIR")
    if not all((ssh_host, remote_path, mount_dir)):
        return None

    state = CodespaceConnectionState(
        codespace_name=values.get("CODESPACE_NAME"),
        ssh_host=ssh_host,
        remote_path=remote_path,
        mount_dir=Path(mount_dir).expanduser(),
    )
    return state if _is_valid_state(state) else None


def _is_valid_state(state: CodespaceConnectionState) -> bool:
    if state.codespace_name is not None:
        if not _is_safe_text(state.codespace_name) or state.codespace_name.startswith("-"):
            return False
    if not _is_safe_text(state.ssh_host) or state.ssh_host.startswith("-"):
        return False
    if any(character in state.ssh_host for character in "*?!"):
        return False
    if not _is_safe_text(state.remote_path):
        return False
    return state.mount_dir.is_absolute() and _is_safe_text(str(state.mount_dir))


def _is_safe_text(value: str) -> bool:
    return bool(value) and "\0" not in value and "\n" not in value and "\r" not in value
