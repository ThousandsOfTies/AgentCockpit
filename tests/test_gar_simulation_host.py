from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.access.aws import AwsCliChannel
from scripts.gar_lib.access.channel import AccessResult
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.composition import (
    simulation_environment_for,
    simulation_host_for,
)
from scripts.gar_lib.simulation.host.aws_ec2 import AwsEc2SimulationHostController
from scripts.gar_lib.simulation.host.ssh_config import SshConfigHostAddressUpdater
from scripts.gar_lib.simulation.host.virtualbox import VirtualBoxSimulationHostController


class GarSimulationHostTest(unittest.TestCase):
    def test_virtualbox_controller_starts_powered_off_vm_and_reports_running_state(self) -> None:
        virtualbox = mock.Mock()
        virtualbox.run.side_effect = [
            AccessResult(
                ("VBoxManage",),
                0,
                'VMState="poweroff"\nVMStateChangeTime="2026-08-31T00:00:00Z"\n',
            ),
            AccessResult(("VBoxManage",), 0),
            AccessResult(("VBoxManage",), 0, 'VMState="running"\n'),
        ]
        controller = VirtualBoxSimulationHostController(
            vm="GAR Ubuntu Sim",
            host="gar-sim-local",
            virtualbox=virtualbox,
            repository_channel=mock.Mock(),
        )

        result = controller.start()

        self.assertTrue(result.state.running)
        self.assertEqual("virtualbox", result.state.backend)
        self.assertEqual("GAR Ubuntu Sim", result.state.id)
        self.assertFalse(result.address_updated)
        self.assertEqual(
            [
                mock.call(("showvminfo", "GAR Ubuntu Sim", "--machinereadable")),
                mock.call(("startvm", "GAR Ubuntu Sim", "--type", "headless")),
                mock.call(("showvminfo", "GAR Ubuntu Sim", "--machinereadable")),
            ],
            virtualbox.run.call_args_list,
        )

    def test_virtualbox_controller_updates_repository_over_shared_ssh_channel(self) -> None:
        virtualbox = mock.Mock()
        virtualbox.run.return_value = AccessResult(("VBoxManage",), 0, 'VMState="running"\n')
        repository = mock.Mock()
        repository.run.return_value = AccessResult(("ssh",), 0)
        controller = VirtualBoxSimulationHostController(
            vm="GAR Ubuntu Sim",
            host="gar-sim-local",
            virtualbox=virtualbox,
            repository_channel=repository,
            repository_path="/srv/simulation repo",
        )

        result = controller.start(update_repository=True)

        self.assertTrue(result.repository_updated)
        repository.run.assert_called_once_with("cd '/srv/simulation repo' && git pull --ff-only")

    def test_virtualbox_controller_requests_acpi_shutdown_for_running_vm(self) -> None:
        virtualbox = mock.Mock()
        virtualbox.run.side_effect = [
            AccessResult(("VBoxManage",), 0, 'VMState="running"\n'),
            AccessResult(("VBoxManage",), 0),
        ]
        controller = VirtualBoxSimulationHostController(
            vm="GAR Ubuntu Sim",
            host="gar-sim-local",
            virtualbox=virtualbox,
            repository_channel=mock.Mock(),
        )

        controller.stop()

        virtualbox.run.assert_called_with(("controlvm", "GAR Ubuntu Sim", "acpipowerbutton"))

    def test_virtualbox_controller_resumes_paused_vm(self) -> None:
        virtualbox = mock.Mock()
        virtualbox.run.side_effect = [
            AccessResult(("VBoxManage",), 0, 'VMState="paused"\n'),
            AccessResult(("VBoxManage",), 0),
            AccessResult(("VBoxManage",), 0, 'VMState="running"\n'),
        ]
        controller = VirtualBoxSimulationHostController(
            vm="GAR Ubuntu Sim",
            host="gar-sim-local",
            virtualbox=virtualbox,
            repository_channel=mock.Mock(),
        )

        result = controller.start()

        self.assertTrue(result.state.running)
        self.assertEqual(
            mock.call(("controlvm", "GAR Ubuntu Sim", "resume")),
            virtualbox.run.call_args_list[1],
        )

    def test_aws_channel_classifies_expired_session_without_host_decisions(self) -> None:
        completed = mock.Mock(
            returncode=255,
            stdout="",
            stderr="Your session has expired. Please reauthenticate using 'aws login'.",
        )
        with (
            mock.patch("scripts.gar_lib.access.aws.shutil.which", return_value="/usr/bin/aws"),
            mock.patch("scripts.gar_lib.access.aws.subprocess.run", return_value=completed),
        ):
            with self.assertRaises(AccessConnectionError) as raised:
                AwsCliChannel("ap-northeast-1").run(("ec2", "describe-instances"))

        self.assertEqual("aws", raised.exception.channel)
        self.assertEqual("authentication", raised.exception.reason)

    def test_ssh_config_updater_only_manages_host_address(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config"
            path.write_text(
                "Host sim-host\n    User ubuntu\n\nHost another-host\n    HostName old\n",
                encoding="utf-8",
            )

            updated = SshConfigHostAddressUpdater(path).update("sim-host", "203.0.113.5")

            self.assertTrue(updated)
            contents = path.read_text(encoding="utf-8")
            self.assertIn("Host sim-host\n    HostName 203.0.113.5\n    User ubuntu", contents)
            self.assertIn("Host another-host\n    HostName old", contents)

    def test_ec2_controller_composes_aws_ssh_config_and_repository_channels(self) -> None:
        aws = mock.Mock()
        aws.run.side_effect = [
            AccessResult(("aws",), 0),
            AccessResult(("aws",), 0),
            AccessResult(("aws",), 0, "running\n"),
            AccessResult(("aws",), 0, "203.0.113.5\n"),
        ]
        address_updater = mock.Mock()
        address_updater.update.return_value = True
        repository = mock.Mock()
        repository.run.return_value = AccessResult(("ssh",), 0)
        controller = AwsEc2SimulationHostController(
            host="sim-host",
            instance_id="i-test",
            region="ap-northeast-1",
            aws=aws,
            address_updater=address_updater,
            repository_channel=repository,
            repository_path="/srv/simulation repo",
        )

        result = controller.start(update_address=True, update_repository=True)

        self.assertTrue(result.state.running)
        self.assertEqual("203.0.113.5", result.state.address)
        self.assertEqual("aws_ec2", result.state.backend)
        self.assertTrue(result.address_updated)
        self.assertTrue(result.repository_updated)
        address_updater.update.assert_called_once_with("sim-host", "203.0.113.5")
        repository.run.assert_called_once_with("cd '/srv/simulation repo' && git pull --ff-only")
        self.assertIn("start-instances", aws.run.call_args_list[0].args[0])
        self.assertIn("instance-running", aws.run.call_args_list[1].args[0])

    def test_ec2_controller_reports_non_authentication_aws_failure_as_domain_error(self) -> None:
        aws = mock.Mock()
        aws.run.return_value = AccessResult(("aws",), 2, "", "access denied")
        controller = AwsEc2SimulationHostController(
            host="sim-host",
            instance_id="i-test",
            region="ap-northeast-1",
            aws=aws,
            address_updater=mock.Mock(),
            repository_channel=mock.Mock(),
        )

        with self.assertRaises(GarDomainError):
            controller.stop()

    def test_ec2_start_does_not_require_public_ip_when_ssh_update_is_disabled(self) -> None:
        aws = mock.Mock()
        aws.run.side_effect = [
            AccessResult(("aws",), 0),
            AccessResult(("aws",), 0),
            AccessResult(("aws",), 0, "running\n"),
            AccessResult(("aws",), 0, "None\n"),
        ]
        address_updater = mock.Mock()
        controller = AwsEc2SimulationHostController(
            host="sim-host",
            instance_id="i-private",
            region="ap-northeast-1",
            aws=aws,
            address_updater=address_updater,
            repository_channel=mock.Mock(),
        )

        result = controller.start(update_address=False)

        self.assertTrue(result.state.running)
        self.assertIsNone(result.state.address)
        self.assertFalse(result.address_updated)
        address_updater.update.assert_not_called()

    def test_resolver_builds_controller_from_workspace_ec2_settings(self) -> None:
        workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={"simulator": "ssh_remote"},
            ec2={
                "host": "sim-host",
                "instance_id": "i-test",
                "region": "ap-northeast-1",
            },
        )

        controller = simulation_host_for(workspace)

        self.assertIsInstance(controller, AwsEc2SimulationHostController)
        self.assertEqual("i-test", controller.instance_id)

    def test_resolver_builds_virtualbox_controller_from_generic_sim_host_settings(self) -> None:
        workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={
                "simulator": "ssh_remote",
                "simulation_host": "virtualbox",
            },
            simulation_host={
                "provider": "virtualbox",
                "host": "gar-sim-local",
                "repo_dir": "/srv/gar",
            },
            virtualbox={"vm": "GAR Ubuntu Sim"},
        )

        controller = simulation_host_for(workspace)
        environment = simulation_environment_for(workspace)

        self.assertIsInstance(controller, VirtualBoxSimulationHostController)
        self.assertEqual("GAR Ubuntu Sim", controller.vm)
        self.assertEqual("gar-sim-local", controller.host)
        self.assertEqual("/srv/gar", controller.repository_path)
        self.assertEqual("gar-sim-local", environment.session_host)

    def test_virtualbox_resolver_does_not_fall_back_to_stale_ec2_alias(self) -> None:
        workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={
                "simulator": "ssh_remote",
                "simulation_host": "virtualbox",
            },
            simulation_host={"provider": "aws_ec2", "host": "stale-aws"},
            virtualbox={"vm": "GAR Ubuntu Sim"},
            ec2={"host": "legacy-aws"},
        )

        with self.assertRaisesRegex(GarDomainError, "SSH alias"):
            simulation_environment_for(workspace)

    def test_ssh_runtime_exposes_an_explicit_session_host(self) -> None:
        workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={"simulator": "ssh_remote"},
            ec2={"host": "sim-host"},
        )

        environment = simulation_environment_for(workspace)

        self.assertEqual("sim-host", environment.session_host)

    def test_resolver_rejects_incomplete_host_configuration(self) -> None:
        workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={"simulator": "ssh_remote"},
            ec2={"host": "sim-host"},
        )

        with self.assertRaisesRegex(GarDomainError, "instance_id, region"):
            simulation_host_for(workspace)

    def test_resolver_does_not_guess_ec2_when_simulator_is_unselected(self) -> None:
        workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            ec2={
                "host": "sim-host",
                "instance_id": "i-test",
                "region": "ap-northeast-1",
            },
        )

        with self.assertRaisesRegex(GarDomainError, "未設定"):
            simulation_host_for(workspace)
