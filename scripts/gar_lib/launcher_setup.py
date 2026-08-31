"""Interactive, user-scoped PATH registration for the GAR launcher."""

from __future__ import annotations

import ctypes
import ntpath
import os
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO


def offer_scripts_path_registration(
    scripts_dir: Path,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> int:
    """Offer one persistent, user-scoped PATH entry and skip duplicates."""

    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    environment = environ or os.environ
    platform_name = platform or os.name
    scripts = str(scripts_dir.resolve())

    if _path_contains(environment.get("PATH", ""), scripts, platform=platform_name):
        print(f"PATH登録済みのためSKIPします: {scripts}", file=output_stream)
        return 0

    if platform_name == "nt":
        try:
            saved_path, value_type = _read_windows_user_path()
        except OSError as error:
            print(f"WindowsのユーザーPATHを確認できません: {error}", file=output_stream)
            return 1
        if _path_contains(saved_path, scripts, platform="nt"):
            print(f"PATH登録済みのためSKIPします: {scripts}", file=output_stream)
            return 0
        registration = ("windows", saved_path, value_type)
    else:
        profile = _posix_shell_profile(environment)
        try:
            profile_text = profile.read_text(encoding="utf-8") if profile.exists() else ""
        except OSError as error:
            print(f"shell profileを確認できません: {profile}: {error}", file=output_stream)
            return 1
        if scripts in profile_text:
            print(f"PATH登録済みのためSKIPします: {scripts}", file=output_stream)
            return 0
        registration = ("posix", profile, profile_text)

    if not input_stream.isatty():
        print("非対話実行のためPATH登録をSKIPします。", file=output_stream)
        return 0

    output_stream.write("GARのscripts directoryをユーザーPATHへ登録しますか? [Y/n]: ")
    output_stream.flush()
    answer = input_stream.readline()
    if not answer or answer.strip().lower() not in {"", "y", "yes"}:
        print("PATH登録をSKIPしました。", file=output_stream)
        return 0

    try:
        if registration[0] == "windows":
            saved_path = registration[1]
            assert isinstance(saved_path, str)
            value_type = registration[2]
            assert isinstance(value_type, int)
            updated = f"{saved_path.rstrip(';')};{scripts}" if saved_path else scripts
            _write_windows_user_path(updated, value_type)
            _broadcast_windows_environment_change()
        else:
            profile = registration[1]
            assert isinstance(profile, Path)
            profile_text = registration[2]
            assert isinstance(profile_text, str)
            _append_posix_path(profile, profile_text, scripts)
    except OSError as error:
        print(f"PATHへ登録できませんでした: {error}", file=output_stream)
        return 1

    print(f"PATHへ登録しました: {scripts}", file=output_stream)
    print("新しいterminalを開くと `gar` commandを使用できます。", file=output_stream)
    return 0


def _path_contains(value: str, scripts: str, *, platform: str) -> bool:
    separator = ";" if platform == "nt" else ":"
    expected = _normalized_path(scripts, platform=platform)
    return any(
        _normalized_path(entry, platform=platform) == expected for entry in value.split(separator) if entry.strip()
    )


def _normalized_path(value: str, *, platform: str) -> str:
    cleaned = value.strip().strip('"')
    if platform == "nt":
        return ntpath.normcase(ntpath.normpath(ntpath.expandvars(cleaned)))
    return os.path.normpath(cleaned)


def _read_windows_user_path() -> tuple[str, int]:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, value_type = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        return "", winreg.REG_EXPAND_SZ
    return (value if isinstance(value, str) else "", value_type)


def _write_windows_user_path(value: str, value_type: int) -> None:
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", access=winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Path", 0, value_type, value)


def _broadcast_windows_environment_change() -> None:
    if not hasattr(ctypes, "windll"):
        return
    hwnd_broadcast = 0xFFFF
    wm_settingchange = 0x001A
    send_timeout_abort_if_hung = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        hwnd_broadcast,
        wm_settingchange,
        0,
        "Environment",
        send_timeout_abort_if_hung,
        5000,
        None,
    )


def _posix_shell_profile(environ: Mapping[str, str]) -> Path:
    home = Path(environ.get("HOME") or Path.home()).expanduser()
    shell = Path(environ.get("SHELL", "")).name
    if shell == "zsh":
        return home / ".zshrc"
    if shell == "bash":
        return home / ".bashrc"
    return home / ".profile"


def _append_posix_path(profile: Path, existing: str, scripts: str) -> None:
    profile.parent.mkdir(parents=True, exist_ok=True)
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    line = f'# Added by Gapless Agent Runtime\nexport PATH={shlex.quote(scripts)}:"$PATH"\n'
    with profile.open("a", encoding="utf-8") as output:
        output.write(prefix + line)
