from __future__ import annotations

from scripts.gar_lib.environments._base import EnvironmentSetupOption
from scripts.gar_lib.environments.docker_install import docker_install_hint, install_docker


class LocalDockerEnvironment(EnvironmentSetupOption):
    environment_id = "local_docker"
    display_name = "Local Docker"
    description = (
        "ローカルの container を simulation host として使います。"
        "GPIO は host kernel の gpio-sim に依存するため Linux 5.17 以降が必要です"
    )
    display_order = 5
    required_commands = ("docker",)

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        if "docker" not in missing:
            return super().install_hint(missing)
        return (
            f"{docker_install_hint()}\n"
            "導入後に `gar sim gpio check` で host kernel の gpio-sim 有無を確認できます。"
        )

    @classmethod
    def install_dependencies(cls, missing: list[str]) -> int:
        if "docker" not in missing:
            print(cls.install_hint(missing))
            return 1
        result = install_docker(cls.run_install_command, purpose="Local Docker simulation host")
        if result == 0:
            print("導入後に `gar sim gpio check` で host kernel の gpio-sim 有無を確認できます。")
        return result
