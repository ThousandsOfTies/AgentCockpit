#!/usr/bin/env python3
"""
Run an Gapless Agent Runtime hardware scenario against bridge.py.

The scenario format is intentionally small JSON so AI agents and CI jobs can
generate and execute it without a dedicated test framework.

virtual H/W への操作 step は ``gar sim io`` と同じ語彙（``action`` +
``device``）を使い、endpoint 解決は
:mod:`scripts.gar_lib.simulation.hardware.io_actions` を共有する。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from scripts.gar_lib.simulation.hardware import io_actions  # noqa: E402
except ImportError:  # simulation host へは run_scenario.py と io_actions.py だけを配る
    import io_actions  # type: ignore[no-redef]  # noqa: E402


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
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            raise KeyError(path)
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
            raise AssertionError(
                f"expect failed: {step['path']} == {expected!r}, got {actual!r}"
            )
        return

    if action in io_actions.IO_ACTIONS:
        request = io_actions.resolve(action, step.get("device"), step)
        if request.method == "GET":
            request_json("GET", f"{base_url}{request.path}")
        else:
            post(base_url, request.path, dict(request.fields))
        return

    raise ValueError(f"unknown action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    base_url = args.base_url.rstrip("/")
    print(f"[scenario] {scenario.get('name', args.scenario.name)}")

    try:
        for idx, step in enumerate(scenario.get("steps", []), start=1):
            print(f"[{idx:02d}] {step['action']}")
            run_step(base_url, step)
    except (AssertionError, urllib.error.URLError, ValueError, KeyError) as exc:
        print(f"[scenario] FAIL: {exc}")
        return 1

    print("[scenario] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
