"""Product workspace model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace_settings import (
    AdbSettings,
    DockerSettings,
    Ec2Settings,
    Esp32Settings,
    SelectedEnvironments,
    TargetSettings,
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
