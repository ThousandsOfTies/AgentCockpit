from __future__ import annotations

from scripts.gar_lib.environments.docker_install import docker_install_hint, install_docker
from scripts.gar_lib.environments.setup_option import DevelopmentEnvironmentSetupOption


class LocalDockerDevelopmentSetup(DevelopmentEnvironmentSetupOption):
    environment_id = "local"
    display_name = "Local Docker"
    description = "このマシン上のローカル Docker/devcontainer 環境を使います"
    display_order = 5
    required_commands = ("docker",)

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        if "docker" not in missing:
            return super().install_hint(missing)
        return docker_install_hint()

    @classmethod
    def install_dependencies(cls, missing: list[str]) -> int:
        if "docker" not in missing:
            print(cls.install_hint(missing))
            return 1
        return install_docker(cls.run_install_command, purpose="Local Docker")


# Import compatibility for integrations that used the old ambiguous name.
LocalDockerEnvironment = LocalDockerDevelopmentSetup
