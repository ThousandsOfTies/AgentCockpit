"""Simulation host lifecycle interfaces and results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SimulationHostState:
    """simulation hostの状態。backend実装の語彙をこの層に持ち込まない。"""

    host: str
    backend: str
    id: str
    state: str
    address: str | None = None
    details: Mapping[str, str] = field(default_factory=dict)

    @property
    def running(self) -> bool:
        return self.state == "running"

    def to_payload(self) -> dict[str, object]:
        return {
            "command": "sim host status",
            "backend": self.backend,
            "id": self.id,
            "state": self.state,
            "address": self.address,
            "running": self.running,
            "details": dict(self.details),
            "ok": True,
        }


@dataclass(frozen=True)
class SimulationHostStartResult:
    state: SimulationHostState
    address_updated: bool
    repository_updated: bool
    repository_update_skipped: bool


class SimulationHostController(Protocol):
    def start(
        self,
        *,
        update_address: bool = True,
        update_repository: bool = False,
    ) -> SimulationHostStartResult: ...

    def stop(self) -> None: ...

    def status(self) -> SimulationHostState: ...
