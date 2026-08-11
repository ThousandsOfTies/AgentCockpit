"""Strict schema-v1 model for ``gar system`` topology files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.gar_lib.core.errors import GarDomainError

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]*$")
_APPLICATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_PROTOCOL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+./-]*$")


@dataclass(frozen=True)
class RuntimeEnvSource:
    kind: str
    value: str | int


@dataclass(frozen=True)
class SystemNode:
    id: str
    workspace: str
    app: str
    role: str
    environment: str
    runtime_env: dict[str, RuntimeEnvSource]


@dataclass(frozen=True)
class SystemLink:
    id: str
    from_node: str
    to_node: str
    protocol: str
    port: int


@dataclass(frozen=True)
class SystemTopology:
    name: str
    nodes: dict[str, SystemNode]
    links: dict[str, SystemLink]
    order: tuple[str, ...]


def load_topology(path: str | Path) -> SystemTopology:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise GarDomainError(f"system fileを読み込めません: {source}: {error}") from error
    except json.JSONDecodeError as error:
        raise GarDomainError(f"system fileはJSONである必要があります: {source}: {error.msg}") from error
    return topology_from_value(raw)


def topology_from_value(raw: object) -> SystemTopology:
    root = _object(raw, "system")
    _only(root, {"schema_version", "name", "nodes", "links", "order"}, "system")
    if root.get("schema_version") != 1:
        raise GarDomainError("system.schema_version は 1 である必要があります")
    name = _nonempty(root.get("name"), "system.name")
    raw_nodes = _array(root.get("nodes"), "system.nodes")
    if len(raw_nodes) < 2:
        raise GarDomainError("system.nodes は2件以上必要です")
    nodes: dict[str, SystemNode] = {}
    for index, value in enumerate(raw_nodes):
        node = _node(value, index)
        if node.id in nodes:
            raise GarDomainError(f"node idが重複しています: {node.id}")
        nodes[node.id] = node
    raw_links = _array(root.get("links"), "system.links")
    links: dict[str, SystemLink] = {}
    for index, value in enumerate(raw_links):
        link = _link(value, index)
        if link.id in links:
            raise GarDomainError(f"link idが重複しています: {link.id}")
        if link.from_node not in nodes or link.to_node not in nodes:
            raise GarDomainError(f"link {link.id} は存在しないnodeを参照しています")
        links[link.id] = link
    order_values = _array(root.get("order"), "system.order")
    order = tuple(_identifier(value, f"system.order[{index}]") for index, value in enumerate(order_values))
    if len(order) != len(nodes) or len(set(order)) != len(order) or set(order) != set(nodes):
        raise GarDomainError("system.order はすべてのnodeをちょうど1回ずつ参照する必要があります")
    for node in nodes.values():
        for source in node.runtime_env.values():
            if source.kind == "node_private_ip" and source.value not in nodes:
                raise GarDomainError(f"node {node.id} のruntime_envは存在しないnodeを参照しています: {source.value}")
            if source.kind == "link_port" and source.value not in links:
                raise GarDomainError(f"node {node.id} のruntime_envは存在しないlinkを参照しています: {source.value}")
    return SystemTopology(name=name, nodes=nodes, links=links, order=order)


def _node(raw: object, index: int) -> SystemNode:
    where = f"system.nodes[{index}]"
    value = _object(raw, where)
    _only(value, {"id", "workspace", "app", "role", "environment", "runtime_env"}, where)
    environment = _nonempty(value.get("environment"), f"{where}.environment")
    if environment not in {"sim", "target"}:
        raise GarDomainError(f"{where}.environment は sim または target である必要があります")
    runtime_raw = _object(value.get("runtime_env"), f"{where}.runtime_env")
    runtime_env: dict[str, RuntimeEnvSource] = {}
    for key, source in runtime_raw.items():
        if not _ENV_NAME.fullmatch(key):
            raise GarDomainError(f"{where}.runtime_env の環境変数名が安全ではありません: {key}")
        runtime_env[key] = _runtime_source(source, f"{where}.runtime_env.{key}")
    return SystemNode(
        id=_identifier(value.get("id"), f"{where}.id"),
        workspace=_nonempty(value.get("workspace"), f"{where}.workspace"),
        app=_application(value.get("app"), f"{where}.app"),
        role=_nonempty(value.get("role"), f"{where}.role"),
        environment=environment,
        runtime_env=runtime_env,
    )


def _link(raw: object, index: int) -> SystemLink:
    where = f"system.links[{index}]"
    value = _object(raw, where)
    _only(value, {"id", "from", "to", "protocol", "port"}, where)
    port = value.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise GarDomainError(f"{where}.port は1から65535の整数である必要があります")
    protocol = _nonempty(value.get("protocol"), f"{where}.protocol")
    if not _PROTOCOL.fullmatch(protocol):
        raise GarDomainError(f"{where}.protocol が不正です")
    if protocol.rsplit("/", 1)[-1].lower() not in {"tcp", "udp"}:
        raise GarDomainError(f"{where}.protocol のtransportは tcp または udp である必要があります")
    return SystemLink(
        id=_identifier(value.get("id"), f"{where}.id"),
        from_node=_identifier(value.get("from"), f"{where}.from"),
        to_node=_identifier(value.get("to"), f"{where}.to"),
        protocol=protocol,
        port=port,
    )


def _runtime_source(raw: object, where: str) -> RuntimeEnvSource:
    value = _object(raw, where)
    _only(value, {"literal", "node_private_ip", "link_port"}, where)
    if len(value) != 1:
        raise GarDomainError(f"{where} は literal、node_private_ip、link_port のいずれか1つだけ指定します")
    key, source = next(iter(value.items()))
    if key == "literal":
        if not isinstance(source, str | int | float) or isinstance(source, bool):
            raise GarDomainError(f"{where}.literal はscalarである必要があります")
    else:
        source = _identifier(source, f"{where}.{key}")
    return RuntimeEnvSource(kind=key, value=source)


def _object(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GarDomainError(f"{where} はobjectである必要があります")
    return value


def _array(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise GarDomainError(f"{where} はarrayである必要があります")
    return value


def _only(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise GarDomainError(f"{where} に未対応の項目があります: {', '.join(sorted(unknown))}")


def _nonempty(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise GarDomainError(f"{where} は空でない文字列である必要があります")
    return value


def _identifier(value: object, where: str) -> str:
    text = _nonempty(value, where)
    if not _IDENTIFIER.fullmatch(text):
        raise GarDomainError(f"{where} は英小文字で始まる安全なidentifierである必要があります")
    return text


def _application(value: object, where: str) -> str:
    text = _nonempty(value, where)
    if not _APPLICATION.fullmatch(text):
        raise GarDomainError(f"{where} は安全なapplication名である必要があります")
    return text
