"""command runner 共通の workspace 解決。"""

from __future__ import annotations

from scripts.gar_lib.config import load_config, saved_workspaces
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace


def workspace_for(selector: str | None) -> Workspace:
    """`--workspace` の指定（省略可）から workspace を一意に決める。"""

    config = load_config()
    entries = saved_workspaces(config)
    if selector:
        matches = [entry for entry in entries if selector in (entry["id"], entry["name"])]
    elif isinstance(config.get("workspace_id"), str):
        matches = [entry for entry in entries if entry["id"] == config["workspace_id"]]
    elif len(entries) == 1:
        matches = entries
    else:
        matches = []

    if len(matches) != 1:
        available = ", ".join(entry["name"] for entry in entries) or "(なし)"
        raise GarDomainError(f"workspace を一意に選べません。--workspace を指定してください: {available}")

    entry = matches[0]
    return Workspace(
        id=entry["id"],
        name=entry["name"],
        branch=entry["branch"],
        connection=dict(entry["connection"]),
        selected_environments=_mapping(entry.get("selected_environments", entry.get("selected_providers"))),
        ec2=_mapping(entry.get("ec2")),
        docker=_mapping(entry.get("docker")),
        target=_mapping(entry.get("target")),
        adb=_mapping(entry.get("adb")),
        esp32=_mapping(entry.get("esp32")),
    )


def _mapping(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}
