"""Setup registry metadata for the AWS SSM simulation connection."""

from __future__ import annotations

from scripts.gar_lib.environments.installers.aws_ssm import (
    aws_ssm_install_hint,
    install_aws_ssm_dependencies,
)
from scripts.gar_lib.environments.setup_option import SimulationEnvironmentSetupOption


class AwsSsmEnvironment(SimulationEnvironmentSetupOption):
    environment_id = "aws_ssm"
    display_name = "AWS SSM (非推奨)"
    description = "runtime componentは接続済みですが、各操作は現在stubです。" "simulationにはSSH Remoteを使ってください"
    display_order = 20
    required_commands = ("aws", "session-manager-plugin")

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        return aws_ssm_install_hint(missing)

    @classmethod
    def install_dependencies(cls, missing: list[str]) -> int:
        return install_aws_ssm_dependencies(
            missing,
            run_command=cls.run_install_command,
        )
