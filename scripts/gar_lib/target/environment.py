"""Physical target interfaces independent from concrete access mechanisms."""

from __future__ import annotations

from typing import Protocol

from scripts.gar_lib.core.artifact import Artifact


class TargetEnvironment(Protocol):
    def deploy(self, artifact: Artifact) -> None: ...
