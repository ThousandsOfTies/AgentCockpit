"""Translate a target definition into the container shape that target needs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BRIDGE_PORT = 8080


@dataclass(frozen=True)
class DockerHostSpec:
    """target が simulation host に要求する container の形。"""

    image: str
    run_options: tuple[str, ...] = ()
    init_command: tuple[str, ...] = ()
    bridge_port: int = DEFAULT_BRIDGE_PORT
    build_context: str | None = None


def docker_host_spec(
    settings: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> DockerHostSpec | None:
    """target manifest の simulation 設定から spec を組み立てる。imageがなければNone。"""
    image = settings.get("image")
    if not isinstance(image, str) or not image:
        return None

    return DockerHostSpec(
        image=image,
        run_options=_run_options(settings),
        init_command=tuple(_strings(settings.get("init"))),
        bridge_port=_bridge_port(settings),
        build_context=_build_context(settings, root),
    )


def _run_options(settings: Mapping[str, Any]) -> tuple[str, ...]:
    options: list[str] = []
    if settings.get("privileged"):
        options.append("--privileged")
    if settings.get("hostCgroups"):
        options.append("--cgroupns=host")
    for path in _strings(settings.get("tmpfs")):
        options.extend(("--tmpfs", path))
    for mount in _strings(settings.get("mounts")):
        options.extend(("--volume", mount))
    for device in _strings(settings.get("devices")):
        options.extend(("--device", device))
    return tuple(options)


def _bridge_port(settings: Mapping[str, Any]) -> int:
    value = settings.get("bridgePort")
    return value if isinstance(value, int) and not isinstance(value, bool) else DEFAULT_BRIDGE_PORT


def _build_context(settings: Mapping[str, Any], root: Path | None) -> str | None:
    value = settings.get("buildContext")
    if not isinstance(value, str) or not value:
        return None
    return str(root / value) if root is not None else value


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [item for item in value if isinstance(item, str) and item]
