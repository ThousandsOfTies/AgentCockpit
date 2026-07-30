"""Artifact-kind-to-script build specification."""

from __future__ import annotations

import platform
from collections.abc import Mapping
from dataclasses import dataclass, field

from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace

# simulation host のアーキテクチャ既定値。設定で上書きできる。
DEFAULT_REMOTE_SIM_ARCH = "aarch64"


@dataclass(frozen=True)
class BuildSpec:
    script: str
    variables: Mapping[str, str] = field(default_factory=dict)


def compiler_for_architecture(arch: str) -> str:
    """simulation host のアーキテクチャに対応するCコンパイラを返す。"""

    if arch == platform.machine():
        return "gcc"
    return f"{arch}-linux-gnu-gcc"


def simulation_build_variables(workspace: Workspace) -> dict[str, str]:
    """artifactを動かすsimulation hostのアーキテクチャをbuild hookへ伝える。"""

    simulator = workspace.selected_environments.simulator
    if simulator == "local_docker":
        arch = workspace.docker.arch or platform.machine()
    elif simulator == "ssh_remote":
        arch = workspace.ec2.arch or DEFAULT_REMOTE_SIM_ARCH
    else:
        return {}

    return {
        "GAR_SIM_ENVIRONMENT": simulator,
        "GAR_SIM_ARCH": arch,
        "CC": compiler_for_architecture(arch),
    }


class ProductBuildSpecResolver:
    _SCRIPTS = {
        ArtifactKind.SIM_APP: "scripts/product-sim-build.sh",
        ArtifactKind.SIM_RUNTIME: "scripts/product-sim-env-build.sh",
        ArtifactKind.TARGET_APP: "scripts/product-target-build.sh",
    }
    _SIMULATION_KINDS = (ArtifactKind.SIM_APP, ArtifactKind.SIM_RUNTIME)

    def for_artifact(self, kind: ArtifactKind, workspace: Workspace) -> BuildSpec:
        script = self._SCRIPTS.get(kind)
        if script is None:
            raise GarDomainError(f"この artifact 種別の product build は未対応です: {kind.value}")
        variables = (
            simulation_build_variables(workspace) if kind in self._SIMULATION_KINDS else {}
        )
        return BuildSpec(script=script, variables=variables)
