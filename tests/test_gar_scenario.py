from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_scenario


class ScenarioLoadingTest(unittest.TestCase):
    def test_load_scenario_rejects_an_empty_step_list(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scenario_path = Path(temporary_directory) / "empty.json"
            scenario_path.write_text('{"name": "empty", "steps": []}\n', encoding="utf-8")

            with self.assertRaisesRegex(run_scenario.ScenarioValidationError, "non-empty array"):
                run_scenario.load_scenario(scenario_path)

    def test_load_scenario_validates_every_step_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scenario_path = Path(temporary_directory) / "invalid-second-step.json"
            scenario_path.write_text(
                json.dumps(
                    {
                        "name": "invalid second step",
                        "steps": [
                            {"action": "state"},
                            {"action": "expect", "path": "gpio.button"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(run_scenario.ScenarioValidationError, "step 2.*equals"):
                run_scenario.load_scenario(scenario_path)

    def test_main_reports_invalid_json_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scenario_path = Path(temporary_directory) / "invalid.json"
            scenario_path.write_text("{ invalid", encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                result = run_scenario.main([str(scenario_path)])

            self.assertEqual(1, result)
            self.assertIn("[scenario] FAIL: invalid JSON", output.getvalue())


class ScenarioExecutionTest(unittest.TestCase):
    def test_expect_reads_a_nested_state_value(self) -> None:
        with mock.patch.object(
            run_scenario,
            "request_json",
            return_value={"spi": {"reader": {"present": True}}},
        ):
            run_scenario.run_step(
                "http://127.0.0.1:8080",
                {
                    "action": "expect",
                    "path": "spi.reader.present",
                    "equals": True,
                },
            )

    def test_get_path_describes_a_missing_value(self) -> None:
        with self.assertRaisesRegex(run_scenario.ScenarioError, "state path does not exist: values.2"):
            run_scenario.get_path({"values": [1]}, "values.2")

    def test_main_executes_a_valid_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            scenario_path = Path(temporary_directory) / "state.json"
            scenario_path.write_text(
                json.dumps(
                    {
                        "name": "read state",
                        "steps": [{"action": "state"}],
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                mock.patch.object(run_scenario, "request_json", return_value={"ok": True}) as request,
                contextlib.redirect_stdout(output),
            ):
                result = run_scenario.main([str(scenario_path), "--base-url", "http://bridge:8080/"])

            self.assertEqual(0, result)
            request.assert_called_once_with("GET", "http://bridge:8080/api/state")
            self.assertIn("[scenario] PASS", output.getvalue())


if __name__ == "__main__":
    unittest.main()
