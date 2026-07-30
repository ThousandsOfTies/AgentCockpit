from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest
from unittest import mock

from scripts.gar_lib.commands import usb


class UsbCommandFailureTest(unittest.TestCase):
    def test_list_propagates_usbipd_failure_instead_of_reporting_no_devices(self) -> None:
        failed_list = subprocess.CompletedProcess(
            args=["usbipd.exe", "list"],
            returncode=7,
            stdout="",
            stderr="usbipd service is unavailable",
        )
        output = io.StringIO()
        error = io.StringIO()
        with (
            mock.patch.object(usb, "_usbipd_executable", return_value="usbipd.exe"),
            mock.patch.object(usb, "_run_usbipd", return_value=failed_list),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            result = usb.run_usb_command("list")

        self.assertEqual(7, result)
        self.assertEqual("", output.getvalue())
        self.assertIn("usbipd service is unavailable", error.getvalue())
        self.assertNotIn("接続中の USB デバイスがありません", output.getvalue())

    def test_json_list_failure_is_machine_readable_and_returns_nonzero(self) -> None:
        failed_list = subprocess.CompletedProcess(
            args=["usbipd.exe", "list"],
            returncode=3,
            stdout="usbipd failed",
            stderr="",
        )
        output = io.StringIO()
        with (
            mock.patch.object(usb, "_usbipd_executable", return_value="usbipd.exe"),
            mock.patch.object(usb, "_run_usbipd", return_value=failed_list),
            contextlib.redirect_stdout(output),
        ):
            result = usb.run_usb_command("list", json_output=True)

        payload = json.loads(output.getvalue())
        self.assertEqual(3, result)
        self.assertEqual("usb list", payload["command"])
        self.assertFalse(payload["ok"])
        self.assertEqual("usbipd failed", payload["error"])


if __name__ == "__main__":
    unittest.main()
