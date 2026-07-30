import contextlib
import io
import unittest
from unittest import mock

from scripts.gar_lib.cli import main
from scripts.gar_lib.commands.usb import parse_usbipd_list, run_usb_command


class GarUsbTest(unittest.TestCase):
    def test_usb_attach_is_available_from_cli(self) -> None:
        with mock.patch("scripts.gar_lib.commands.usb.run_usb_command", return_value=0) as run_usb:
            result = main(
                [
                    "usb",
                    "attach",
                    "--busid",
                    "3-4",
                    "--match",
                    "CH9102",
                    "--no-remember",
                ]
            )

        self.assertEqual(0, result)
        run_usb.assert_called_once_with(
            "attach",
            busid="3-4",
            match="CH9102",
            remember=False,
            json_output=False,
        )

    def test_usb_list_parses_usbipd_output(self) -> None:
        output = (
            "Connected:\n"
            "BUSID  VID:PID    DEVICE                                STATE\n"
            "1-4    8087:0aaa  Intel(R) Wireless Bluetooth(R)        Not shared\n"
            "2-3    18d1:4ee7  Android ADB Interface, USB Mass...    Shared\n"
            "\n"
            "Persisted:\n"
            "GUID  DEVICE\n"
        )
        devices = parse_usbipd_list(output)

        self.assertEqual(2, len(devices))
        android = devices[1]
        self.assertEqual("2-3", android.busid)
        self.assertEqual("18d1:4ee7", android.vid_pid)
        self.assertEqual("Shared", android.state)
        self.assertTrue(android.is_shared)
        self.assertTrue(android.looks_like_android)
        self.assertFalse(devices[0].looks_like_android)

    def test_usb_attach_auto_detects_android_and_remembers_busid(self) -> None:
        output = (
            "Connected:\n"
            "BUSID  VID:PID    DEVICE             STATE\n"
            "2-3    18d1:4ee7  Android ADB        Shared\n"
        )
        saved: dict = {}
        with (
            mock.patch("scripts.gar_lib.commands.usb._usbipd_executable", return_value="usbipd.exe"),
            mock.patch(
                "scripts.gar_lib.commands.usb.list_usb_devices",
                return_value=parse_usbipd_list(output),
            ),
            mock.patch("scripts.gar_lib.commands.usb.load_config", return_value={"selected_environments": {}}),
            mock.patch("scripts.gar_lib.commands.usb.save_config", side_effect=lambda c: saved.update(c)),
            mock.patch("scripts.gar_lib.commands.usb._run_usbipd") as run_usbipd,
        ):
            run_usbipd.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer):
                result = run_usb_command("attach")

        self.assertEqual(0, result)
        run_usbipd.assert_called_once_with(["attach", "--wsl", "--busid", "2-3"])
        self.assertEqual("2-3", saved.get("usb", {}).get("busid"))

    def test_usb_attach_can_match_ch9102_serial_device(self) -> None:
        output = (
            "Connected:\n"
            "BUSID  VID:PID    DEVICE                         STATE\n"
            "3-4    1a86:55d4  USB-Enhanced-SERIAL CH9102      Shared\n"
        )
        saved: dict = {}
        with (
            mock.patch("scripts.gar_lib.commands.usb._usbipd_executable", return_value="usbipd.exe"),
            mock.patch(
                "scripts.gar_lib.commands.usb.list_usb_devices",
                return_value=parse_usbipd_list(output),
            ),
            mock.patch("scripts.gar_lib.commands.usb.load_config", return_value={"selected_environments": {}}),
            mock.patch("scripts.gar_lib.commands.usb.save_config", side_effect=lambda c: saved.update(c)),
            mock.patch("scripts.gar_lib.commands.usb._run_usbipd") as run_usbipd,
        ):
            run_usbipd.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            result = run_usb_command("attach", match="CH9102")

        self.assertEqual(0, result)
        run_usbipd.assert_called_once_with(["attach", "--wsl", "--busid", "3-4"])
        self.assertEqual("3-4", saved.get("usb", {}).get("busid"))

    def test_usb_bind_can_match_ch9102_serial_device(self) -> None:
        output = (
            "Connected:\n"
            "BUSID  VID:PID    DEVICE                         STATE\n"
            "3-4    1a86:55d4  USB-Enhanced-SERIAL CH9102      Not shared\n"
        )
        with (
            mock.patch("scripts.gar_lib.commands.usb._usbipd_executable", return_value="usbipd.exe"),
            mock.patch(
                "scripts.gar_lib.commands.usb.list_usb_devices",
                return_value=parse_usbipd_list(output),
            ),
            mock.patch("scripts.gar_lib.commands.usb.load_config", return_value={"selected_environments": {}}),
            mock.patch("scripts.gar_lib.commands.usb.save_config"),
            mock.patch("scripts.gar_lib.commands.usb._run_usbipd") as run_usbipd,
        ):
            run_usbipd.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            result = run_usb_command("bind", match="CH9102")

        self.assertEqual(0, result)
        run_usbipd.assert_called_once_with(["bind", "--busid", "3-4"])

    def test_usb_attach_hints_bind_when_not_shared(self) -> None:
        output = (
            "Connected:\n"
            "BUSID  VID:PID    DEVICE             STATE\n"
            "2-3    18d1:4ee7  Android ADB        Not shared\n"
        )
        with (
            mock.patch("scripts.gar_lib.commands.usb._usbipd_executable", return_value="usbipd.exe"),
            mock.patch(
                "scripts.gar_lib.commands.usb.list_usb_devices",
                return_value=parse_usbipd_list(output),
            ),
            mock.patch("scripts.gar_lib.commands.usb.load_config", return_value={"selected_environments": {}}),
            mock.patch("scripts.gar_lib.commands.usb._run_usbipd") as run_usbipd,
        ):
            err_buffer = io.StringIO()
            with contextlib.redirect_stderr(err_buffer):
                result = run_usb_command("attach")

        self.assertEqual(1, result)
        run_usbipd.assert_not_called()
        self.assertIn("gar usb bind --busid 2-3", err_buffer.getvalue())
        self.assertIn("usbipd bind --busid 2-3", err_buffer.getvalue())
        self.assertIn("Host OS", err_buffer.getvalue())
        self.assertIn("管理者権限", err_buffer.getvalue())

    def test_usb_bind_admin_error_hints_windows_usbipd_command(self) -> None:
        output = (
            "Connected:\n"
            "BUSID  VID:PID    DEVICE                      STATE\n"
            "4-2    1a86:55d4  USB-Enhanced-SERIAL CH9102  Not shared\n"
        )
        with (
            mock.patch("scripts.gar_lib.commands.usb._usbipd_executable", return_value="usbipd.exe"),
            mock.patch(
                "scripts.gar_lib.commands.usb.list_usb_devices",
                return_value=parse_usbipd_list(output),
            ),
            mock.patch("scripts.gar_lib.commands.usb.load_config", return_value={"selected_environments": {}}),
            mock.patch("scripts.gar_lib.commands.usb._run_usbipd") as run_usbipd,
        ):
            run_usbipd.return_value = mock.Mock(
                returncode=1,
                stdout="",
                stderr="usbipd: error: Access denied; this operation requires administrator privileges.",
            )
            err_buffer = io.StringIO()
            with contextlib.redirect_stderr(err_buffer):
                result = run_usb_command("bind", match="CH9102")

        self.assertEqual(1, result)
        run_usbipd.assert_called_once_with(["bind", "--busid", "4-2"])
        self.assertIn("Access denied", err_buffer.getvalue())
        self.assertIn("Host OS の usbipd bind", err_buffer.getvalue())
        self.assertIn("管理者権限不足でエラー", err_buffer.getvalue())
        self.assertIn("管理者権限で開いて", err_buffer.getvalue())
        self.assertIn("usbipd bind --busid 4-2", err_buffer.getvalue())
        self.assertIn("gar usb attach --busid 4-2", err_buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
