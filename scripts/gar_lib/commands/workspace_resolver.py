"""Resolve a configured workspace for command runners."""

from __future__ import annotations

from pathlib import Path

from scripts.gar_lib.core.config import load_config, saved_workspaces
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace


def _mapping(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _hardware_dir(
    entry: dict,
    connection: dict,
) -> Path | None:
    """Resolve the local CSV source that belongs to this product workspace."""

    configured_hardware = _mapping(entry.get("hardware"))
    configured_path = _string(configured_hardware.get("path"))
    connection_type = _string(connection.get("type"))
    local_root = (
        Path(connection["path"]).expanduser().resolve()
        if connection_type == "local" and _string(connection.get("path"))
        else None
    )

    if configured_path is not None:
        path = Path(configured_path).expanduser()
        if not path.is_absolute() and local_root is not None:
            path = local_root / path
        return path.resolve()

    if local_root is not None:
        product_hardware = local_root / "hardware"
        if product_hardware.is_dir():
            return product_hardware

    return None


def _workspace_from_entry(entry: dict) -> Workspace:
    connection = _mapping(entry.get("connection"))
    selected_target = _string(entry.get("selected_target"))
    return Workspace(
        id=entry["id"],
        name=entry["name"],
        branch=entry["branch"],
        connection=connection,
        selected_environments=_mapping(entry.get("selected_environments", entry.get("selected_providers"))),
        selected_target=selected_target,
        hardware_dir=_hardware_dir(entry, connection),
        build=_mapping(entry.get("build")),
        simulation_host=_mapping(entry.get("simulation_host")),
        virtualbox=_mapping(entry.get("virtualbox")),
        ec2=_mapping(entry.get("ec2")),
        docker=_mapping(entry.get("docker")),
        target=_mapping(entry.get("target")),
        adb=_mapping(entry.get("adb")),
        esp32=_mapping(entry.get("esp32")),
    )


def _select_workspace_entry(config: dict, selector: str | None) -> dict:
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
    return matches[0]


def resolve_workspace(selector: str | None) -> Workspace:
    """`--workspace` の指定（省略可）から workspace を一意に決める。"""

    config = load_config(workspace_selector=selector)
    return _workspace_from_entry(_select_workspace_entry(config, selector))
