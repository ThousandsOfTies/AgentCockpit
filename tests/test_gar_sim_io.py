import contextlib
import io
import unittest

from support.gar_cli_test_support import GarCliDispatchAssertions

from scripts.gar_lib.cli import main
from scripts.gar_lib.core.command import SIM_RUNTIME_DIAG, SIM_RUNTIME_START, GarCommand
from scripts.gar_lib.simulation.diagnostics.parse import (
    parse_gpio_runtime_status,
    parse_gpio_sim_check,
    parse_sim_diag,
)
from scripts.gar_lib.simulation.hardware import io_actions
from scripts.gar_lib.simulation.runtime.linux_commands import LinuxSystemdCommandBuilder, gpio_sim_plan


class GarSimulationIoTest(GarCliDispatchAssertions, unittest.TestCase):
    def test_sim_gpio_plan_builds_gpio_sim_contract(self) -> None:
        hw_definition = {
            "gpio": [
                {
                    "name": "test_button",
                    "chip": "/dev/gpiochip2",
                    "line": "5",
                    "direction": "input",
                    "role": "button",
                    "sim_control": "pull",
                },
                {
                    "name": "test_led",
                    "chip": "/dev/gpiochip2",
                    "line": "6",
                    "direction": "output",
                    "role": "led",
                    "sim_control": "value",
                },
            ],
        }

        plan = gpio_sim_plan(hw_definition)

        self.assertEqual("gpio-sim", plan["driver"])
        self.assertEqual("/dev/gpiochip2", plan["target_device"])
        self.assertEqual(54, plan["num_lines"])
        self.assertEqual("BTN_GPIO5", plan["lines"][0]["label"])
        self.assertEqual("LED_GPIO6", plan["lines"][1]["label"])

    def test_sim_runtime_start_manages_port_forward_by_default(self) -> None:
        self.assert_sim_dispatches(
            ["sim", "runtime", "start", "--workspace", "Local/GarStreamTx"],
            SIM_RUNTIME_START,
            settings=None,
            profile_name=None,
            no_port_forward=False,
            panel_port=8080,
        )

    def test_parse_sim_diag_builds_structured_payload(self) -> None:
        raw = (
            "@@PROC@@\n"
            "1234 /usr/bin/python3 /home/ubuntu/web-bridge/bridge.py\n"
            "1235 ./cuse_i2c -f --devname=i2c-1\n"
            "@@DEV@@\n"
            "/dev/i2c-1 1\n"
            "/dev/gpiochip0 0\n"
            "/dev/spidev0.0 0\n"
            "@@API@@\n"
            '{"led18": 1, "button17": 0}\n'
        )
        payload = parse_sim_diag(raw)

        self.assertEqual(2, len(payload["processes"]))
        self.assertEqual(1234, payload["processes"][0]["pid"])
        self.assertIn("bridge.py", payload["processes"][0]["cmd"])
        self.assertEqual(
            {"/dev/i2c-1": True, "/dev/gpiochip0": False, "/dev/spidev0.0": False},
            payload["devices"],
        )
        self.assertEqual({"led18": 1, "button17": 0}, payload["api"])
        self.assertTrue(payload["ok"])

    def test_parse_sim_diag_marks_not_ok_when_api_missing(self) -> None:
        raw = "@@PROC@@\n" "@@DEV@@\n" "/dev/i2c-1 0\n" "@@API@@\n"
        payload = parse_sim_diag(raw)

        self.assertEqual([], payload["processes"])
        self.assertIsNone(payload["api"])
        self.assertFalse(payload["ok"])

    def test_parse_gpio_sim_check_builds_structured_payload(self) -> None:
        raw = (
            "@@KERNEL@@\n"
            "6.8.0-test\n"
            "@@MODINFO@@\n"
            "1\n"
            "filename: /lib/modules/gpio-sim.ko\n"
            "@@CONFIG@@\n"
            "CONFIG_GPIO_SIM=m\n"
            "@@CONFIGFS@@\n"
            "1\n"
            "@@DEV@@\n"
            "/dev/gpiochip0\n"
        )
        payload = parse_gpio_sim_check(raw)

        self.assertEqual("6.8.0-test", payload["kernel"])
        self.assertTrue(payload["module_available"])
        self.assertTrue(payload["config_mentions_gpio_sim"])
        self.assertTrue(payload["configfs_available"])
        self.assertEqual(["/dev/gpiochip0"], payload["gpiochips"])
        self.assertTrue(payload["ok"])

    def test_parse_gpio_runtime_status_builds_structured_payload(self) -> None:
        raw = (
            "@@SERVICE@@\n"
            "active\n"
            "@@DEVICE@@\n"
            "/dev/gpiochip0 1\n"
            "@@MOUNT@@\n"
            "1\n"
            "/dev/gpiochip1\n"
            "@@CONFIGFS@@\n"
            "1\n"
            "1\n"
            "gpiochip1\n"
            "@@GPIOCHIPS@@\n"
            "/dev/gpiochip0\n"
            "/dev/gpiochip1\n"
        )

        payload = parse_gpio_runtime_status(raw)

        self.assertEqual("active", payload["service"])
        self.assertEqual({"path": "/dev/gpiochip0", "exists": True}, payload["device"])
        self.assertEqual({"active": True, "source": "/dev/gpiochip1"}, payload["mount"])
        self.assertEqual(
            {"active": True, "live": "1", "chip_name": "gpiochip1"},
            payload["configfs"],
        )
        self.assertTrue(payload["ok"])

    def test_sim_gpio_start_is_available_from_cli(self) -> None:
        self.assert_sim_dispatches(
            ["sim", "gpio", "start", "--workspace", "Network/Product"],
            GarCommand("sim", "gpio", "start"),
            workspace="Network/Product",
        )

    def test_sim_gpio_plan_json_is_available_from_cli(self) -> None:
        self.assert_sim_dispatches(
            ["sim", "gpio", "plan", "--json"],
            GarCommand("sim", "gpio", "plan"),
            workspace=None,
            json_output=True,
        )

    def test_sim_runtime_diag_json_uses_workspace_environment(self) -> None:
        self.assert_sim_dispatches(
            ["sim", "runtime", "diag", "--json", "--workspace", "Local/GarStreamTx"],
            SIM_RUNTIME_DIAG,
            workspace="Local/GarStreamTx",
            json_output=True,
        )


class SimulationIoCommandTest(unittest.TestCase):
    def test_build_io_command_button_press(self) -> None:
        command = LinuxSystemdCommandBuilder().build_io(
            "press", {"device": "button", "button": "17", "duration_ms": 150}
        )
        self.assertIn("/api/button/press?line=17&duration_ms=150", command)
        self.assertIn("-X POST", command)

    def test_build_io_command_button_press_accepts_name(self) -> None:
        command = LinuxSystemdCommandBuilder().build_io(
            "press", {"device": "button", "button": "A", "duration_ms": 150}
        )
        self.assertIn("/api/button/press?line=17&duration_ms=150", command)

    def test_build_io_command_rfid_set_encodes_uid(self) -> None:
        command = LinuxSystemdCommandBuilder().build_io("set", {"device": "rfid", "uid": "04:AB:CD:EF:01:23"})
        self.assertIn("/api/rfid/tap?uid=04:AB:CD:EF:01:23", command)

    def test_build_io_command_rfid_clear(self) -> None:
        command = LinuxSystemdCommandBuilder().build_io("clear", {"device": "rfid"})
        self.assertIn("/api/rfid/remove", command)

    def test_build_io_command_range_set(self) -> None:
        command = LinuxSystemdCommandBuilder().build_io("set", {"device": "range", "value": "300"})
        self.assertIn("/api/range?value=300", command)

    def test_build_io_command_requires_device_for_non_state(self) -> None:
        with self.assertRaises(ValueError):
            LinuxSystemdCommandBuilder().build_io("set", {"value": "1"})

    def test_build_io_command_state_is_get(self) -> None:
        command = LinuxSystemdCommandBuilder().build_io("state", {})
        self.assertIn("/api/state", command)
        self.assertNotIn("-X POST", command)

    def test_build_io_command_rejects_unknown_action(self) -> None:
        with self.assertRaises(ValueError):
            LinuxSystemdCommandBuilder().build_io("explode", {})

    def test_scenario_runner_shares_io_vocabulary_with_cli(self) -> None:
        steps = (
            ("press", {"device": "button", "line": 17, "duration_ms": 150}),
            ("set", {"device": "button", "line": 17, "value": 1}),
            ("set", {"device": "rfid", "uid": "04:AB:CD:EF:01:23"}),
            ("clear", {"device": "rfid"}),
            ("set", {"device": "range", "value": 300}),
        )
        for action, step in steps:
            with self.subTest(action=action, device=step.get("device")):
                request = io_actions.resolve(action, step.get("device"), step)
                command = LinuxSystemdCommandBuilder().build_io(action, step)
                self.assertIn(request.path, command)

    def test_scenario_runner_rejects_legacy_action_names(self) -> None:
        for legacy in ("button_press", "rfid_tap", "range_set"):
            with self.subTest(action=legacy):
                self.assertNotIn(legacy, io_actions.IO_ACTIONS)

    def test_sim_ui_is_not_a_public_cli_command(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as exc:
                main(["sim", "ui", "button", "press", "17"])

        self.assertEqual(2, exc.exception.code)
        self.assertIn("invalid choice: 'ui'", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
