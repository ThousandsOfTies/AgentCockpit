from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.commands.setup.command import _configure_workspace_phase
from scripts.gar_lib.commands.setup.environment_setup import (
    ensure_environment_dependencies,
)
from scripts.gar_lib.core.config import load_config
from scripts.gar_lib.environments.registry.target.adb_win import AdbWinEnvironment
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption


def _workspace_entry(workspace_id: str, name: str, path: Path) -> dict:
    return {
        "id": workspace_id,
        "name": name,
        "connection": {"type": "local", "path": str(path)},
        "branch": "main",
        "selected_environments": {"target": workspace_id},
    }


class ConfigWorkspaceContextTests(unittest.TestCase):
    def test_explicit_workspace_selection_does_not_leak_to_next_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            entries = [
                _workspace_entry("tx", "Local/Tx", root / "tx"),
                _workspace_entry("rx", "Local/Rx", root / "rx"),
            ]
            config_path.write_text(json.dumps({"workspaces": entries}), encoding="utf-8")

            with mock.patch("scripts.gar_lib.core.config.CONFIG_PATH", config_path):
                selected = load_config(workspace_selector="rx")
                inferred = load_config()

        self.assertEqual("rx", selected["workspace_id"])
        self.assertNotIn("workspace_id", inferred)
        self.assertEqual(2, len(inferred["workspaces"]))

    def test_explicit_workspace_path_selects_local_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected_path = root / "product"
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "workspaces": [
                            _workspace_entry("product", "Local/Product", selected_path),
                            _workspace_entry("other", "Local/Other", root / "other"),
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("scripts.gar_lib.core.config.CONFIG_PATH", config_path):
                config = load_config(workspace_selector=selected_path)

        self.assertEqual("product", config["workspace_id"])

    def test_setup_reloads_only_the_workspace_selected_in_that_phase(self) -> None:
        original_config = {"workspaces": [], "selected_environments": {}}
        selected_config = {"workspace_id": "rx", "workspaces": []}

        with (
            mock.patch("scripts.gar_lib.commands.setup.command.sys.stdin.isatty", return_value=True),
            mock.patch(
                "scripts.gar_lib.commands.setup.command.configure_workspace_root",
                return_value="rx",
            ),
            mock.patch(
                "scripts.gar_lib.commands.setup.command.load_config",
                return_value=selected_config,
            ) as load,
        ):
            result = _configure_workspace_phase(original_config)

        self.assertIs(selected_config, result)
        self.assertEqual({}, result["selected_environments"])
        load.assert_called_once_with(workspace_selector="rx")


class EnvironmentConfigurationContextTests(unittest.TestCase):
    def test_dependency_check_passes_selected_config_to_environment(self) -> None:
        config = {"workspace_id": "selected"}

        class ConfigRecordingEnvironment(EnvironmentSetupOption):
            environment_id = "test"
            display_name = "Test"
            description = "Test environment"
            recorded_config: dict | None = None

            @classmethod
            def record_detected_configuration(cls, detected_config: dict) -> None:
                cls.recorded_config = detected_config

        with mock.patch.object(ConfigRecordingEnvironment, "missing_commands", return_value=[]):
            result = ensure_environment_dependencies(
                ConfigRecordingEnvironment,
                config=config,
                no_install=True,
            )

        self.assertEqual(0, result)
        self.assertIs(config, ConfigRecordingEnvironment.recorded_config)

    def test_adb_detection_updates_only_the_supplied_config(self) -> None:
        config = {
            "workspace_id": "selected",
            "adb": {"exe_path": "old-adb.exe"},
        }
        version = subprocess.CompletedProcess(
            ["C:/Android/adb.exe", "version"],
            0,
            stdout="Android Debug Bridge version 1.0.41\n",
        )

        with (
            mock.patch(
                "scripts.gar_lib.environments.registry.target.adb_win.shutil.which",
                return_value="C:/Android/adb.exe",
            ),
            mock.patch(
                "scripts.gar_lib.environments.registry.target.adb_win.subprocess.run",
                return_value=version,
            ),
            mock.patch("scripts.gar_lib.environments.registry.target.adb_win.save_config") as save,
        ):
            result = AdbWinEnvironment.remember_adb_exe(config)

        self.assertEqual("C:/Android/adb.exe", result)
        self.assertEqual("C:/Android/adb.exe", config["adb"]["exe_path"])
        self.assertEqual("Android Debug Bridge version 1.0.41", config["adb"]["version"])
        save.assert_called_once_with(config)


if __name__ == "__main__":
    unittest.main()
