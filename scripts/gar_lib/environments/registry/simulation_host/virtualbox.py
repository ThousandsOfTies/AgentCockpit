from __future__ import annotations

from scripts.gar_lib.environments.setup_option import SimulationHostSetupOption


class VirtualBoxSimulationHostSetup(SimulationHostSetupOption):
    environment_id = "virtualbox"
    display_name = "Local Ubuntu (VirtualBox)"
    description = "gpio_simを使うローカルUbuntu VMをVBoxManageとSSHで操作します"
    display_order = 5
    required_commands = ("VBoxManage", "ssh", "scp")

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        return (
            f"不足: {', '.join(missing)}\n"
            "WindowsへOracle VirtualBoxとOpenSSH Clientを導入し、VBoxManageをPATHへ追加してください。"
        )
