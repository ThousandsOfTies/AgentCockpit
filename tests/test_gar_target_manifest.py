from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.commands.setup import run_setup
from scripts.gar_lib.environments.setup_option import (
    DevelopmentEnvironmentSetupOption,
    SimulationEnvironmentSetupOption,
    TargetEnvironmentSetupOption,
)
from scripts.gar_lib.target.manifest import (
    TargetManifestValidationError,
    TargetManifestValidationIssue,
    discover_target_manifests,
)


class LocalDevelopmentEnvironment(DevelopmentEnvironmentSetupOption):
    environment_id = "local"
    display_name = "Local"
    description = "local development"


class WokwiSimulationEnvironment(SimulationEnvironmentSetupOption):
    environment_id = "wokwi"
    display_name = "Wokwi"
    description = "Wokwi simulation"


class AdbTargetEnvironment(TargetEnvironmentSetupOption):
    environment_id = "adb_usb"
    display_name = "ADB"
    description = "ADB target"


ENVIRONMENTS = (
    LocalDevelopmentEnvironment,
    WokwiSimulationEnvironment,
    AdbTargetEnvironment,
)


class TargetManifestValidationTest(unittest.TestCase):
    def test_reports_invalid_json_with_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _manifest_path(Path(tmp))
            manifest_path.write_text("{ invalid", encoding="utf-8")

            with (
                mock.patch.dict("os.environ", {"GAR_TOOLS_TARGETS": tmp}),
                self.assertRaises(TargetManifestValidationError) as raised,
            ):
                discover_target_manifests(ENVIRONMENTS)

        issue = raised.exception.issues[0]
        self.assertEqual(manifest_path, issue.path)
        self.assertIn("invalid JSON", issue.message)

    def test_reports_each_missing_required_field(self) -> None:
        payload = _valid_manifest()
        del payload["description"]

        issue = _single_validation_issue(payload)

        self.assertEqual("description", issue.field)
        self.assertIn("required field", issue.message)

    def test_reports_unknown_backend_id_at_default_backend_field(self) -> None:
        payload = _valid_manifest()
        payload["defaultBackends"]["simulator"] = "missing-simulator"

        issue = _single_validation_issue(payload)

        self.assertEqual("defaultBackends.simulator", issue.field)
        self.assertIn("unknown backend id 'missing-simulator'", issue.message)
        self.assertEqual(("wokwi",), issue.candidates)

    def test_reports_backend_registered_in_the_wrong_category(self) -> None:
        payload = _valid_manifest()
        payload["defaultBackends"]["simulator"] = "adb_usb"

        issue = _single_validation_issue(payload)

        self.assertEqual("defaultBackends.simulator", issue.field)
        self.assertIn("belongs to category 'target', not 'simulator'", issue.message)
        self.assertEqual(("wokwi",), issue.candidates)

    def test_preserves_backend_specific_simulation_settings(self) -> None:
        payload = _valid_manifest()
        payload["simulation"] = {
            "docker": {
                "image": "gar-linux-device:latest",
                "publishedHost": "127.0.0.1",
                "publishedBridgePort": 18080,
                "containerBridgePort": 8080,
                "environment": ["GAR_BRIDGE_HOST=0.0.0.0"],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _manifest_path(Path(tmp))
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.dict("os.environ", {"GAR_TOOLS_TARGETS": tmp}):
                manifests = discover_target_manifests(ENVIRONMENTS)

        self.assertEqual(1, len(manifests))
        docker = manifests[0].simulation_settings("docker")
        self.assertEqual("127.0.0.1", docker["publishedHost"])
        self.assertEqual(18080, docker["publishedBridgePort"])
        self.assertEqual(8080, docker["containerBridgePort"])
        self.assertEqual(["GAR_BRIDGE_HOST=0.0.0.0"], docker["environment"])

    def test_setup_prints_manifest_issues_and_fails(self) -> None:
        issue = TargetManifestValidationIssue(
            Path("/gar-tools/targets/broken/target.json"),
            "defaultBackends.target",
            "unknown backend id 'esp32_serial' for category 'target'",
            ("adb_usb", "esp32_esptool"),
        )
        error = TargetManifestValidationError([issue])
        with (
            mock.patch(
                "scripts.gar_lib.commands.setup.command.discover_environments",
                return_value=list(ENVIRONMENTS),
            ),
            mock.patch(
                "scripts.gar_lib.commands.setup.command.discover_target_manifests",
                side_effect=error,
            ),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as stderr,
        ):
            result = run_setup(no_install=True)

        self.assertEqual(1, result)
        self.assertIn(str(issue.path), stderr.getvalue())
        self.assertIn("defaultBackends.target", stderr.getvalue())
        self.assertIn("candidates: adb_usb, esp32_esptool", stderr.getvalue())


def _manifest_path(targets_root: Path) -> Path:
    path = targets_root / "test-target" / "target.json"
    path.parent.mkdir(parents=True)
    return path


def _valid_manifest() -> dict:
    return {
        "id": "test-target",
        "displayName": "Test Target",
        "description": "target used by validation tests",
        "toolsRoot": "targets/test-target",
        "defaultBackends": {
            "codespace": "local",
            "simulator": "wokwi",
            "target": "adb_usb",
        },
    }


def _single_validation_issue(payload: dict) -> TargetManifestValidationIssue:
    with tempfile.TemporaryDirectory() as tmp:
        manifest_path = _manifest_path(Path(tmp))
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch.dict("os.environ", {"GAR_TOOLS_TARGETS": tmp}):
            try:
                discover_target_manifests(ENVIRONMENTS)
            except TargetManifestValidationError as error:
                issues = error.issues
            else:
                raise AssertionError("expected manifest validation to fail")
    if len(issues) != 1:
        raise AssertionError(f"expected one validation issue, got {issues!r}")
    return issues[0]


if __name__ == "__main__":
    unittest.main()
