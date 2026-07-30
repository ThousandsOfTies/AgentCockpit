from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from unittest import mock

from scripts.gar_lib.api import Gar
from scripts.gar_lib.cli import main
from scripts.gar_lib.core.errors import AccessConnectionError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.diagnostic import SimulationDiagnostic
from scripts.gar_lib.simulation.host import SimulationHostState


def cli_args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json_output": False, **values})


class GarSimulationLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            ec2={"region": "ap-northeast-1", "host": "sim-host"},
        )

    def test_host_aws_authentication_failure_uses_terminal_bridge_recovery(self) -> None:
        controller = mock.Mock()
        controller.status.side_effect = AccessConnectionError(
            channel="aws",
            endpoint="ap-northeast-1",
            reason="authentication",
            returncode=255,
        )
        with (
            mock.patch("scripts.gar_lib.commands.sim.workspace_for", return_value=self.workspace),
            mock.patch(
                "scripts.gar_lib.api.simulation_host_for", return_value=controller
            ),
            mock.patch(
                "scripts.gar_lib.commands.sim.run_terminal_run_command", return_value=0
            ) as terminal_request,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = main(["sim", "host", "status", "--workspace", "Local/Product"])

        self.assertEqual(1, result)
        self.assertEqual(
            "aws login --remote --region ap-northeast-1",
            terminal_request.call_args.kwargs["command_text"],
        )

    def test_host_status_builds_controller_and_serializes_result(self) -> None:
        controller = mock.Mock()
        controller.status.return_value = SimulationHostState(
            host="sim-host",
            backend="aws_ec2",
            id="i-test",
            state="running",
            address="203.0.113.5",
            details={"region": "ap-northeast-1"},
        )

        output = io.StringIO()
        with (
            mock.patch(
                "scripts.gar_lib.api.simulation_host_for", return_value=controller
            ) as host_for,
            contextlib.redirect_stdout(output),
        ):
            exit_code = Gar(self.workspace).sim.host.status(json_output=True)

        payload = json.loads(output.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("aws_ec2", payload["backend"])
        self.assertEqual("i-test", payload["id"])
        self.assertTrue(payload["running"])
        host_for.assert_called_once_with(self.workspace)
        controller.status.assert_called_once_with()

    def test_diag_builds_environment_and_loads_hardware(self) -> None:
        environment = mock.Mock()
        environment.diag.return_value = SimulationDiagnostic(
            processes=[{"pid": 123, "cmd": "bridge.py"}],
            devices={"/dev/i2c-1": True},
            api={"ready": True},
            ok=True,
        )

        output = io.StringIO()
        with (
            mock.patch(
                "scripts.gar_lib.api.simulation_environment_for",
                return_value=environment,
            ),
            mock.patch("scripts.gar_lib.api.load_hw_definition", return_value={}),
            contextlib.redirect_stdout(output),
        ):
            Gar(self.workspace).sim.runtime.diag(json_output=True)

        self.assertEqual("sim-host", json.loads(output.getvalue())["host"])
        environment.diag.assert_called_once_with({})

    def test_status_checks_runtime_even_when_session_is_stopped(self) -> None:
        environment = mock.Mock()
        environment.runtime_host = "sim-host"
        environment.status.return_value = 0
        sessions = mock.Mock()
        sessions.status.return_value = 1

        with (
            mock.patch(
                "scripts.gar_lib.api.simulation_environment_for",
                return_value=environment,
            ),
            mock.patch("scripts.gar_lib.api.load_hw_definition", return_value={}),
            mock.patch(
                "scripts.gar_lib.api.VsCodeSimulationSessionManager",
                return_value=sessions,
            ),
        ):
            exit_code = Gar(self.workspace).sim.runtime.status()

        self.assertEqual(1, exit_code)
        environment.status.assert_called_once_with({})

    def test_start_can_skip_session_management(self) -> None:
        environment = mock.Mock()
        environment.runtime_host = "sim-host"
        environment.start.return_value = 0
        sessions = mock.Mock()

        with (
            mock.patch(
                "scripts.gar_lib.api.simulation_environment_for",
                return_value=environment,
            ),
            mock.patch("scripts.gar_lib.api.load_hw_definition", return_value={}),
            mock.patch(
                "scripts.gar_lib.api.VsCodeSimulationSessionManager",
                return_value=sessions,
            ),
        ):
            exit_code = Gar(self.workspace).sim.runtime.start(no_port_forward=True)

        self.assertEqual(0, exit_code)
        sessions.start.assert_not_called()

    def test_wokwi_lifecycle_does_not_use_terminal_or_session(self) -> None:
        environment = mock.Mock()
        environment.runtime_host = None
        environment.start.return_value = 0
        sessions = mock.Mock()

        with (
            mock.patch(
                "scripts.gar_lib.api.simulation_environment_for",
                return_value=environment,
            ),
            mock.patch("scripts.gar_lib.api.load_hw_definition", return_value={}),
            mock.patch(
                "scripts.gar_lib.api.VsCodeSimulationSessionManager",
                return_value=sessions,
            ),
        ):
            exit_code = Gar(self.workspace).sim.runtime.start()

        self.assertEqual(0, exit_code)
        sessions.configure_terminal.assert_not_called()
        sessions.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
