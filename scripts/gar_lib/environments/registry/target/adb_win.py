"""Windows-native ADB device environment (called from WSL via interop).

方式2: USB-C 実機は Windows がネイティブ認識し、WSL からは Windows の
``adb.exe`` を直接呼ぶ。``usbipd-win`` による attach/bind は不要。

ローカル側（WSL）のファイルパスのみ ``wslpath -w`` で Windows 形式へ変換して
``adb.exe`` に渡す。device 側のパス（dest）は Linux のままで変換しない。

``adb.exe`` の場所は ``gar setup`` 時に確定し、``.gar/config.json`` の
``adb.exe_path`` に保存する。実行時は 保存パス > PATH 上の ``adb.exe`` の順で解決する。
"""

from __future__ import annotations

import shutil
import subprocess

from scripts.gar_lib.core.config import (
    save_config,
    saved_adb_exe,
    set_saved_adb_exe,
)
from scripts.gar_lib.environments.setup_option import TargetEnvironmentSetupOption

# winget の Android Platform Tools パッケージ ID。
WINGET_PACKAGE_ID = "Google.PlatformTools"


class AdbWinEnvironment(TargetEnvironmentSetupOption):
    environment_id = "adb_win"
    display_name = "ADB (Windows native)"
    description = "Windows ネイティブの adb.exe を WSL から呼び出して USB-C 実機へ接続します" "（usbipd 不要）"
    display_order = 15
    required_commands = ("adb.exe",)

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        return (
            "Windows 側に Android Platform Tools (adb.exe) をインストールしてください。\n"
            "  winget install --exact --id Google.PlatformTools\n"
            "インストール後、adb.exe が Windows の PATH に含まれるようにしてください。"
        )

    @classmethod
    def install_dependencies(cls, missing: list[str]) -> int:
        winget = shutil.which("winget.exe")
        if winget is None:
            print(cls.install_hint(missing))
            return 1

        print("Windows へ Android Platform Tools を winget でインストールします。")
        result = cls.run_install_command(
            [
                winget,
                "install",
                "--exact",
                "--id",
                WINGET_PACKAGE_ID,
                "--accept-source-agreements",
                "--accept-package-agreements",
            ]
        )
        if result != 0:
            print(cls.install_hint(missing))
            return result

        return 0

    @classmethod
    def record_detected_configuration(cls, config: dict) -> None:
        """Record the detected executable in the selected workspace config."""

        cls.remember_adb_exe(config)

    @classmethod
    def remember_adb_exe(cls, config: dict) -> str | None:
        """Resolve adb.exe and save it to the explicitly supplied config."""
        exe = shutil.which("adb.exe")
        if exe is None:
            return None

        version = None
        proc = subprocess.run(
            [exe, "version"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            version = proc.stdout.strip().splitlines()[0].strip()

        if saved_adb_exe(config) != exe:
            set_saved_adb_exe(config, exe, version=version)
            save_config(config)
        return exe
