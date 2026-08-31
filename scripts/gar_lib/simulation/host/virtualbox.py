"""VirtualBox implementation of the local Ubuntu SimulationHost."""

from __future__ import annotations

import json
import shlex

from scripts.gar_lib.access.channel import AccessResult, CommandChannel
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.simulation.host.contract import SimulationHostStartResult, SimulationHostState

BACKEND_ID = "virtualbox"


class VirtualBoxSimulationHostController:
    def __init__(
        self,
        *,
        vm: str,
        host: str,
        virtualbox,
        repository_channel: CommandChannel,
        repository_path: str | None = None,
    ):
        self.vm = vm
        self.host = host
        self.virtualbox = virtualbox
        self.repository_channel = repository_channel
        self.repository_path = repository_path

    def start(
        self,
        *,
        update_address: bool = True,
        update_repository: bool = False,
    ) -> SimulationHostStartResult:
        del update_address
        state = self.status()
        if state.state == "paused":
            self._require_success(
                self.virtualbox.run(("controlvm", self.vm, "resume")),
                "VirtualBox Ubuntu VMの再開に失敗しました",
            )
            state = self.status()
        elif not state.running:
            self._require_success(
                self.virtualbox.run(("startvm", self.vm, "--type", "headless")),
                "VirtualBox Ubuntu VMの起動に失敗しました",
            )
            state = self.status()
        if not state.running:
            raise GarDomainError(f"VirtualBox Ubuntu VMがrunningではありません: {state.state}")

        repository_updated = False
        repository_update_skipped = False
        if update_repository:
            if self.repository_path:
                result = self.repository_channel.run(f"cd {shlex.quote(self.repository_path)} && git pull --ff-only")
                self._require_success(result, "local Sim Host上のgit pullに失敗しました")
                repository_updated = True
            else:
                repository_update_skipped = True

        return SimulationHostStartResult(
            state=state,
            address_updated=False,
            repository_updated=repository_updated,
            repository_update_skipped=repository_update_skipped,
        )

    def stop(self) -> None:
        state = self.status()
        if state.state in {"poweroff", "saved", "aborted"}:
            return
        if state.state == "paused":
            self._require_success(
                self.virtualbox.run(("controlvm", self.vm, "resume")),
                "VirtualBox Ubuntu VMの再開に失敗しました",
            )
        self._require_success(
            self.virtualbox.run(("controlvm", self.vm, "acpipowerbutton")),
            "VirtualBox Ubuntu VMへACPI shutdownを要求できませんでした",
        )

    def status(self) -> SimulationHostState:
        result = self.virtualbox.run(("showvminfo", self.vm, "--machinereadable"))
        self._require_success(result, "VirtualBox Ubuntu VMの状態を取得できませんでした")
        values = _machine_readable_values(result.stdout)
        state = values.get("VMState") or "unknown"
        return SimulationHostState(
            host=self.host,
            backend=BACKEND_ID,
            id=self.vm,
            state=state,
            details={
                "vm": self.vm,
                **({"state_changed": values["VMStateChangeTime"]} if values.get("VMStateChangeTime") else {}),
            },
        )

    @staticmethod
    def _require_success(result: AccessResult, message: str) -> None:
        if result.returncode == 0:
            return
        detail = (result.stderr or result.stdout).strip()
        raise GarDomainError(f"{message} (exit {result.returncode})" + (f": {detail}" if detail else ""))


def _machine_readable_values(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        name, separator, raw_value = line.partition("=")
        if not separator or not name:
            continue
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed = raw_value
        if isinstance(parsed, str):
            values[name] = parsed
    return values
