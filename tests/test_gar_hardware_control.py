from __future__ import annotations

import unittest
from unittest import mock

from scripts.gar_lib.access.channel import AccessResult
from scripts.gar_lib.simulation.hardware.control import LinuxBridgeHardwareControl


class GarHardwareControlTest(unittest.TestCase):
    def test_gpio_plan_does_not_use_transport(self) -> None:
        channel = mock.Mock()
        control = LinuxBridgeHardwareControl(channel, mock.Mock(), host="sim-host")

        result = control.gpio(
            "plan",
            {
                "gpio": [
                    {
                        "name": "button_a",
                        "chip": "/dev/gpiochip0",
                        "line": "17",
                        "direction": "input",
                        "role": "button",
                        "sim_control": "pull",
                    }
                ]
            },
        )

        self.assertEqual(0, result.exit_code)
        self.assertEqual("sim-host", result.payload["host"])
        self.assertEqual("gpio-sim", result.payload["driver"])
        channel.run.assert_not_called()

    def test_gpio_start_uses_builder_and_command_channel(self) -> None:
        channel = mock.Mock()
        channel.run.return_value = AccessResult(("ssh",), 0, "active\n", "")
        builder = mock.Mock()
        builder.build_gpio_systemd_start.return_value = "install gpio service\nsystemctl restart gar-gpio-sim.service"
        hardware = {"gpio": []}
        control = LinuxBridgeHardwareControl(channel, builder)

        result = control.gpio("start", hardware)

        self.assertEqual(0, result.exit_code)
        builder.build_gpio_systemd_start.assert_called_once_with(hardware)
        command = channel.run.call_args.args[0]
        self.assertIn("install gpio service", command)
        self.assertIn("systemctl restart gar-gpio-sim.service", command)

    def test_gpio_status_parses_result_and_adds_host(self) -> None:
        raw = (
            "@@SERVICE@@\nactive\n"
            "@@DEVICE@@\n/dev/gpiochip0 1\n"
            "@@MOUNT@@\n0\n"
            "@@CONFIGFS@@\n1\n1\ngpiochip0\n"
            "@@GPIOCHIPS@@\n/dev/gpiochip0\n"
        )
        channel = mock.Mock()
        channel.run.return_value = AccessResult(("ssh",), 0, raw, "")
        builder = mock.Mock()
        builder.build_gpio_runtime_status.return_value = "gpio status"
        control = LinuxBridgeHardwareControl(channel, builder, host="sim-host")

        result = control.gpio("status", {"gpio": []})

        self.assertEqual(0, result.exit_code)
        self.assertTrue(result.payload["ok"])
        self.assertEqual("sim-host", result.payload["host"])
        channel.run.assert_called_once_with("gpio status")

    def test_io_state_uses_same_command_channel(self) -> None:
        channel = mock.Mock()
        channel.run.return_value = AccessResult(("ssh",), 0, '{"led18": 1}', "")
        builder = mock.Mock()
        builder.build_io.return_value = "curl state"
        control = LinuxBridgeHardwareControl(channel, builder)

        result = control.io("state", {})

        self.assertEqual(0, result.exit_code)
        self.assertEqual({"led18": 1}, result.payload)
        builder.build_io.assert_called_once_with("state", {})
        channel.run.assert_called_once_with("curl state")

    def test_io_state_reports_invalid_json_as_a_failure(self) -> None:
        channel = mock.Mock()
        channel.run.return_value = AccessResult(("ssh",), 0, "not-json", "")
        builder = mock.Mock()
        builder.build_io.return_value = "curl state"
        control = LinuxBridgeHardwareControl(channel, builder)

        result = control.io("state", {})

        self.assertEqual(1, result.exit_code)
        self.assertEqual({"ok": False, "raw": "not-json"}, result.payload)
