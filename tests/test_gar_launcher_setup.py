from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.launcher_setup import offer_scripts_path_registration


class TtyInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class GarLauncherSetupTest(unittest.TestCase):
    def test_current_path_duplicate_skips_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scripts = Path(temporary_directory) / "scripts"
            scripts.mkdir()
            output = io.StringIO()

            result = offer_scripts_path_registration(
                scripts,
                stdin=TtyInput("\n"),
                stdout=output,
                environ={"PATH": f'"{scripts.resolve()}/"'},
                platform="posix",
            )

        self.assertEqual(0, result)
        self.assertIn("PATH登録済みのためSKIP", output.getvalue())
        self.assertNotIn("[Y/n]", output.getvalue())

    def test_windows_persistent_path_duplicate_skips_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scripts = Path(temporary_directory) / "scripts"
            scripts.mkdir()
            output = io.StringIO()
            with (
                mock.patch(
                    "scripts.gar_lib.launcher_setup._read_windows_user_path",
                    return_value=(str(scripts.resolve()).upper(), 2),
                ),
                mock.patch("scripts.gar_lib.launcher_setup._write_windows_user_path") as write_path,
            ):
                result = offer_scripts_path_registration(
                    scripts,
                    stdin=TtyInput("\n"),
                    stdout=output,
                    environ={"PATH": ""},
                    platform="nt",
                )

        self.assertEqual(0, result)
        write_path.assert_not_called()
        self.assertIn("PATH登録済みのためSKIP", output.getvalue())
        self.assertNotIn("[Y/n]", output.getvalue())

    def test_windows_default_yes_appends_user_path_and_broadcasts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scripts = Path(temporary_directory) / "scripts"
            scripts.mkdir()
            output = io.StringIO()
            with (
                mock.patch(
                    "scripts.gar_lib.launcher_setup._read_windows_user_path",
                    return_value=("C:\\Tools", 2),
                ),
                mock.patch("scripts.gar_lib.launcher_setup._write_windows_user_path") as write_path,
                mock.patch("scripts.gar_lib.launcher_setup._broadcast_windows_environment_change") as broadcast,
            ):
                result = offer_scripts_path_registration(
                    scripts,
                    stdin=TtyInput("\n"),
                    stdout=output,
                    environ={"PATH": ""},
                    platform="nt",
                )

        self.assertEqual(0, result)
        write_path.assert_called_once_with(f"C:\\Tools;{scripts.resolve()}", 2)
        broadcast.assert_called_once_with()
        self.assertIn("[Y/n]", output.getvalue())
        self.assertIn("新しいterminal", output.getvalue())

    def test_no_answer_keeps_path_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scripts = Path(temporary_directory) / "scripts"
            scripts.mkdir()
            output = io.StringIO()
            with (
                mock.patch("scripts.gar_lib.launcher_setup._read_windows_user_path", return_value=("", 2)),
                mock.patch("scripts.gar_lib.launcher_setup._write_windows_user_path") as write_path,
            ):
                result = offer_scripts_path_registration(
                    scripts,
                    stdin=TtyInput("n\n"),
                    stdout=output,
                    environ={"PATH": ""},
                    platform="nt",
                )

        self.assertEqual(0, result)
        write_path.assert_not_called()
        self.assertIn("PATH登録をSKIPしました", output.getvalue())

    def test_posix_default_yes_adds_one_profile_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            home = Path(temporary_directory)
            scripts = home / "repo" / "scripts"
            scripts.mkdir(parents=True)
            output = io.StringIO()

            result = offer_scripts_path_registration(
                scripts,
                stdin=TtyInput("\n"),
                stdout=output,
                environ={"PATH": "/usr/bin", "HOME": str(home), "SHELL": "/bin/bash"},
                platform="posix",
            )
            profile = (home / ".bashrc").read_text(encoding="utf-8")

        self.assertEqual(0, result)
        self.assertIn(str(scripts.resolve()), profile)
        self.assertIn('"$PATH"', profile)

    def test_noninteractive_setup_does_not_change_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scripts = Path(temporary_directory) / "scripts"
            scripts.mkdir()
            output = io.StringIO()
            with (
                mock.patch("scripts.gar_lib.launcher_setup._read_windows_user_path", return_value=("", 2)),
                mock.patch("scripts.gar_lib.launcher_setup._write_windows_user_path") as write_path,
            ):
                result = offer_scripts_path_registration(
                    scripts,
                    stdin=io.StringIO(""),
                    stdout=output,
                    environ={"PATH": ""},
                    platform="nt",
                )

        self.assertEqual(0, result)
        write_path.assert_not_called()
        self.assertIn("非対話実行", output.getvalue())


if __name__ == "__main__":
    unittest.main()
