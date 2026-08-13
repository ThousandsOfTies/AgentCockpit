"""virtual H/W への操作を (action, device) から Bridge API へ解決する単一の定義元。

Bridge の機械向けクライアントは2つある。

* ``gar sim io``（AI 向け / :mod:`scripts.gar_lib.simulation.runtime.linux_commands` が curl を組み立てる）
* JSON scenario runner（CI 向け / :mod:`scripts.run_scenario` が HTTP を直接叩く）

両者が別々に endpoint を持つと語彙が割れるため、解決はこのモジュールへ集約する。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

STATE_PATH = "/api/state"

DEFAULT_BUTTON_LINE = 17
DEFAULT_PRESS_DURATION_MS = 150

BUTTON_LINE_ALIASES = {
    "a": 17,
    "power": 17,
    "power_button": 17,
    "b": 27,
    "aux": 27,
    "aux_button": 27,
}

IO_ACTIONS = ("state", "press", "set", "clear", "rotate")
IO_DEVICES = ("button", "rfid", "range", "rotary")


@dataclass(frozen=True)
class IoRequest:
    """Bridge へ送る1操作。transport（curl / urllib）に依存しない形で表す。"""

    method: str
    path: str
    fields: dict[str, str | int]


def resolve_button_line(params: Mapping[str, object]) -> int:
    value = str(params.get("line") or params.get("button") or DEFAULT_BUTTON_LINE)
    if value.isdigit():
        return int(value)
    key = value.strip().lower()
    if key in BUTTON_LINE_ALIASES:
        return BUTTON_LINE_ALIASES[key]
    raise ValueError(f"unknown button: {value}")


def resolve(action: str, device: str | None, params: Mapping[str, object]) -> IoRequest:
    """``(action, device, params)`` を Bridge の1リクエストへ解決する。"""

    if action == "state":
        return IoRequest("GET", STATE_PATH, {})

    if not device:
        raise ValueError(f"io {action} には device の指定が必要です。")

    if device == "button":
        if action == "press":
            duration = params.get("duration_ms")
            duration_ms = int(DEFAULT_PRESS_DURATION_MS if duration is None else duration)
            return IoRequest(
                "POST",
                "/api/button/press",
                {"line": resolve_button_line(params), "duration_ms": max(0, duration_ms)},
            )
        if action == "set":
            return IoRequest(
                "POST",
                "/api/button",
                {
                    "line": resolve_button_line(params),
                    "value": 1 if int(params.get("value", 1)) else 0,
                },
            )
    elif device == "rfid":
        if action == "set":
            return IoRequest("POST", "/api/rfid/tap", {"uid": str(params["uid"])})
        if action == "clear":
            return IoRequest("POST", "/api/rfid/remove", {})
    elif device == "range":
        if action == "set":
            return IoRequest("POST", "/api/range", {"value": int(params["value"])})
    elif device == "rotary":
        if action == "rotate":
            direction = int(params.get("direction", 1))
            if direction not in {-1, 1}:
                raise ValueError("rotary direction must be -1 or 1")
            return IoRequest("POST", "/api/rotary/rotate", {"direction": direction})
        if action == "press":
            return IoRequest("POST", "/api/rotary/press", {})
    else:
        raise ValueError(f"unknown io device: {device}")

    raise ValueError(f"io {action} は device={device} では未対応です。")
