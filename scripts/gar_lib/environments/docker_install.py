"""Docker Engine installation shared by setup options that require docker."""

from __future__ import annotations

import getpass
import platform
import shutil
from collections.abc import Callable

from scripts.gar_lib.environments.install import print_user_terminal_handoff, sudo_block_reason

DOCKER_INSTALL_COMMANDS = (
    "sudo apt-get update",
    "sudo apt-get install -y docker.io",
    "sudo groupadd -f docker",
    "sudo usermod -aG docker $USER",
    "sudo service docker start || true",
)

GROUP_REFRESH_NOTE = "docker group の反映にはログアウト/再ログインが必要です。"


def is_wsl_or_linux() -> bool:
    release = platform.release().lower()
    return platform.system() == "Linux" or "microsoft" in release


def docker_install_hint() -> str:
    if is_wsl_or_linux():
        return (
            "不足: docker\n"
            "Debian/Ubuntu/WSL では次のコマンドを実行してください。\n"
            "`sudo apt-get update && sudo apt-get install -y docker.io && "
            "sudo groupadd -f docker && sudo usermod -aG docker $USER`\n"
            "必要に応じて Docker daemon を起動してください: "
            "`sudo service docker start`\n"
            f"{GROUP_REFRESH_NOTE}"
        )
    return "不足: docker\nDocker Desktop または Docker Engine をインストールしてください。"


def install_docker(run_command: Callable[[list[str]], int], *, purpose: str) -> int:
    """apt-get で Docker Engine を導入する。sudo が使えない場合は利用者へ委譲する。"""

    if not is_wsl_or_linux() or shutil.which("apt-get") is None:
        print(docker_install_hint())
        return 1

    blocked = sudo_block_reason()
    if blocked:
        print_user_terminal_handoff(
            f"{purpose} のインストールには sudo が必要です。",
            list(DOCKER_INSTALL_COMMANDS),
            reason=blocked,
        )
        return 1

    print(f"{purpose} を apt-get でインストールします。")
    print("sudo のパスワードを求められたら、このターミナルで入力してください。")

    steps = (
        ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "-y", "docker.io"],
        ["sudo", "groupadd", "-f", "docker"],
        ["sudo", "usermod", "-aG", "docker", getpass.getuser()],
    )
    for step in steps:
        result = run_command(list(step))
        if result != 0:
            return result

    run_command(["sudo", "service", "docker", "start"])
    print(GROUP_REFRESH_NOTE)
    return 0
