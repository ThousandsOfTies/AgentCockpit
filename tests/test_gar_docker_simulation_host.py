from __future__ import annotations

import contextlib
import unittest
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

from scripts.gar_lib.access.channel import AccessResult
from scripts.gar_lib.access.docker import (
    DockerCliChannel,
    DockerCommandChannel,
    DockerFileChannel,
)
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.composition import (
    hardware_control_for,
    simulation_environment_for,
    simulation_host_for,
)
from scripts.gar_lib.simulation.hardware.control import LinuxBridgeHardwareControl
from scripts.gar_lib.simulation.host.docker import (
    ABSENT_STATE,
    DockerSimulationHostController,
)
from scripts.gar_lib.simulation.host.docker_spec import DockerHostSpec, docker_host_spec
from scripts.gar_lib.simulation.runtime.linux_systemd import LinuxSystemdSimulationEnvironment
from scripts.gar_lib.target.manifest import TargetManifest

LINUX_DEVICE_DOCKER = {
    "image": "gar-linux-device:latest",
    "buildContext": "targets/linux-device",
    "bridgePort": 8080,
    "init": ["/sbin/init"],
    "privileged": True,
    "hostCgroups": True,
    "tmpfs": ["/run", "/run/lock"],
    "mounts": ["/sys/fs/cgroup:/sys/fs/cgroup:rw", "/sys/kernel/config:/sys/kernel/config"],
    "devices": ["/dev/fuse", "/dev/cuse"],
}


def linux_device_manifest() -> TargetManifest:
    return TargetManifest(
        id="linux-device",
        display_name="Linux device",
        description="linux device",
        tools_root="targets/linux-device",
        default_backends={"simulator": "local_docker"},
        backend_notes={},
        simulation={"docker": dict(LINUX_DEVICE_DOCKER)},
    )


@contextlib.contextmanager
def target_manifest(manifest: TargetManifest | None) -> Iterator[None]:
    """container の形を決める target 定義を差し替える。"""

    with mock.patch(
        "scripts.gar_lib.simulation.composition.active_target_manifest", return_value=manifest
    ):
        yield


def docker_workspace(**docker: object) -> Workspace:
    return Workspace(
        id="ws",
        name="Local/Product",
        branch="Product",
        connection={"type": "local", "path": "/tmp/product"},
        selected_environments={"simulator": "local_docker"},
        docker=docker,
    )


class DockerAccessChannelTest(unittest.TestCase):
    def test_command_channel_wraps_shell_command_for_container(self) -> None:
        completed = mock.Mock(returncode=0, stdout="ok", stderr="")
        with (
            mock.patch("scripts.gar_lib.access.docker.shutil.which", return_value="/usr/bin/docker"),
            mock.patch(
                "scripts.gar_lib.access.docker.subprocess.run", return_value=completed
            ) as run,
        ):
            result = DockerCommandChannel("gar-sim").run("systemctl is-active gar-bridge")

        self.assertEqual(0, result.returncode)
        self.assertEqual(
            (
                "/usr/bin/docker",
                "exec",
                "-i",
                "gar-sim",
                "bash",
                "-lc",
                "systemctl is-active gar-bridge",
            ),
            run.call_args.args[0],
        )

    def test_command_channel_reports_stopped_container_as_connection_failure(self) -> None:
        completed = mock.Mock(
            returncode=125,
            stdout="",
            stderr="Error response from daemon: Container gar-sim is not running",
        )
        with (
            mock.patch("scripts.gar_lib.access.docker.shutil.which", return_value="/usr/bin/docker"),
            mock.patch("scripts.gar_lib.access.docker.subprocess.run", return_value=completed),
        ):
            with self.assertRaises(AccessConnectionError) as raised:
                DockerCommandChannel("gar-sim").run("true")

        self.assertEqual("docker", raised.exception.channel)
        self.assertEqual("gar-sim", raised.exception.endpoint)
        self.assertEqual("container", raised.exception.reason)

    def test_cli_channel_reports_stopped_daemon_as_connection_failure(self) -> None:
        completed = mock.Mock(
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock.",
        )
        with (
            mock.patch("scripts.gar_lib.access.docker.shutil.which", return_value="/usr/bin/docker"),
            mock.patch("scripts.gar_lib.access.docker.subprocess.run", return_value=completed),
        ):
            with self.assertRaises(AccessConnectionError) as raised:
                DockerCliChannel().run(("ps",))

        self.assertEqual("daemon", raised.exception.reason)

    def test_missing_docker_executable_is_a_domain_error(self) -> None:
        with mock.patch("scripts.gar_lib.access.docker.shutil.which", return_value=None):
            with self.assertRaisesRegex(GarDomainError, "docker"):
                DockerCliChannel().run(("ps",))

    def test_file_channel_pushes_through_docker_cp(self) -> None:
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        with (
            mock.patch("scripts.gar_lib.access.docker.shutil.which", return_value="/usr/bin/docker"),
            mock.patch(
                "scripts.gar_lib.access.docker.subprocess.run", return_value=completed
            ) as run,
        ):
            DockerFileChannel("gar-sim").push(Path("/tmp/bundle"), "/tmp/staged")

        self.assertEqual(
            ("/usr/bin/docker", "cp", "/tmp/bundle", "gar-sim:/tmp/staged"),
            run.call_args.args[0],
        )


class DockerSimulationHostControllerTest(unittest.TestCase):
    def controller(self, docker: mock.Mock) -> DockerSimulationHostController:
        return DockerSimulationHostController(
            container="gar-sim",
            spec=docker_host_spec(LINUX_DEVICE_DOCKER),
            docker=docker,
            repository_channel=mock.Mock(),
        )

    def test_status_reports_absent_container_without_raising(self) -> None:
        docker = mock.Mock()
        docker.run.return_value = AccessResult(
            ("docker",), 1, "", "Error: No such object: gar-sim"
        )

        state = self.controller(docker).status()

        self.assertEqual(ABSENT_STATE, state.state)
        self.assertFalse(state.running)
        self.assertIsNone(state.address)
        self.assertEqual("docker", state.backend)

    def test_start_creates_container_when_absent(self) -> None:
        docker = mock.Mock()
        docker.run.side_effect = [
            AccessResult(("docker",), 1, "", "No such object: gar-sim"),
            AccessResult(("docker",), 0, "sha256:abc\n"),
            AccessResult(("docker",), 0, "abc123\n"),
            AccessResult(("docker",), 0, "running\n"),
        ]

        result = self.controller(docker).start()

        self.assertTrue(result.state.running)
        self.assertEqual("127.0.0.1", result.state.address)
        self.assertFalse(result.address_updated)
        created = docker.run.call_args_list[2].args[0]
        self.assertEqual("run", created[0])
        self.assertIn("--privileged", created)
        self.assertIn("/sys/kernel/config:/sys/kernel/config", created)
        self.assertIn("/dev/cuse", created)
        self.assertIn("8080:8080", created)
        self.assertEqual("/sbin/init", created[-1])

    def test_start_builds_image_from_target_build_context_when_missing(self) -> None:
        docker = mock.Mock()
        docker.run.side_effect = [
            AccessResult(("docker",), 1, "", "No such object: gar-sim"),
            AccessResult(("docker",), 1, "", "No such image"),
            AccessResult(("docker",), 0, "built\n"),
            AccessResult(("docker",), 0, "abc123\n"),
            AccessResult(("docker",), 0, "running\n"),
        ]

        self.controller(docker).start()

        self.assertEqual(
            ("build", "--tag", "gar-linux-device:latest", "targets/linux-device"),
            docker.run.call_args_list[2].args[0],
        )

    def test_start_requires_a_build_context_when_image_is_missing(self) -> None:
        docker = mock.Mock()
        docker.run.side_effect = [
            AccessResult(("docker",), 1, "", "No such object: gar-sim"),
            AccessResult(("docker",), 1, "", "No such image"),
        ]
        controller = DockerSimulationHostController(
            container="gar-sim",
            spec=DockerHostSpec(image="missing:latest"),
            docker=docker,
            repository_channel=mock.Mock(),
        )

        with self.assertRaisesRegex(GarDomainError, "missing:latest"):
            controller.start()

    def test_start_restarts_existing_stopped_container(self) -> None:
        docker = mock.Mock()
        docker.run.side_effect = [
            AccessResult(("docker",), 0, "exited\n"),
            AccessResult(("docker",), 0, "gar-sim\n"),
            AccessResult(("docker",), 0, "running\n"),
        ]

        result = self.controller(docker).start()

        self.assertTrue(result.state.running)
        self.assertEqual(("start", "gar-sim"), docker.run.call_args_list[1].args[0])

    def test_stop_rejects_absent_container(self) -> None:
        docker = mock.Mock()
        docker.run.return_value = AccessResult(("docker",), 1, "", "No such object: gar-sim")

        with self.assertRaisesRegex(GarDomainError, "gar-sim"):
            self.controller(docker).stop()


class DockerBackendTest(unittest.TestCase):
    def test_host_takes_container_shape_from_target_definition(self) -> None:
        with target_manifest(linux_device_manifest()):
            controller = simulation_host_for(docker_workspace())

        self.assertIsInstance(controller, DockerSimulationHostController)
        self.assertEqual("gar-sim", controller.container)
        self.assertEqual("gar-linux-device:latest", controller.image)
        self.assertIn("--device", controller.spec.run_options)
        self.assertIn("/dev/cuse", controller.spec.run_options)
        self.assertEqual(("/sbin/init",), controller.spec.init_command)
        self.assertTrue(controller.spec.build_context.endswith("targets/linux-device"))

    def test_host_honours_workspace_docker_settings(self) -> None:
        workspace = docker_workspace(container="poc", image="poc:dev", bridge_port=9090)

        with target_manifest(linux_device_manifest()):
            controller = simulation_host_for(workspace)

        self.assertEqual("poc", controller.container)
        self.assertEqual("poc:dev", controller.image)
        self.assertEqual(9090, controller.bridge_port)
        self.assertIn("--privileged", controller.spec.run_options)

    def test_host_requires_an_image_when_target_is_unknown(self) -> None:
        with target_manifest(None), self.assertRaisesRegex(GarDomainError, "image"):
            simulation_host_for(docker_workspace())

    def test_host_falls_back_to_workspace_image_without_target(self) -> None:
        with target_manifest(None):
            controller = simulation_host_for(docker_workspace(image="poc:dev"))

        self.assertEqual("poc:dev", controller.image)
        self.assertEqual((), controller.spec.run_options)

    def test_environment_reuses_linux_systemd_runtime(self) -> None:
        environment = simulation_environment_for(docker_workspace())

        self.assertIsInstance(environment, LinuxSystemdSimulationEnvironment)
        self.assertIsInstance(environment.command_channel, DockerCommandChannel)
        self.assertIsInstance(environment.file_channel, DockerFileChannel)

    def test_hardware_control_reuses_linux_bridge(self) -> None:
        control = hardware_control_for(docker_workspace())

        self.assertIsInstance(control, LinuxBridgeHardwareControl)
        self.assertIsInstance(control.command_channel, DockerCommandChannel)


if __name__ == "__main__":
    unittest.main()
