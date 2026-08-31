"""VS Code integrated terminal profile management (settings.json)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def write_vscode_terminal_profile(
    settings_path: Path,
    profile_name: str,
    terminal_bin: Path,
    *,
    arguments: list[str] | None = None,
) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if settings_path.exists() and settings_path.stat().st_size:
        data = json.loads(settings_path.read_text(encoding="utf-8"))

    platform_name = "windows" if os.name == "nt" else "linux"
    profiles = data.setdefault(f"terminal.integrated.profiles.{platform_name}", {})
    if arguments is not None:
        profiles[profile_name] = {
            "path": str(terminal_bin),
            "args": arguments,
        }
    elif os.name == "nt" and terminal_bin.suffix.lower() == ".cmd":
        profiles[profile_name] = {
            "path": os.environ.get("COMSPEC", "cmd.exe"),
            "args": ["/d", "/c", str(terminal_bin)],
        }
    else:
        profiles[profile_name] = {"path": str(terminal_bin)}
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def remove_vscode_terminal_profile(settings_path: Path, profile_name: str) -> int:
    if not settings_path.exists() or settings_path.stat().st_size == 0:
        print(f"Profile:   not present ({profile_name})")
        return 0

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"gar code stop: invalid VS Code settings JSON: {settings_path}", file=sys.stderr)
        return 1

    platform_name = "windows" if os.name == "nt" else "linux"
    profiles = data.get(f"terminal.integrated.profiles.{platform_name}")
    if not isinstance(profiles, dict) or profile_name not in profiles:
        print(f"Profile:   not present ({profile_name})")
        return 0

    del profiles[profile_name]
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Profile:   removed {profile_name} from {settings_path}")
    return 0
