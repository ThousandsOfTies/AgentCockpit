from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.cli import main
from scripts.gar_lib.core.hardware_validation import validate_hardware_contract
from scripts.gar_lib.core.workspace import Workspace


def requirements() -> dict[str, object]:
    return {
        "schema_version": 1,
        "product": "GarStreamRx",
        "requirements": [
            {
                "id": "gpio-ready",
                "kind": "gpio",
                "component": "status-led",
                "voltage_v": 3.3,
                "required_drivers": ["gpio-cdev"],
                "direction": "output",
            },
            {
                "id": "camera",
                "kind": "video",
                "component": "usb-uvc-camera",
                "voltage_v": 5.0,
                "required_drivers": ["uvcvideo"],
                "min_fps": 30,
                "device": "/dev/video0",
            },
            {
                "id": "uplink",
                "kind": "network",
                "component": "ethernet",
                "required_drivers": ["stmmac"],
            },
        ],
    }


def capabilities() -> dict[str, object]:
    return {
        "schema_version": 1,
        "target_id": "luckfox-rk3506",
        "platform": {
            "architecture": "armv7l",
            "abi": "gnueabihf",
            "toolchain_triple": "arm-buildroot-linux-gnueabihf",
            "init_system": "busybox",
            "privilege_model": "root",
        },
        "resources": [
            {
                "id": "gpio0",
                "kind": "gpio",
                "device": "/dev/gpiochip0",
                "voltage_v": 3.3,
                "drivers": ["gpio-cdev"],
                "pinmux": {"id": "gpio", "settings": []},
                "lines": [12, 13],
                "line_pins": {"12": "P12", "13": "P13"},
                "directions": ["input", "output"],
            },
            {
                "id": "usb-uvc",
                "kind": "video",
                "device": "/dev/video0",
                "voltage_v": 5.0,
                "drivers": ["uvcvideo"],
                "pinmux": {"id": "usb", "settings": []},
                "max_fps": 60,
                "signal_pins": {"USB": "USB0"},
            },
            {
                "id": "network0",
                "kind": "network",
                "device": "eth0",
                "drivers": ["stmmac"],
                "pinmux": {"id": "ethernet", "settings": []},
                "signal_pins": {"Ethernet": "RJ45"},
            },
        ],
    }


def binding() -> dict[str, object]:
    return {
        "schema_version": 1,
        "product": "GarStreamRx",
        "target_id": "luckfox-rk3506",
        "mappings": [
            {
                "requirement": "gpio-ready",
                "resource": "gpio0",
                "line": 12,
                "physical_pin": "P12",
                "pinmux": "gpio",
            },
            {"requirement": "camera", "resource": "usb-uvc", "physical_pin": "USB0", "pinmux": "usb"},
            {"requirement": "uplink", "resource": "network0", "physical_pin": "RJ45", "pinmux": "ethernet"},
        ],
    }


class GarHardwareValidationTest(unittest.TestCase):
    def _write_contract(self, root: Path) -> tuple[Path, Path, Path]:
        paths = (root / "requirements.json", root / "capabilities.json", root / "binding.json")
        for path, value in zip(paths, (requirements(), capabilities(), binding()), strict=True):
            path.write_text(json.dumps(value), encoding="utf-8")
        return paths

    def test_accepts_complete_contract_and_preserves_physical_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_contract(Path(tmp))
            report = validate_hardware_contract(
                requirements_path=paths[0],
                capabilities_path=paths[1],
                binding_path=paths[2],
                selected_target_id="luckfox-rk3506",
            )

        self.assertTrue(report.ok)
        self.assertEqual("busybox", report.platform["init_system"] if report.platform else None)
        self.assertEqual("P12", report.assignments[0]["physical_pin"])
        self.assertEqual("gpio", report.assignments[0]["pinmux"])

    def test_detects_gpio_spi_and_voltage_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirement_data = requirements()
            requirement_data["requirements"].append(  # type: ignore[index]
                {
                    "id": "gpio-other",
                    "kind": "gpio",
                    "component": "other-led",
                    "voltage_v": 1.8,
                    "required_drivers": ["gpio-cdev"],
                    "direction": "output",
                }
            )
            binding_data = binding()
            binding_data["mappings"].append(  # type: ignore[index]
                {
                    "requirement": "gpio-other",
                    "resource": "gpio0",
                    "line": 12,
                    "physical_pin": "P12",
                    "pinmux": "gpio",
                }
            )
            paths = (root / "requirements.json", root / "capabilities.json", root / "binding.json")
            for path, value in zip(paths, (requirement_data, capabilities(), binding_data), strict=True):
                path.write_text(json.dumps(value), encoding="utf-8")
            report = validate_hardware_contract(
                requirements_path=paths[0],
                capabilities_path=paths[1],
                binding_path=paths[2],
            )

        self.assertFalse(report.ok)
        self.assertIn("voltage_mismatch", {error["code"] for error in report.errors})
        self.assertIn("gpio_pin_conflict", {error["code"] for error in report.errors})

    def test_rejects_unknown_binding_fields_and_target_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binding_data = binding()
            binding_data["target_id"] = "wrong-target"
            binding_data["mappings"][0]["unknown"] = True  # type: ignore[index]
            paths = (root / "requirements.json", root / "capabilities.json", root / "binding.json")
            for path, value in zip(paths, (requirements(), capabilities(), binding_data), strict=True):
                path.write_text(json.dumps(value), encoding="utf-8")
            report = validate_hardware_contract(
                requirements_path=paths[0],
                capabilities_path=paths[1],
                binding_path=paths[2],
                selected_target_id="luckfox-rk3506",
            )

        self.assertFalse(report.ok)
        self.assertIn("invalid_schema", {error["code"] for error in report.errors})

    def test_detects_duplicate_spi_bus_and_chip_select(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirement_data = {
                "schema_version": 1,
                "product": "spi-test",
                "requirements": [
                    {
                        "id": item_id,
                        "kind": "spi",
                        "component": "display",
                        "voltage_v": 3.3,
                        "required_drivers": ["spidev"],
                        "min_speed_hz": 1_000_000,
                        "mode": 0,
                        "device": "/dev/spidev0.0",
                    }
                    for item_id in ("display-a", "display-b")
                ],
            }
            capability_data = {
                "schema_version": 1,
                "target_id": "target",
                "platform": {
                    "architecture": "aarch64",
                    "abi": "gnu",
                    "toolchain_triple": "aarch64-linux-gnu",
                    "init_system": "systemd",
                    "privilege_model": "sudo-noninteractive",
                },
                "resources": [
                    {
                        "id": resource_id,
                        "kind": "spi",
                        "device": "/dev/spidev0.0",
                        "voltage_v": 3.3,
                        "drivers": ["spidev"],
                        "pinmux": {"id": "spi0", "settings": ["enable-spi0"]},
                        "bus": 0,
                        "chip_select": 0,
                        "max_speed_hz": 2_000_000,
                        "modes": [0, 1, 2, 3],
                        "signal_pins": {"MOSI": "P1", "MISO": "P2", "SCLK": "P3", "CS0": "P4"},
                    }
                    for resource_id in ("spi0.cs0-a", "spi0.cs0-b")
                ],
            }
            binding_data = {
                "schema_version": 1,
                "product": "spi-test",
                "target_id": "target",
                "mappings": [
                    {
                        "requirement": "display-a",
                        "resource": "spi0.cs0-a",
                        "physical_pins": ["P1:MOSI", "P2:MISO", "P3:SCLK", "P4:CS0"],
                        "pinmux": "spi0",
                    },
                    {
                        "requirement": "display-b",
                        "resource": "spi0.cs0-b",
                        "physical_pins": ["P1:MOSI", "P2:MISO", "P3:SCLK", "P4:CS0"],
                        "pinmux": "spi0",
                    },
                ],
            }
            paths = (root / "requirements.json", root / "capabilities.json", root / "binding.json")
            for path, value in zip(paths, (requirement_data, capability_data, binding_data), strict=True):
                path.write_text(json.dumps(value), encoding="utf-8")
            report = validate_hardware_contract(
                requirements_path=paths[0], capabilities_path=paths[1], binding_path=paths[2]
            )

        self.assertIn("spi_bus_cs_conflict", {error["code"] for error in report.errors})

    def test_reports_driver_device_speed_mode_fps_and_identity_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirement_data = requirements()
            requirement_data["requirements"].append(  # type: ignore[index]
                {
                    "id": "display",
                    "kind": "spi",
                    "component": "ili9341",
                    "voltage_v": 3.3,
                    "required_drivers": ["spidev"],
                    "min_speed_hz": 10_000_000,
                    "mode": 0,
                    "device": "/dev/spidev0.0",
                }
            )
            capability_data = capabilities()
            capability_data["resources"][1].update(  # type: ignore[index,union-attr]
                {"device": "/dev/video1", "drivers": ["videodev"], "max_fps": 15}
            )
            capability_data["resources"].append(  # type: ignore[index]
                {
                    "id": "spi0.cs0",
                    "kind": "spi",
                    "device": "/dev/spidev0.0",
                    "voltage_v": 3.3,
                    "drivers": ["spidev"],
                    "pinmux": {"id": "spi0", "settings": []},
                    "bus": 0,
                    "chip_select": 0,
                    "max_speed_hz": 1_000_000,
                    "modes": [3],
                    "signal_pins": {"MOSI": "P1", "MISO": "P2", "SCLK": "P3", "CS0": "P4"},
                }
            )
            binding_data = binding()
            binding_data["product"] = "other-product"
            binding_data["mappings"].append(  # type: ignore[index]
                {
                    "requirement": "display",
                    "resource": "spi0.cs0",
                    "physical_pins": ["P1:MOSI", "P2:MISO", "P3:SCLK", "P4:CS0"],
                    "pinmux": "spi0",
                }
            )
            paths = (root / "requirements.json", root / "capabilities.json", root / "binding.json")
            for path, value in zip(paths, (requirement_data, capability_data, binding_data), strict=True):
                path.write_text(json.dumps(value), encoding="utf-8")
            report = validate_hardware_contract(
                requirements_path=paths[0], capabilities_path=paths[1], binding_path=paths[2]
            )

        codes = {error["code"] for error in report.errors}
        self.assertTrue(
            {
                "driver_missing",
                "device_mismatch",
                "video_fps_too_low",
                "spi_speed_too_low",
                "spi_mode_unsupported",
                "product_drift",
            }
            <= codes
        )

    def test_rejects_physical_pin_conflict_and_unknown_pinmux(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capability_data = capabilities()
            capability_data["resources"][1]["signal_pins"] = {"USB": "P12"}  # type: ignore[index]
            binding_data = binding()
            binding_data["mappings"][1]["physical_pin"] = "P12"  # type: ignore[index]
            binding_data["mappings"][2]["pinmux"] = "not-a-target-pinmux"  # type: ignore[index]
            paths = (root / "requirements.json", root / "capabilities.json", root / "binding.json")
            for path, value in zip(paths, (requirements(), capability_data, binding_data), strict=True):
                path.write_text(json.dumps(value), encoding="utf-8")
            report = validate_hardware_contract(
                requirements_path=paths[0], capabilities_path=paths[1], binding_path=paths[2]
            )

        codes = {error["code"] for error in report.errors}
        self.assertIn("physical_pin_conflict", codes)
        self.assertIn("pinmux_mismatch", codes)

    def test_rejects_unsafe_numeric_and_empty_binding_arrays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capability_data = capabilities()
            capability_data["resources"][0]["lines"] = [-1]  # type: ignore[index]
            binding_data = binding()
            binding_data["mappings"][0]["line"] = -1  # type: ignore[index]
            binding_data["mappings"][0]["physical_pins"] = []  # type: ignore[index]
            paths = (root / "requirements.json", root / "capabilities.json", root / "binding.json")
            for path, value in zip(paths, (requirements(), capability_data, binding_data), strict=True):
                path.write_text(json.dumps(value), encoding="utf-8")
            report = validate_hardware_contract(
                requirements_path=paths[0], capabilities_path=paths[1], binding_path=paths[2]
            )

        self.assertFalse(report.ok)
        self.assertEqual({"invalid_schema"}, {error["code"] for error in report.errors})

    def test_json_cli_uses_workspace_contract_defaults_and_writes_only_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirement_path = root / "hardware" / "requirements.json"
            binding_path = root / "hardware" / "bindings" / "luckfox-rk3506.json"
            capability_path = root / "tools" / "targets" / "luckfox-rk3506" / "hardware" / "capabilities.json"
            for path, value in zip(
                (requirement_path, binding_path, capability_path),
                (requirements(), binding(), capabilities()),
                strict=True,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            workspace = Workspace(
                id="rx",
                name="Local/GarStreamRx",
                branch="main",
                connection={"type": "local", "path": str(root)},
                selected_target="luckfox-rk3506",
            )
            output, error = io.StringIO(), io.StringIO()
            with (
                mock.patch("scripts.gar_lib.commands.hw.resolve_workspace", return_value=workspace),
                mock.patch("scripts.gar_lib.commands.hw.gar_tools_root", return_value=root / "tools"),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
            ):
                exit_code = main(["hw", "validate", "--json"])

        self.assertEqual(0, exit_code)
        self.assertEqual("", error.getvalue())
        self.assertTrue(json.loads(output.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
