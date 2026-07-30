"""Translate a target definition into the container shape that target needs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Any

DEFAULT_BRIDGE_PORT = 8080
DEFAULT_PUBLISHED_HOST = "127.0.0.1"
_IGNORED_CONTEXT_DIRECTORIES = {".git", ".pio", "__pycache__", "build", "node_modules"}
_MANAGED_ENVIRONMENT_VARIABLES = {"GAR_BRIDGE_PORT"}


@dataclass(frozen=True)
class DockerHostSpec:
    """target が simulation host に要求する container の形。"""

    image: str
    run_options: tuple[str, ...] = ()
    init_command: tuple[str, ...] = ()
    published_bridge_port: int = DEFAULT_BRIDGE_PORT
    container_bridge_port: int = DEFAULT_BRIDGE_PORT
    published_host: str = DEFAULT_PUBLISHED_HOST
    build_context: str | None = None
    build_context_fingerprint: str | None = None

    @property
    def bridge_port(self) -> int:
        """以前の呼び出し元向けに host 側の公開ポートを返す。"""

        return self.published_bridge_port

    @property
    def fingerprint(self) -> str:
        """container の実行形状を識別する安定した fingerprint。"""

        payload = {
            "image": self.image,
            "run_options": self.run_options,
            "init_command": self.init_command,
            "published_bridge_port": self.published_bridge_port,
            "container_bridge_port": self.container_bridge_port,
            "published_host": self.published_host,
            "build_context_fingerprint": self.build_context_fingerprint,
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


def docker_host_spec(
    settings: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> DockerHostSpec | None:
    """target manifest の simulation 設定から spec を組み立てる。imageがなければNone。"""
    image = settings.get("image")
    if not isinstance(image, str) or not image:
        return None

    build_context = _build_context(settings, root)
    return DockerHostSpec(
        image=image,
        run_options=_run_options(settings),
        init_command=tuple(_strings(settings.get("init"))),
        published_bridge_port=_published_bridge_port(settings),
        container_bridge_port=_container_bridge_port(settings),
        published_host=_published_host(settings),
        build_context=build_context,
        build_context_fingerprint=_context_fingerprint(build_context),
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
    for environment in _strings(settings.get("environment")):
        name = environment.partition("=")[0]
        if name in _MANAGED_ENVIRONMENT_VARIABLES:
            continue
        options.extend(("--env", environment))
    return tuple(options)


def _published_bridge_port(settings: Mapping[str, Any]) -> int:
    return _port_setting(settings, "publishedBridgePort")


def _container_bridge_port(settings: Mapping[str, Any]) -> int:
    return _port_setting(settings, "containerBridgePort")


def _published_host(settings: Mapping[str, Any]) -> str:
    value = settings.get("publishedHost")
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_PUBLISHED_HOST
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return DEFAULT_PUBLISHED_HOST


def _port_setting(settings: Mapping[str, Any], name: str) -> int:
    value = settings.get(name, settings.get("bridgePort"))
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535:
        return value
    return DEFAULT_BRIDGE_PORT


def _build_context(settings: Mapping[str, Any], root: Path | None) -> str | None:
    value = settings.get("buildContext")
    if not isinstance(value, str) or not value:
        return None
    return str(root / value) if root is not None else value


def _context_fingerprint(build_context: str | None) -> str | None:
    if build_context is None:
        return None
    root = Path(build_context)
    if not root.is_dir():
        return None

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in _IGNORED_CONTEXT_DIRECTORIES for part in relative.parts):
            continue
        if path.is_symlink():
            digest.update(b"link\0")
            digest.update(relative.as_posix().encode())
            digest.update(b"\0")
            digest.update(path.readlink().as_posix().encode())
            digest.update(b"\0")
        elif path.is_file():
            digest.update(b"file\0")
            digest.update(relative.as_posix().encode())
            digest.update(b"\0")
            digest.update(str(path.stat().st_mode & 0o111).encode())
            digest.update(b"\0")
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
    return digest.hexdigest()


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [item for item in value if isinstance(item, str) and item]
