import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from scripts.gar_lib.cli import main
from scripts.gar_lib.commands.terminal import run_terminal_run_command
from scripts.gar_lib.core.hardware import HW_TEMPLATE_FILES, write_hw_template


def _create_hardware_templates(tools_root: Path, target: str = "linux-device") -> None:
    template_dir = tools_root / "targets" / target / "hardware"
    template_dir.mkdir(parents=True)
    for name, headers in HW_TEMPLATE_FILES.items():
        (template_dir / name).write_text(",".join(headers) + "\n", encoding="utf-8")


class GarTerminalHardwareTest(unittest.TestCase):
    def test_terminal_run_creates_vscode_terminal_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with (
                mock.patch("scripts.gar_lib.commands.terminal.CONFIG_PATH", tmp_path / ".gar" / "config.json"),
                mock.patch("scripts.gar_lib.commands.terminal.Path.cwd", return_value=tmp_path),
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = run_terminal_run_command(
                        command_parts=["echo", "hello"],
                        command_text=None,
                        title="Test Terminal",
                        cwd=None,
                    )

            self.assertEqual(0, result)
            requests = list((tmp_path / ".gar" / "terminal-requests").glob("*.json"))
            self.assertEqual(1, len(requests))

            request = json.loads(requests[0].read_text(encoding="utf-8"))
            self.assertEqual("Test Terminal", request["title"])
            self.assertEqual("echo hello", request["command"])
            self.assertEqual(str(tmp_path), request["cwd"])

    def test_terminal_run_is_available_from_cli(self) -> None:
        with mock.patch(
            "scripts.gar_lib.commands.terminal.run_terminal_run_command",
            return_value=0,
        ) as run_terminal:
            result = main(
                [
                    "terminal",
                    "run",
                    "--title",
                    "Test Terminal",
                    "--cwd",
                    "/tmp/product",
                    "--",
                    "echo",
                    "hello world",
                ]
            )

        self.assertEqual(0, result)
        run_terminal.assert_called_once_with(
            command_parts=["--", "echo", "hello world"],
            command_text=None,
            title="Test Terminal",
            cwd="/tmp/product",
        )

    def test_terminal_run_preserves_argument_boundaries_after_separator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with (
                mock.patch("scripts.gar_lib.commands.terminal.CONFIG_PATH", tmp_path / ".gar" / "config.json"),
                mock.patch("scripts.gar_lib.commands.terminal.Path.cwd", return_value=tmp_path),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = run_terminal_run_command(
                    command_parts=["--", "printf", "%s", "hello world"],
                    command_text=None,
                    title="Test Terminal",
                    cwd=None,
                )

            self.assertEqual(0, result)
            [request_path] = (tmp_path / ".gar" / "terminal-requests").glob("*.json")
            request = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual("printf %s 'hello world'", request["command"])

    def test_terminal_gc_removes_old_processed_requests(self) -> None:
        from scripts.gar_lib.commands.terminal import run_terminal_gc_command

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            processed = tmp_path / ".gar" / "terminal-requests" / "processed"
            status_dir = tmp_path / ".gar" / "terminal-status"
            processed.mkdir(parents=True)
            status_dir.mkdir(parents=True)

            old = processed / "old.started.json"
            new = processed / "new.started.json"
            old_status = status_dir / "old.json"
            old.write_text("{}", encoding="utf-8")
            new.write_text("{}", encoding="utf-8")
            old_status.write_text("{}", encoding="utf-8")

            old_mtime = datetime.now(UTC).timestamp() - 30 * 86400
            os.utime(old, (old_mtime, old_mtime))
            os.utime(old_status, (old_mtime, old_mtime))

            with (
                mock.patch(
                    "scripts.gar_lib.commands.terminal.CONFIG_PATH",
                    tmp_path / ".gar" / "config.json",
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = run_terminal_gc_command(keep_days=7, dry_run=False)

            self.assertEqual(0, result)
            self.assertFalse(old.exists())
            self.assertFalse(old_status.exists())
            self.assertTrue(new.exists())

    def test_terminal_gc_dry_run_reports_matched_files(self) -> None:
        from scripts.gar_lib.commands.terminal import run_terminal_gc_command

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            processed = tmp_path / ".gar" / "terminal-requests" / "processed"
            processed.mkdir(parents=True)
            old = processed / "old.started.json"
            old.write_text("{}", encoding="utf-8")
            old_mtime = datetime.now(UTC).timestamp() - 30 * 86400
            os.utime(old, (old_mtime, old_mtime))

            output = io.StringIO()
            with (
                mock.patch(
                    "scripts.gar_lib.commands.terminal.CONFIG_PATH",
                    tmp_path / ".gar" / "config.json",
                ),
                contextlib.redirect_stdout(output),
            ):
                result = run_terminal_gc_command(keep_days=7, dry_run=True)

            self.assertEqual(0, result)
            self.assertTrue(old.exists())
            self.assertIn("scan: 1 ファイル / 対象: 1", output.getvalue())

    def test_hw_init_copies_gar_tools_csv_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_hw = root / "gar-tools" / "targets" / "linux-device" / "hardware"
            tools_hw.mkdir(parents=True)
            templates = {
                "components.csv": "component_id,name,kind,part_number,description\nboard,Board,board,Test,Template row\n",
                "gpio.csv": "name,chip,line,direction,role,active,initial,pull,sim_control,description\nbutton,/dev/gpiochip0,1,input,button,high,,pull-up,pull,Template row\n",
                "i2c.csv": "name,bus,dev,address,driver,sim,description\noled,1,/dev/i2c-1,0x3c,ssd1306,ssd1306,Template row\n",
                "spi.csv": "name,bus,chip_select,dev,mode,max_speed_hz,driver,sim,description\nrfid,0,0,/dev/spidev0.0,0,1000000,mfrc522,mfrc522,Template row\n",
                "connections.csv": "source,source_pin,target,target_pin,signal,description\nboard,GPIO1,button,signal,GPIO1,Template row\n",
            }
            for name, content in templates.items():
                (tools_hw / name).write_text(content, encoding="utf-8")

            hw_dir = root / "hardware"
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"GAR_TOOLS_ROOT": str(root / "gar-tools")}),
                contextlib.redirect_stdout(output),
            ):
                result = main(["hw", "init", "--target", "linux-device", "--dir", str(hw_dir)])

            self.assertEqual(0, result)
            for name, content in templates.items():
                self.assertEqual(content, (hw_dir / name).read_text(encoding="utf-8"))

    def test_hw_init_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_root = root / "gar-tools"
            _create_hardware_templates(tools_root)
            hw_dir = root / "hardware"
            hw_dir.mkdir()
            gpio_csv = hw_dir / "gpio.csv"
            gpio_csv.write_text("keep me\n", encoding="utf-8")

            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"GAR_TOOLS_ROOT": str(tools_root)}),
                contextlib.redirect_stdout(output),
            ):
                result = main(["hw", "init", "--dir", str(hw_dir)])

            self.assertEqual(1, result)
            self.assertEqual("keep me\n", gpio_csv.read_text(encoding="utf-8"))
            self.assertIn("--force", output.getvalue())

    def test_hw_init_rejects_target_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(
                    [
                        "hw",
                        "init",
                        "--target",
                        "../outside",
                        "--dir",
                        str(Path(tmp) / "hardware"),
                    ]
                )

            self.assertEqual(1, result)
            self.assertIn("invalid target id", output.getvalue())

    def test_hw_template_rejects_non_string_target_id(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = write_hw_template(target_id=None)  # type: ignore[arg-type]

        self.assertEqual(1, result)
        self.assertIn("invalid target id", output.getvalue())

    def test_hw_init_defaults_to_the_current_product_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp)
            tools_root = workspace_root / "gar-tools"
            _create_hardware_templates(tools_root)
            with (
                mock.patch.dict(os.environ, {"GAR_TOOLS_ROOT": str(tools_root)}),
                mock.patch("scripts.gar_lib.core.hardware.Path.cwd", return_value=workspace_root),
            ):
                result = main(["hw", "init"])

            self.assertEqual(0, result)
            self.assertTrue((workspace_root / "hardware" / "components.csv").exists())

    def test_hw_init_uses_selected_target_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_root = root / "gar-tools"
            template = tools_root / "targets" / "luckfox-rv1106" / "hardware"
            template.mkdir(parents=True)
            for name, headers in HW_TEMPLATE_FILES.items():
                (template / name).write_text(",".join(headers) + "\n", encoding="utf-8")

            output_dir = root / "output"
            with (
                mock.patch.dict(os.environ, {"GAR_TOOLS_ROOT": str(tools_root)}),
                mock.patch(
                    "scripts.gar_lib.commands.hw.load_config",
                    return_value={"selected_target": "luckfox-rv1106"},
                ),
            ):
                result = main(["hw", "init", "--dir", str(output_dir)])

            self.assertEqual(0, result)
            self.assertTrue((output_dir / "gpio.csv").exists())

    def test_hw_init_is_available_from_cli(self) -> None:
        with mock.patch("scripts.gar_lib.commands.hw.run_hw_command", return_value=0) as run_hw:
            result = main(["hw", "init", "--target", "luckfox-rv1106", "--dir", "custom-hw", "--force"])

        self.assertEqual(0, result)
        run_hw.assert_called_once_with(
            "init",
            output_dir="custom-hw",
            force=True,
            target_id="luckfox-rv1106",
        )


if __name__ == "__main__":
    unittest.main()
