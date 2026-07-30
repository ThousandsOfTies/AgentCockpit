"""MuJoCo bridge hardware control and HTTP access."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from scripts.gar_lib.simulation.hardware.control import HardwareControlResult

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8081"


class MujocoBridgeHardwareControl:
    """Translate common control-plane operations to the MuJoCo JSON bridge."""

    def __init__(self, bridge_url: str | None = None):
        self.bridge_url = (
            bridge_url or os.environ.get("GAR_MUJOCO_BRIDGE_URL", DEFAULT_BRIDGE_URL)
        ).rstrip("/")

    def gpio(
        self,
        action: str,
        hardware: dict[str, list[dict[str, str]]],
    ) -> HardwareControlResult:
        del hardware
        return HardwareControlResult(
            0,
            {
                "environment": "mujoco",
                "action": action,
                "ok": True,
                "status": "not-applicable",
                "reason": "MuJoCoはLinux GPIOではなくロボット物理を制御します。",
            },
        )

    def io(self, action: str, params: dict[str, object]) -> HardwareControlResult:
        if action == "state":
            payload = bridge_state(self.bridge_url)
            if payload is None:
                return HardwareControlResult(1, {"environment": "mujoco", "ok": False})
            return HardwareControlResult(0, payload)
        status, payload = _bridge_command(self.bridge_url, action, params)
        return HardwareControlResult(
            0 if status < 300 else 1,
            {
                "environment": "mujoco",
                "action": action,
                "ok": status < 300,
                "result": payload,
            },
        )


def bridge_state(bridge_url: str) -> dict[str, object] | None:
    """Read the current MuJoCo bridge state, or return None when unavailable."""

    try:
        with urllib.request.urlopen(f"{bridge_url}/api/state", timeout=2) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _bridge_command(
    bridge_url: str,
    action: str,
    params: dict[str, object],
) -> tuple[int, dict[str, object] | str]:
    body = json.dumps({"action": action, "params": params}).encode("utf-8")
    request = urllib.request.Request(
        f"{bridge_url}/api/command",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
    except urllib.error.URLError as exc:
        return 503, str(exc.reason)
    try:
        decoded = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return 200, raw
    return 200, decoded if isinstance(decoded, dict) else {"value": decoded}
