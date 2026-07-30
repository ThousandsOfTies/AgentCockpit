"""Simulation hardware control plane independent from transport details."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from scripts.gar_lib.access.channel import AccessResult, CommandChannel
from scripts.gar_lib.simulation.diagnostics.parse import parse_gpio_runtime_status, parse_gpio_sim_check
from scripts.gar_lib.simulation.runtime.linux_commands import LinuxSystemdCommandBuilder, gpio_sim_plan


@dataclass(frozen=True)
class HardwareControlResult:
    exit_code: int
    payload: dict[str, object] | None = None
    stdout: str = ""
    stderr: str = ""


class SimulationHardwareControl(Protocol):
    def gpio(
        self,
        action: str,
        hardware: dict[str, list[dict[str, str]]],
    ) -> HardwareControlResult: ...

    def io(self, action: str, params: dict[str, object]) -> HardwareControlResult: ...


class LinuxBridgeHardwareControl:
    def __init__(
        self,
        command_channel: CommandChannel,
        command_builder: LinuxSystemdCommandBuilder,
        *,
        host: str | None = None,
    ):
        self.command_channel = command_channel
        self.command_builder = command_builder
        self.host = host

    def gpio(
        self,
        action: str,
        hardware: dict[str, list[dict[str, str]]],
    ) -> HardwareControlResult:
        if action == "plan":
            return HardwareControlResult(0, self._with_host(gpio_sim_plan(hardware)))
        if action == "install":
            return self._command(self.command_builder.build_gpio_systemd_install(hardware))
        if action == "start":
            return self._command(self.command_builder.build_gpio_systemd_start(hardware))
        if action == "stop":
            return self._command("sudo systemctl stop gar-gpio-sim.service")
        if action == "status":
            result = self.command_channel.run(self.command_builder.build_gpio_runtime_status(hardware))
            payload = (
                parse_gpio_runtime_status(result.stdout) if result.returncode == 0 else self._error_payload(result)
            )
            return HardwareControlResult(
                result.returncode if result.returncode else (0 if payload.get("ok") else 1),
                self._with_host(payload),
                result.stdout,
                result.stderr,
            )
        if action == "check":
            result = self.command_channel.run(self.command_builder.build_gpio_sim_check())
            payload = parse_gpio_sim_check(result.stdout) if result.returncode == 0 else self._error_payload(result)
            return HardwareControlResult(
                result.returncode if result.returncode else (0 if payload.get("ok") else 1),
                self._with_host(payload),
                result.stdout,
                result.stderr,
            )
        return HardwareControlResult(1, {"ok": False, "error": f"unknown gpio action: {action}"})

    def io(self, action: str, params: dict[str, object]) -> HardwareControlResult:
        result = self.command_channel.run(self.command_builder.build_io(action, params))
        if action != "state":
            return HardwareControlResult(result.returncode, stdout=result.stdout, stderr=result.stderr)
        try:
            payload = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            payload = {"ok": False, "raw": result.stdout.strip()}
        if not isinstance(payload, dict):
            payload = {"ok": False, "state": payload}
        exit_code = result.returncode or (1 if payload.get("ok") is False else 0)
        return HardwareControlResult(exit_code, payload, result.stdout, result.stderr)

    def _command(self, command: str) -> HardwareControlResult:
        result = self.command_channel.run(command)
        return HardwareControlResult(result.returncode, stdout=result.stdout, stderr=result.stderr)

    def _with_host(self, payload: dict) -> dict[str, object]:
        return {**payload, **({"host": self.host} if self.host else {})}

    @staticmethod
    def _error_payload(result: AccessResult) -> dict[str, object]:
        return {
            "ok": False,
            "error": f"command exited {result.returncode}",
            "stderr": result.stderr.strip(),
        }
