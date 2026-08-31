from __future__ import annotations

from scripts.gar_lib.environments.setup_option import SimulationHostSetupOption


class AwsEc2SimulationHostSetup(SimulationHostSetupOption):
    environment_id = "aws_ec2"
    display_name = "Remote Ubuntu (AWS EC2)"
    description = "AWS EC2 Ubuntuをremote Sim HostとしてAWS CLIとSSHで操作します"
    display_order = 10
    required_commands = ("aws", "ssh", "scp")

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        return f"不足: {', '.join(missing)}\nAWS CLIとOpenSSH Clientを導入してください。"
