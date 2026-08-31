from __future__ import annotations

from scripts.gar_lib.environments.setup_option import SimulationEnvironmentSetupOption


class SshRemoteEnvironment(SimulationEnvironmentSetupOption):
    environment_id = "ssh_remote"
    display_name = "Ubuntu Device Simulation (SSH)"
    description = "VirtualBoxまたはAWS上の共通Ubuntu runtimeへSSHで接続します"
    display_order = 30
    required_commands = ("ssh",)

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        commands = ", ".join(missing)
        return f"不足: {commands}\nOpenSSH client をインストールしてください。"
