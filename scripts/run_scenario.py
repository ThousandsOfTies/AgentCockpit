#!/usr/bin/env python3
"""Run a Gapless Agent Runtime hardware scenario against a bridge API.

The scenario format is intentionally small JSON so AI agents and CI jobs can
generate and execute it without a dedicated test framework.

virtual H/W への操作 step は ``gar sim io`` と同じ語彙（``action`` +
``device``）を使い、endpoint 解決は
:mod:`scripts.gar_lib.simulation.hardware.io_actions` を共有する。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
STANDALONE_IO_ACTIONS = SCRIPT_PATH.with_name("io_actions.py")

if STANDALONE_IO_ACTIONS.is_file():
    # ``make sim-scenario`` deploys these two files next to each other.
    import io_actions  # type: ignore[no-redef]  # noqa: E402
else:
    sys.path.insert(0, str(SCRIPT_PATH.parent.parent))
    from scripts.gar_lib.simulation.hardware import io_actions  # noqa: E402


class ScenarioError(ValueError):
    """The scenario cannot be executed as written."""


class ScenarioValidationError(ScenarioError):
    """The JSON document does not satisfy the scenario contract."""


@dataclass(frozen=True)
class Scenario:
    name: str
    steps: tuple[dict[str, Any], ...]


def _required_string(step: dict[str, Any], field: str, *, step_number: int) -> str:
    value = step.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ScenarioValidationError(f"step {step_number}: {field} must be a non-empty string")
    return value.strip()


def validate_step(step: dict[str, Any], *, step_number: int) -> None:
    action = _required_string(step, "action", step_number=step_number)

    if action == "wait":
        try:
            seconds = float(step.get("seconds", 1))
        except (TypeError, ValueError) as exc:
            raise ScenarioValidationError(f"step {step_number}: wait seconds must be a number") from exc
        if not math.isfinite(seconds) or seconds < 0:
            raise ScenarioValidationError(f"step {step_number}: wait seconds must be a finite non-negative number")
        return

    if action == "bridge-command":
        _required_string(step, "command", step_number=step_number)
        params = step.get("params", {})
        if not isinstance(params, dict):
            raise ScenarioValidationError(f"step {step_number}: bridge-command params must be an object")
        return

    if action == "expect":
        _required_string(step, "path", step_number=step_number)
        if "equals" not in step:
            raise ScenarioValidationError(f"step {step_number}: expect requires equals")
        return

    if action in io_actions.IO_ACTIONS:
        device = step.get("device")
        if device is not None and not isinstance(device, str):
            raise ScenarioValidationError(f"step {step_number}: device must be a string")
        try:
            io_actions.resolve(action, device, step)
        except (KeyError, TypeError, ValueError) as exc:
            raise ScenarioValidationError(f"step {step_number}: {exc}") from exc
        return

    raise ScenarioValidationError(f"step {step_number}: unknown action: {action}")


def load_scenario(path: Path) -> Scenario:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioValidationError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise ScenarioValidationError(f"cannot read {path}: {exc}") from exc

    if not isinstance(document, dict):
        raise ScenarioValidationError("scenario root must be a JSON object")

    raw_steps = document.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ScenarioValidationError("scenario steps must be a non-empty array")

    steps: list[dict[str, Any]] = []
    for step_number, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict):
            raise ScenarioValidationError(f"step {step_number}: step must be a JSON object")
        step = dict(raw_step)
        validate_step(step, step_number=step_number)
        steps.append(step)

    raw_name = document.get("name", path.name)
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ScenarioValidationError("scenario name must be a non-empty string")
    return Scenario(name=raw_name.strip(), steps=tuple(steps))


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as res:
        body = res.read().decode("utf-8")
    return json.loads(body) if body else None


def get_path(obj: Any, path: str) -> Any:
    cur = obj
    try:
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur[part]
            elif isinstance(cur, list):
                cur = cur[int(part)]
            else:
                raise KeyError(part)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise ScenarioError(f"state path does not exist: {path}") from exc
    return cur


def post(base_url: str, endpoint: str, payload: dict[str, Any] | None = None) -> Any:
    return request_json("POST", f"{base_url}{endpoint}", payload or {})


def run_step(base_url: str, step: dict[str, Any]) -> None:
    action = step["action"]

    if action == "wait":
        time.sleep(float(step.get("seconds", 1)))
        return

    if action == "bridge-command":
        command = step.get("command")
        if not isinstance(command, str) or not command:
            raise ValueError("bridge-command requires a non-empty command")
        params = step.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("bridge-command params must be an object")
        post(base_url, "/api/command", {"action": command, "params": params})
        return

    if action == "expect":
        state = request_json("GET", f"{base_url}{io_actions.STATE_PATH}")
        actual = get_path(state, step["path"])
        expected = step["equals"]
        if actual != expected:
            raise AssertionError(f"expect failed: {step['path']} == {expected!r}, got {actual!r}")
        return

    if action in io_actions.IO_ACTIONS:
        request = io_actions.resolve(action, step.get("device"), step)
        if request.method == "GET":
            request_json("GET", f"{base_url}{request.path}")
        else:
            post(base_url, request.path, dict(request.fields))
        return

    raise ValueError(f"unknown action: {action}")


def execute_scenario(base_url: str, scenario: Scenario) -> None:
    for step_number, step in enumerate(scenario.steps, start=1):
        print(f"[{step_number:02d}] {step['action']}")
        run_step(base_url, step)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args(argv)
    base_url = args.base_url.rstrip("/")

    try:
        scenario = load_scenario(args.scenario)
        print(f"[scenario] {scenario.name}")
        execute_scenario(base_url, scenario)
    except (
        AssertionError,
        OSError,
        ScenarioError,
        TimeoutError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ) as exc:
        print(f"[scenario] FAIL: {exc}")
        return 1

    print("[scenario] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
