"""Ordered orchestration of a :mod:`gar system` topology."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from scripts.gar_lib.api import Gar
from scripts.gar_lib.commands.workspace_resolver import resolve_workspace
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.system.model import SystemLink, SystemNode, SystemTopology


@dataclass(frozen=True)
class SystemReport:
    command: str
    name: str
    nodes: list[dict[str, object]]
    links: list[dict[str, object]]
    failures: list[dict[str, str]]

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": f"system.{self.command}",
            "name": self.name,
            "ok": self.ok,
            "exit_code": self.exit_code,
            "nodes": self.nodes,
            "links": self.links,
            "failures": self.failures,
        }


class SystemOrchestrator:
    """Call GAR's public node APIs in the topology's declared order."""

    def __init__(
        self,
        topology: SystemTopology,
        *,
        workspace_resolver: Callable[[str], Workspace] = resolve_workspace,
        gar_factory: Callable[[Workspace], Gar] = Gar,
    ):
        self.topology = topology
        self.workspace_resolver = workspace_resolver
        self.gar_factory = gar_factory

    def run(self, command: str) -> SystemReport:
        if command not in {"build", "deploy", "start", "status", "diag", "test"}:
            raise GarDomainError(f"未対応の system action: {command}")
        workspaces, failures = self._resolve_workspaces()
        nodes: list[dict[str, object]] = []
        for node_id in self.topology.order:
            node = self.topology.nodes[node_id]
            workspace = workspaces.get(node_id)
            if workspace is None:
                nodes.append({"id": node.id, "workspace": node.workspace, "environment": node.environment, "ok": False})
                continue
            result = self._run_node(command, node, workspace, workspaces)
            nodes.append(result)
            if not result["ok"]:
                failures.append({"node": node.id, "action": command, "error": str(result["error"])})
        links = self._resolved_links(workspaces, failures, resolve_private_ips=command in {"deploy", "start"})
        return SystemReport(command=command, name=self.topology.name, nodes=nodes, links=links, failures=failures)

    def _resolve_workspaces(self) -> tuple[dict[str, Workspace], list[dict[str, str]]]:
        resolved: dict[str, Workspace] = {}
        failures: list[dict[str, str]] = []
        for node_id in self.topology.order:
            node = self.topology.nodes[node_id]
            try:
                resolved[node_id] = self.workspace_resolver(node.workspace)
            except Exception as error:
                failures.append({"node": node.id, "action": "resolve", "error": str(error)})
        return resolved, failures

    def _run_node(
        self,
        command: str,
        node: SystemNode,
        workspace: Workspace,
        workspaces: dict[str, Workspace],
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "id": node.id,
            "workspace": node.workspace,
            "app": node.app,
            "role": node.role,
            "environment": node.environment,
            "ok": True,
        }
        try:
            gar = self.gar_factory(workspace)
            if command == "build":
                if node.environment == "sim":
                    gar.sim.app.build()
                    gar.sim.runtime.build()
                else:
                    gar.target.build()
            elif command == "deploy":
                result["deployment"] = self._deploy(gar, node, workspaces)
            elif command == "start":
                self._start(gar, node, workspaces)
            elif command == "status":
                status = self._status(gar, node)
                result["status"] = status
                if status:
                    raise GarDomainError(f"status failed (exit {status})")
            else:  # diag and test deliberately use diagnostics only in P1-2.
                result["diagnostic"] = self._diag(gar, node)
            return result
        except Exception as error:
            result["ok"] = False
            result["error"] = str(error)
            return result

    def _deploy(self, gar: Gar, node: SystemNode, workspaces: dict[str, Workspace]) -> dict[str, object]:
        # Resolve every machine-local binding before changing the node.  A
        # missing peer must not leave a newly deployed artifact with stale
        # runtime configuration.
        values = self._runtime_env(node, workspaces)
        if node.environment == "sim":
            gar.sim.runtime.deploy()
            gar.sim.app.deploy()
            destination = gar.sim.runtime.configure_system_env(node.app, values)
            return {"system_env": destination}
        else:
            # Target validates compatibility before placing the env, then
            # deploys and converges the app against that same atomic file.
            deployed = gar.target.deploy_report(system_env_app=node.app, system_env=values)
            assert deployed.configuration is not None
            return {"system_env": deployed.configuration.destination}

    def _start(self, gar: Gar, node: SystemNode, workspaces: dict[str, Workspace]) -> None:
        values = self._runtime_env(node, workspaces)
        if node.environment == "sim":
            # Resolve network bindings at start too, so a changed private address is not stale.
            gar.sim.runtime.configure_system_env(node.app, values)
            exit_code = gar.sim.runtime.start(no_port_forward=True)
            if exit_code:
                raise GarDomainError(f"simulation runtime start failed (exit {exit_code})")
        else:
            # Re-resolve topology-owned bindings immediately before target
            # lifecycle convergence, so an address cannot become stale.
            gar.target.start(app=node.app, system_env=values)

    def _status(self, gar: Gar, node: SystemNode) -> int:
        if node.environment == "sim":
            return gar.sim.runtime.status()
        return gar.target.status(app=node.app).exit_code

    def _diag(self, gar: Gar, node: SystemNode) -> dict[str, object]:
        report = gar.sim.runtime.diag() if node.environment == "sim" else gar.target.diag(app=node.app)
        payload = report.as_dict() if callable(getattr(report, "as_dict", None)) else {"exit_code": report.exit_code}
        if report.exit_code:
            raise GarDomainError(f"diagnostic failed (exit {report.exit_code})")
        return payload

    def _runtime_env(self, node: SystemNode, workspaces: dict[str, Workspace]) -> dict[str, str]:
        values: dict[str, str] = {}
        for name, source in node.runtime_env.items():
            if source.kind == "literal":
                values[name] = str(source.value)
            elif source.kind == "link_port":
                values[name] = str(self.topology.links[str(source.value)].port)
            else:
                peer = workspaces[str(source.value)]
                private_ip = peer.ec2.private_ip
                if not private_ip:
                    raise GarDomainError(f"node {source.value} のprivate_ipが未設定です")
                values[name] = private_ip
        return values

    def _resolved_links(
        self,
        workspaces: dict[str, Workspace],
        failures: list[dict[str, str]],
        *,
        resolve_private_ips: bool,
    ) -> list[dict[str, object]]:
        endpoints: list[dict[str, object]] = []
        for link in self.topology.links.values():
            entry: dict[str, object] = {
                "id": link.id,
                "from": link.from_node,
                "to": link.to_node,
                "protocol": link.protocol,
                "port": link.port,
                "firewall": self._firewall_plan(link),
                "diagnostic_target": self._diagnostic_target(link),
            }
            if not resolve_private_ips:
                entry["ok"] = True
                endpoints.append(entry)
                continue
            try:
                entry["from_private_ip"] = self._private_ip(link, "from", workspaces)
                entry["to_private_ip"] = self._private_ip(link, "to", workspaces)
                entry["ok"] = True
            except GarDomainError as error:
                entry["ok"] = False
                entry["error"] = str(error)
                failures.append({"node": "system", "action": "resolve-links", "error": str(error)})
            endpoints.append(entry)
        return endpoints

    @staticmethod
    def _transport_protocol(link: SystemLink) -> str:
        return link.protocol.rsplit("/", 1)[-1].lower()

    @classmethod
    def _firewall_plan(cls, link: SystemLink) -> list[dict[str, object]]:
        transport = cls._transport_protocol(link)
        return [
            {
                "node": link.from_node,
                "direction": "egress",
                "peer": link.to_node,
                "protocol": transport,
                "port": link.port,
            },
            {
                "node": link.to_node,
                "direction": "ingress",
                "peer": link.from_node,
                "protocol": transport,
                "port": link.port,
            },
        ]

    @classmethod
    def _diagnostic_target(cls, link: SystemLink) -> dict[str, object]:
        return {
            "from": link.from_node,
            "to": link.to_node,
            "protocol": cls._transport_protocol(link),
            "port": link.port,
        }

    def _private_ip(self, link: SystemLink, endpoint: str, workspaces: dict[str, Workspace]) -> str:
        node_id = link.from_node if endpoint == "from" else link.to_node
        workspace = workspaces.get(node_id)
        if workspace is None:
            raise GarDomainError(f"node {node_id} のworkspaceを解決できません")
        private_ip = workspace.ec2.private_ip
        if not private_ip:
            raise GarDomainError(f"node {node_id} のprivate_ipが未設定です")
        return private_ip
