"""Physical target interfaces independent from concrete access mechanisms."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from scripts.gar_lib.core.artifact import Artifact
from scripts.gar_lib.core.errors import GarDomainError

if TYPE_CHECKING:
    from scripts.gar_lib.target.compatibility import CompatibilityReport


class TargetPlacementError(GarDomainError):
    """A deployment failed after one or more destinations were replaced."""

    def __init__(
        self,
        message: str,
        *,
        placed_destinations: tuple[str, ...],
        placement_complete: bool,
    ):
        if not placed_destinations:
            raise ValueError("TargetPlacementError requires at least one placed destination")
        self.placed_destinations = placed_destinations
        self.placement_complete = placement_complete
        super().__init__(message)

    @property
    def partial(self) -> bool:
        return not self.placement_complete


class TargetEnvironment(Protocol):
    def prepare(self) -> None: ...

    def validate_deployment(self, artifact: Artifact) -> CompatibilityReport | None: ...

    def deploy(self, artifact: Artifact) -> None: ...
