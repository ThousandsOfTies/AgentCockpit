"""workspace が選んだ simulator backend から、実際に動かすオブジェクトを作る。

`gar setup` で選ばれた backend id（`local_docker` / `wokwi` など）を見て、
対応する実装とアクセス経路を組み立てるだけの層。実処理は各実装が持つ。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts.gar_lib.access.aws import AwsCliChannel
from scripts.gar_lib.access.docker import (
    DockerCliChannel,
    DockerCommandChannel,
    DockerFileChannel,
)
from scripts.gar_lib.access.local import LocalProcessChannel
from scripts.gar_lib.access.ssh import ScpFileChannel, SshCommandChannel
from scripts.gar_lib.config import PROJECT_ROOT
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.aws_ec2 import AwsEc2SimulationHostController
from scripts.gar_lib.simulation.aws_ssm import AwsSsmSimulationEnvironment
from scripts.gar_lib.simulation.control import (
    LinuxBridgeHardwareControl,
    SimulationHardwareControl,
)
from scripts.gar_lib.simulation.docker_host import (
    BACKEND_ID,
    DEFAULT_CONTAINER,
    DockerSimulationHostController,
)
from scripts.gar_lib.simulation.docker_spec import DockerHostSpec, docker_host_spec
from scripts.gar_lib.simulation.environment import SimulationEnvironment
from scripts.gar_lib.simulation.esp32_qemu import Esp32QemuSimulationEnvironment
from scripts.gar_lib.simulation.host import SimulationHostController
from scripts.gar_lib.simulation.linux import LinuxSystemdCommandBuilder
from scripts.gar_lib.simulation.linux_systemd import LinuxSystemdSimulationEnvironment
from scripts.gar_lib.simulation.mujoco import (
    MujocoBridgeHardwareControl,
    MujocoSimulationEnvironment,
)
from scripts.gar_lib.simulation.renode import RenodeSimulationEnvironment
from scripts.gar_lib.simulation.ssh_config import SshConfigHostAddressUpdater
from scripts.gar_lib.simulation.wokwi import WokwiSimulationEnvironment
from scripts.gar_lib.target.manifest import active_target_manifest
from scripts.gar_lib.tools_repository import gar_tools_root

LOCAL_DOCKER = "local_docker"


def selected_simulator(workspace: Workspace) -> str | None:
    return workspace.selected_environments.get("simulator")


def simulation_environment_for(workspace: Workspace) -> SimulationEnvironment:
    """simulation runtime（stub / bridge）を操作するオブジェクトを作る。"""

    backend = selected_simulator(workspace)

    if backend == LOCAL_DOCKER:
        container = _container_name(workspace)
        return LinuxSystemdSimulationEnvironment(
            command_channel=DockerCommandChannel(container),
            file_channel=DockerFileChannel(container),
            command_builder=LinuxSystemdCommandBuilder(),
            runtime_host=container,
        )

    if backend == "ssh_remote":
        host = _ec2_host(workspace)
        return LinuxSystemdSimulationEnvironment(
            command_channel=SshCommandChannel(host),
            file_channel=ScpFileChannel(host),
            command_builder=LinuxSystemdCommandBuilder(),
            runtime_host=host,
        )

    if backend == "wokwi":
        return WokwiSimulationEnvironment(_wokwi_project_dir(workspace), LocalProcessChannel())

    if backend == "mujoco":
        return MujocoSimulationEnvironment(process_channel=LocalProcessChannel())

    if backend == "renode_mcu":
        return RenodeSimulationEnvironment(process_channel=LocalProcessChannel())

    if backend == "esp32_qemu_firmware":
        return Esp32QemuSimulationEnvironment(process_channel=LocalProcessChannel())

    if backend == "aws_ssm":
        instance_id, region = _ssm_settings(workspace)
        return AwsSsmSimulationEnvironment(aws=AwsCliChannel(region), instance_id=instance_id)

    raise GarDomainError(f"simulation environmentはまだ未対応です: {backend or '(未設定)'}")


def simulation_host_for(workspace: Workspace) -> SimulationHostController:
    """simulation を載せる host（container / EC2）を操作するオブジェクトを作る。"""

    if selected_simulator(workspace) == LOCAL_DOCKER:
        settings = workspace.docker
        container = _container_name(workspace)
        repository_path = settings.get("repo_dir")
        return DockerSimulationHostController(
            container=container,
            spec=docker_spec_for(settings),
            docker=DockerCliChannel(),
            repository_channel=DockerCommandChannel(container),
            repository_path=repository_path if isinstance(repository_path, str) else None,
        )

    instance_id = workspace.ec2.get("instance_id")
    region = workspace.ec2.get("region")
    host = workspace.ec2.get("host")
    missing = [
        name
        for name, value in (("host", host), ("instance_id", instance_id), ("region", region))
        if not isinstance(value, str) or not value
    ]
    if missing:
        raise GarDomainError(
            f"simulation host設定が不足しています ({', '.join(missing)}): {workspace.name}"
        )

    repository_path = workspace.ec2.get("repo_dir")
    return AwsEc2SimulationHostController(
        host=host,
        instance_id=instance_id,
        region=region,
        aws=AwsCliChannel(region),
        address_updater=SshConfigHostAddressUpdater(),
        repository_channel=SshCommandChannel(host),
        repository_path=repository_path if isinstance(repository_path, str) else None,
    )


def hardware_control_for(workspace: Workspace) -> SimulationHardwareControl:
    """virtual H/W を操作する control plane のオブジェクトを作る。"""

    backend = selected_simulator(workspace)

    if backend == LOCAL_DOCKER:
        container = _container_name(workspace)
        return LinuxBridgeHardwareControl(
            DockerCommandChannel(container),
            LinuxSystemdCommandBuilder(),
            host=container,
        )

    if backend == "ssh_remote":
        host = _ec2_host(workspace)
        return LinuxBridgeHardwareControl(
            SshCommandChannel(host),
            LinuxSystemdCommandBuilder(),
            host=host,
        )

    if backend == "mujoco":
        return MujocoBridgeHardwareControl()

    raise GarDomainError(
        f"hardware controlはこのsimulation environmentに未対応です: {backend or '(未設定)'}"
    )


def docker_spec_for(settings: Mapping[str, Any]) -> DockerHostSpec:
    """container の形は target 定義が決め、workspace 設定は上書きだけを担当する。"""

    manifest = active_target_manifest()
    spec = (
        docker_host_spec(manifest.simulation_settings(BACKEND_ID), root=gar_tools_root())
        if manifest is not None
        else None
    )

    image = settings.get("image")
    port = settings.get("bridge_port")
    override_port = isinstance(port, int) and not isinstance(port, bool)
    if spec is None:
        if not isinstance(image, str) or not image:
            raise GarDomainError(
                "simulation container の image を決められません。"
                "gar setup で target を選ぶか、workspace の docker.image を設定してください"
            )
        spec = DockerHostSpec(image=image)

    return DockerHostSpec(
        image=image if isinstance(image, str) and image else spec.image,
        run_options=spec.run_options,
        init_command=spec.init_command,
        bridge_port=port if override_port else spec.bridge_port,
        build_context=spec.build_context,
    )


def _container_name(workspace: Workspace) -> str:
    container = workspace.docker.get("container")
    return container if isinstance(container, str) and container else DEFAULT_CONTAINER


def _ec2_host(workspace: Workspace) -> str:
    host = workspace.ec2.get("host")
    if not isinstance(host, str) or not host:
        raise GarDomainError(f"simulation hostが未設定です: {workspace.name}")
    return host


def _ssm_settings(workspace: Workspace) -> tuple[str, str]:
    instance_id = workspace.ec2.get("instance_id")
    region = workspace.ec2.get("region")
    missing = [
        name
        for name, value in (("instance_id", instance_id), ("region", region))
        if not isinstance(value, str) or not value
    ]
    if missing:
        raise GarDomainError(
            f"AWS SSM設定が不足しています ({', '.join(missing)}): {workspace.name}"
        )
    return instance_id, region


def _wokwi_project_dir(workspace: Workspace) -> Path:
    configured = os.environ.get("GAR_WOKWI_PROJECT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if workspace.connection_type == "local":
        return workspace.local_root / ".gar" / "wokwi" / "m5stackc"
    return PROJECT_ROOT / ".gar" / "wokwi" / workspace.id
