from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.commands.code import CodeStartOptions, configure_vscode_codespace
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.simulation.session.remote import sim_terminal_script
from scripts.gar_lib.vscode.profile_manage import write_vscode_terminal_profile


class WindowsHostAdapterTest(unittest.TestCase):
    def test_codespaces_profile_runs_python_launcher_without_sshfs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            options = CodeStartOptions(
                home=root,
                codespace_name="codespace-test",
                remote_path="/workspaces/product",
                mount_dir=root / "unused-mount",
                settings_path=root / "settings.json",
                profile_name="Codespaces",
                state_path=root / "state.json",
                terminal_path=root / "codespace-terminal",
                no_mount=True,
                gh_timeout=30,
            )
            with (
                mock.patch("scripts.gar_lib.commands.code._is_windows_host", return_value=True),
                mock.patch("scripts.gar_lib.commands.code.write_vscode_terminal_profile") as write_profile,
            ):
                configure_vscode_codespace(options)
            launcher = options.terminal_path.read_text(encoding="utf-8")

        self.assertTrue(launcher.startswith("#!/usr/bin/env python3"))
        write_profile.assert_called_once_with(
            options.settings_path,
            "Codespaces",
            Path(sys.executable),
            arguments=[str(options.terminal_path)],
        )

    def test_windows_sim_terminal_uses_cmd_launcher(self) -> None:
        with mock.patch("scripts.gar_lib.simulation.session.remote.os.name", "nt"):
            script = sim_terminal_script("gar-sim-local")

        self.assertTrue(script.startswith("@echo off\r\n"))
        self.assertIn("ssh", script)
        self.assertIn("gar-sim-local", script)

    def test_sim_terminal_rejects_cmd_metacharacters_in_host_alias(self) -> None:
        with self.assertRaises(GarDomainError):
            sim_terminal_script("gar-sim & calc")

    def test_windows_vscode_profile_runs_cmd_file_through_cmd_exe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = Path(temporary_directory) / "settings.json"
            launcher = Path(temporary_directory) / "gar-sim-terminal.cmd"
            with (
                mock.patch("scripts.gar_lib.vscode.profile_manage.os.name", "nt"),
                mock.patch.dict(
                    "scripts.gar_lib.vscode.profile_manage.os.environ",
                    {"COMSPEC": "C:/Windows/System32/cmd.exe"},
                    clear=False,
                ),
            ):
                write_vscode_terminal_profile(settings, "GAR Simulation Host", launcher)

            profile = json.loads(settings.read_text(encoding="utf-8"))

        self.assertEqual(
            {
                "path": "C:/Windows/System32/cmd.exe",
                "args": ["/d", "/c", str(launcher)],
            },
            profile["terminal.integrated.profiles.windows"]["GAR Simulation Host"],
        )


if __name__ == "__main__":
    unittest.main()
