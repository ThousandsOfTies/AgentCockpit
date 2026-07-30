from __future__ import annotations

from pathlib import Path
from unittest import mock

from scripts.gar_lib.cli import main
from scripts.gar_lib.core.command import GarCommand
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption


class FakeDevelopmentEnvironment(EnvironmentSetupOption):
    environment_id = "development_test"
    display_name = "Development Test"
    description = "codespace"
    category_id = "codespace"
    category_name = "開発環境"
    required_commands = ()


class FakeSimulationEnvironment(EnvironmentSetupOption):
    environment_id = "simulation_test"
    display_name = "Simulation Test"
    description = "simulator"
    category_id = "simulator"
    category_name = "シミュレート環境"
    required_commands = ()


class FakeWokwiEnvironment(EnvironmentSetupOption):
    environment_id = "wokwi"
    display_name = "Wokwi"
    description = "wokwi"
    category_id = "simulator"
    category_name = "シミュレート環境"
    required_commands = ()


class FakeMissingSimulationEnvironment(EnvironmentSetupOption):
    environment_id = "missing_simulation"
    display_name = "Missing Simulation"
    description = "missing simulation"
    category_id = "simulator"
    category_name = "シミュレート環境"
    required_commands = ("missing-sim-command",)


class FakeTargetAccessEnvironment(EnvironmentSetupOption):
    environment_id = "device_test"
    display_name = "Device Test"
    description = "target"
    category_id = "target"
    category_name = "実機環境"
    required_commands = ()


class FakeMissingTargetAccessEnvironment(EnvironmentSetupOption):
    environment_id = "missing_test"
    display_name = "Missing Test"
    description = "missing"
    category_id = "target"
    category_name = "実機環境"
    required_commands = ("missing-command",)


class GarCliDispatchAssertions:
    """CLI dispatch assertions shared by root-parser integration tests."""

    def assert_sim_dispatches(
        self,
        argv: list[str],
        command: GarCommand,
        **expected: object,
    ) -> None:
        workspace = Workspace(id="ws", name="Local/Product", branch="main", connection={"type": "local"})
        classes = {
            "app": "SimulationApp",
            "runtime": "SimulationRuntime",
            "host": "SimulationHost",
            "gpio": "SimulationGpio",
            "io": "SimulationIo",
        }
        action_result: object = 0
        if command.subject in {"gpio", "io"} or (command.subject == "runtime" and command.action == "diag"):
            action_result = mock.Mock(exit_code=0)
        with (
            mock.patch(
                f"scripts.gar_lib.api.{classes[command.subject]}.{command.action}",
                return_value=action_result,
                autospec=True,
            ) as action,
            mock.patch("scripts.gar_lib.commands.sim.resolve_workspace", return_value=workspace) as lookup,
            mock.patch("scripts.gar_lib.commands.sim._render_artifact", return_value=0),
            mock.patch("scripts.gar_lib.commands.sim._render_optional_runtime_artifact", return_value=0),
            mock.patch("scripts.gar_lib.commands.sim._render_host_start"),
            mock.patch("scripts.gar_lib.commands.sim._render_host_status") as render_host_status,
            mock.patch("scripts.gar_lib.commands.sim._render_hardware_result") as render_hardware_result,
            mock.patch("scripts.gar_lib.commands.sim._render_diagnostic") as render_diagnostic,
            mock.patch(
                "scripts.gar_lib.api.SimulationRuntime.session_host",
                new_callable=mock.PropertyMock,
                return_value=None,
            ),
        ):
            result = main(argv)

        self.assertEqual(0, result)
        subject = action.call_args.args[0]
        self.assertIs(workspace, subject.workspace)
        selector = argv[argv.index("--workspace") + 1] if "--workspace" in argv else None
        lookup.assert_called_once_with(selector)
        for name, value in expected.items():
            if name == "workspace":
                continue
            if name == "json_output" and command.subject == "host" and command.action == "status":
                self.assertEqual(value, render_host_status.call_args.kwargs[name], name)
                continue
            if name == "json_output" and command.subject in {"gpio", "io"}:
                self.assertEqual(value, render_hardware_result.call_args.kwargs[name], name)
                continue
            if name == "json_output" and command.subject == "runtime" and command.action == "diag":
                self.assertEqual(value, render_diagnostic.call_args.kwargs[name], name)
                continue
            self.assertEqual(value, action.call_args.kwargs[name], name)

    def assert_target_dispatches(
        self,
        argv: list[str],
        command: GarCommand,
    ) -> None:
        workspace = Workspace(id="ws", name="Local/Product", branch="main", connection={"type": "local"})
        artifact = mock.Mock(bundle_path=Path("/tmp/artifact"))
        with (
            mock.patch(
                f"scripts.gar_lib.api.Target.{command.action}",
                return_value=artifact,
                autospec=True,
            ) as action,
            mock.patch("scripts.gar_lib.commands.target.resolve_workspace", return_value=workspace) as lookup,
        ):
            result = main(argv)

        self.assertEqual(0, result)
        target = action.call_args.args[0]
        self.assertIs(workspace, target.workspace)
        lookup.assert_called_once_with("Local/Product")
