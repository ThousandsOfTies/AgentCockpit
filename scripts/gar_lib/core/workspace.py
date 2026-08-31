"""Product workspace model."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path

from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace_settings import (
    AdbSettings,
    BuildSettings,
    DockerSettings,
    Ec2Settings,
    Esp32Settings,
    SelectedEnvironments,
    SimulationHostSettings,
    TargetSettings,
    VirtualBoxSettings,
    WorkspaceConnection,
)


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    branch: str
    connection: WorkspaceConnection
    selected_environments: SelectedEnvironments = field(default_factory=SelectedEnvironments)
    selected_target: str | None = None
    hardware_dir: Path | None = None
    build: BuildSettings = field(default_factory=BuildSettings)
    simulation_host: SimulationHostSettings = field(default_factory=SimulationHostSettings)
    virtualbox: VirtualBoxSettings = field(default_factory=VirtualBoxSettings)
    ec2: Ec2Settings = field(default_factory=Ec2Settings)
    docker: DockerSettings = field(default_factory=DockerSettings)
    target: TargetSettings = field(default_factory=TargetSettings)
    adb: AdbSettings = field(default_factory=AdbSettings)
    esp32: Esp32Settings = field(default_factory=Esp32Settings)

    def __post_init__(self) -> None:
        # ``Workspace`` remains friendly to callers loading JSON mappings, but
        # every resolved instance carries concrete settings objects afterwards.
        object.__setattr__(self, "connection", WorkspaceConnection.from_value(self.connection))
        object.__setattr__(
            self,
            "selected_environments",
            SelectedEnvironments.from_value(self.selected_environments),
        )
        object.__setattr__(self, "build", BuildSettings.from_value(self.build))
        object.__setattr__(
            self,
            "simulation_host",
            SimulationHostSettings.from_value(self.simulation_host),
        )
        object.__setattr__(self, "virtualbox", VirtualBoxSettings.from_value(self.virtualbox))
        object.__setattr__(self, "ec2", Ec2Settings.from_value(self.ec2))
        object.__setattr__(self, "docker", DockerSettings.from_value(self.docker))
        object.__setattr__(self, "target", TargetSettings.from_value(self.target))
        object.__setattr__(self, "adb", AdbSettings.from_value(self.adb))
        object.__setattr__(self, "esp32", Esp32Settings.from_value(self.esp32))

    @property
    def connection_type(self) -> str:
        return self.connection.type

    @property
    def local_root(self) -> Path:
        if self.connection_type != "local":
            raise GarDomainError(f"workspace は local 接続ではありません: {self.name}")
        value = self.connection.path
        if not value:
            raise GarDomainError(f"workspace の local path が未設定です: {self.name}")
        return Path(value).expanduser().resolve()

    @property
    def remote_root(self) -> str:
        value = self.connection.path
        if not value:
            raise GarDomainError(f"workspace の remote path が未設定です: {self.name}")
        return value.rstrip("/")

    @property
    def codespace_name(self) -> str:
        if self.connection_type != "codespaces":
            raise GarDomainError(f"workspace は Codespaces 接続ではありません: {self.name}")
        value = self.connection.codespace
        if not value:
            raise GarDomainError(f"workspace の Codespaces 名が未設定です: {self.name}")
        return value

    @property
    def simulation_architecture(self) -> str | None:
        simulator = self.selected_environments.simulator
        if simulator == "local_docker":
            return normalize_linux_architecture(self.docker.arch or native_linux_architecture())
        if simulator != "ssh_remote":
            return None
        provider = self.simulation_host_provider
        configured = self.simulation_host.arch if self._generic_simulation_host_matches(provider) else None
        if configured is None and provider == "aws_ec2":
            configured = self.ec2.arch
        if configured:
            return normalize_linux_architecture(configured)
        if provider == "virtualbox":
            return "x86_64"
        return "aarch64"

    @property
    def simulation_host_provider(self) -> str | None:
        selected = self.selected_environments.simulation_host
        if selected:
            return selected
        if self.simulation_host.provider:
            return self.simulation_host.provider
        if self.virtualbox.vm:
            return "virtualbox"
        if any(
            (
                self.ec2.host,
                self.ec2.instance_id,
                self.ec2.private_ip,
                self.ec2.region,
                self.ec2.repo_dir,
                self.ec2.identity_file,
                self.ec2.arch,
            )
        ):
            return "aws_ec2"
        return None

    @property
    def simulation_ssh_host(self) -> str | None:
        provider = self.simulation_host_provider
        if self._generic_simulation_host_matches(provider) and self.simulation_host.host:
            return self.simulation_host.host
        return self.ec2.host if provider == "aws_ec2" else None

    @property
    def simulation_repository_dir(self) -> str | None:
        provider = self.simulation_host_provider
        if self._generic_simulation_host_matches(provider) and self.simulation_host.repo_dir:
            return self.simulation_host.repo_dir
        return self.ec2.repo_dir if provider == "aws_ec2" else None

    @property
    def simulation_private_ip(self) -> str | None:
        provider = self.simulation_host_provider
        if self._generic_simulation_host_matches(provider) and self.simulation_host.private_ip:
            return self.simulation_host.private_ip
        return self.ec2.private_ip if provider == "aws_ec2" else None

    @property
    def simulation_bridge_port(self) -> int | None:
        if self.selected_environments.simulator == "local_docker":
            return self.docker.bridge_port
        provider = self.simulation_host_provider
        if self._generic_simulation_host_matches(provider):
            return self.simulation_host.bridge_port
        return None

    def _generic_simulation_host_matches(self, provider: str | None) -> bool:
        configured_provider = self.simulation_host.provider
        return configured_provider is None or configured_provider == provider


def native_linux_architecture() -> str:
    return normalize_linux_architecture(platform.machine())


def normalize_linux_architecture(value: str) -> str:
    value = value.lower()
    return {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "aarch64",
    }.get(value, value)
