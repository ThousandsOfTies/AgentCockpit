"""Setup registry metadata for the Renode MCU simulator."""

from __future__ import annotations

from scripts.gar_lib.environments.installers.renode import (
    install_renode_dependencies,
    renode_dependency_status,
    renode_install_hint,
)
from scripts.gar_lib.environments.setup_option import (
    DependencyStatus,
    SimulationEnvironmentSetupOption,
)


class RenodeMcuEnvironment(SimulationEnvironmentSetupOption):
    environment_id = "renode_mcu"
    display_name = "Renode (MCU/ベアメタル)"
    description = (
        "Cortex-M / RISC-V などの MCU ファームを命令セットエミュレータで仮想実行します"
        "（未改変バイナリを sim と実機で共有。runtime操作は現在stub）"
    )
    display_order = 10
    required_commands = ("renode", "renode-test")

    @classmethod
    def dependency_status(cls) -> list[DependencyStatus]:
        return renode_dependency_status()

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        return renode_install_hint(missing)

    @classmethod
    def install_dependencies(cls, missing: list[str]) -> int:
        return install_renode_dependencies(missing)
