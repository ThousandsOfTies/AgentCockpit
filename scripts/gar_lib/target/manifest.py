"""gar-tools が提供する target.json の読込と検索。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.gar_lib.config import load_config
from scripts.gar_lib.tools_repository import gar_tools_root


@dataclass(frozen=True)
class TargetManifest:
    id: str
    display_name: str
    description: str
    tools_root: str
    default_backends: dict[str, str]
    backend_notes: dict[str, str]
    simulation: dict[str, dict[str, Any]] = field(default_factory=dict)

    def simulation_settings(self, backend_id: str) -> dict[str, Any]:
        return self.simulation.get(backend_id, {})


def discover_target_manifests() -> list[TargetManifest]:
    targets_root = _targets_root()
    if not targets_root.is_dir():
        return []
    return [
        manifest
        for path in sorted(targets_root.glob("*/target.json"))
        if (manifest := _load_target_manifest(path))
    ]


def active_target_manifest() -> TargetManifest | None:
    return target_by_id(discover_target_manifests(), load_config().get("selected_target"))


def target_by_id(targets: list[TargetManifest], target_id: str | None) -> TargetManifest | None:
    return next((target for target in targets if target.id == target_id), None)


def _targets_root() -> Path:
    configured = os.environ.get("GAR_TOOLS_TARGETS")
    return Path(configured).expanduser() if configured else gar_tools_root() / "targets"


def _load_target_manifest(path: Path) -> TargetManifest | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    target_id = _str(data.get("id"))
    display_name = _str(data.get("displayName"))
    description = _str(data.get("description"))
    tools_root = _str(data.get("toolsRoot"))
    if not (target_id and display_name and description and tools_root):
        return None
    return TargetManifest(
        id=target_id,
        display_name=display_name,
        description=description,
        tools_root=tools_root,
        default_backends=_str_dict(data.get("defaultBackends")),
        backend_notes=_str_dict(data.get("backendNotes")),
        simulation=_settings_dict(data.get("simulation")),
    )


def _str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _settings_dict(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        key: dict(item)
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, dict)
    }


def _str_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str) and isinstance(item, str)}
