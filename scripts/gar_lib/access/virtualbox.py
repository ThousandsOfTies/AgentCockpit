"""VirtualBox CLI access without simulation lifecycle decisions."""

from __future__ import annotations

import shutil

from scripts.gar_lib.access.channel import AccessResult, run_cli
from scripts.gar_lib.core.errors import GarDomainError


def virtualbox_executable() -> str:
    executable = shutil.which("VBoxManage") or shutil.which("VBoxManage.exe")
    if executable is None:
        raise GarDomainError("VBoxManageが見つかりません。WindowsへOracle VirtualBoxを導入してください。")
    return executable


class VirtualBoxCliChannel:
    def run(self, arguments: tuple[str, ...]) -> AccessResult:
        return run_cli((virtualbox_executable(), *arguments))
