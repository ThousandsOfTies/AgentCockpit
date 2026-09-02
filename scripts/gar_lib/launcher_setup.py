"""Interactive, user-scoped PATH registration for the GAR launcher."""

from __future__ import annotations

import ctypes
import ntpath
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

from scripts.gar_lib.commands.completion import (
    completion_bash_script,
    completion_powershell_script,
    completion_zsh_script,
)

COMPLETION_BLOCK_START = "# >>> Gapless Agent Runtime completion >>>"
COMPLETION_BLOCK_END = "# <<< Gapless Agent Runtime completion <<<"


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
    environment = os.environ if environ is None else environ
    platform_name = platform or os.name
    scripts = str(scripts_dir.resolve())

    if _path_contains(environment.get("PATH", ""), scripts, platform=platform_name):
        print(f"現在のPATHでgarを使用できます: {scripts}", file=output_stream)
        return 0

    if platform_name == "nt":
        try:
            saved_path, value_type = _read_windows_user_path()
        except OSError as error:
            print(f"WindowsのユーザーPATHを確認できません: {error}", file=output_stream)
            return 1
        if _path_contains(saved_path, scripts, platform="nt"):
            _print_path_activation_notice(scripts, platform="nt", output=output_stream)
            return 0
        registration = ("windows", saved_path, value_type)
    else:
        profile = _posix_shell_profile(environment)
        try:
            profile_text = profile.read_text(encoding="utf-8") if profile.exists() else ""
        except OSError as error:
            print(f"shell profileを確認できません: {profile}: {error}", file=output_stream)
            return 1
        if _posix_path_line(scripts) in profile_text:
            _print_path_activation_notice(scripts, platform="posix", output=output_stream)
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
    _print_path_activation_notice(scripts, platform=platform_name, output=output_stream)
    return 0


def offer_shell_completion_registration(
    scripts_dir: Path,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> int:
    """Offer an idempotent user-profile hook for the current platform's shell."""

    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    environment = os.environ if environ is None else environ
    platform_name = platform or os.name
    scripts = scripts_dir.resolve()
    plan = _completion_registration_plan(scripts, environment, platform=platform_name)
    if plan is None:
        shell = "PowerShell" if platform_name == "nt" else Path(environment.get("SHELL", "")).name or "unknown"
        print(f"{shell}の補完登録先を検出できないためSKIPします。", file=output_stream)
        return 0

    shell_name, completion_path, completion_text, profiles, profile_block = plan
    try:
        completion_current = completion_path.exists() and completion_path.read_text(encoding="utf-8") == completion_text
        profiles_current = all(
            profile.exists() and profile_block in profile.read_text(encoding="utf-8") for profile in profiles
        )
    except OSError as error:
        print(f"{shell_name}補完の登録状態を確認できません: {error}", file=output_stream)
        return 1

    if completion_current and profiles_current:
        print(f"{shell_name}補完は登録済みです: {completion_path}", file=output_stream)
        return 0

    if not input_stream.isatty():
        print(f"非対話実行のため{shell_name}補完登録をSKIPします。", file=output_stream)
        return 0

    output_stream.write(f"GARの{shell_name} Tab補完をユーザーprofileへ登録しますか? [Y/n]: ")
    output_stream.flush()
    answer = input_stream.readline()
    if not answer or answer.strip().lower() not in {"", "y", "yes"}:
        print(f"{shell_name}補完登録をSKIPしました。", file=output_stream)
        return 0

    try:
        completion_path.parent.mkdir(parents=True, exist_ok=True)
        completion_path.write_text(completion_text, encoding="utf-8")
        for profile in profiles:
            _upsert_completion_profile(profile, profile_block)
    except OSError as error:
        print(f"{shell_name}補完を登録できませんでした: {error}", file=output_stream)
        return 1

    print(f"{shell_name}補完を登録しました: {completion_path}", file=output_stream)
    print("terminal hostをいったん終了して開き直すとTab補完を使用できます。", file=output_stream)
    return 0


def _completion_registration_plan(
    scripts_dir: Path,
    environ: Mapping[str, str],
    *,
    platform: str,
) -> tuple[str, Path, str, list[Path], str] | None:
    completion_dir = scripts_dir.parent / ".gar" / "completion"
    if platform == "nt":
        profiles = _windows_powershell_profiles(environ)
        if not profiles:
            return None
        launcher = str(scripts_dir / "gar.cmd")
        completion_path = completion_dir / "gar.ps1"
        completion_text = completion_powershell_script(launcher)
        quoted_path = str(completion_path).replace("'", "''")
        source_line = f"if (Test-Path -LiteralPath '{quoted_path}') {{ . '{quoted_path}' }}"
        return (
            "PowerShell",
            completion_path,
            completion_text,
            profiles,
            _managed_completion_block(source_line),
        )

    shell = Path(environ.get("SHELL", "")).name
    launcher = str(scripts_dir / "gar")
    if shell == "bash":
        completion_path = completion_dir / "gar.bash"
        completion_text = completion_bash_script(launcher)
        shell_name = "Bash"
    elif shell == "zsh":
        completion_path = completion_dir / "_gar"
        completion_text = completion_zsh_script(launcher)
        shell_name = "Zsh"
    else:
        return None
    profile = _posix_shell_profile(environ)
    source_line = f"[ ! -f {shlex.quote(str(completion_path))} ] || . {shlex.quote(str(completion_path))}"
    return (
        shell_name,
        completion_path,
        completion_text,
        [profile],
        _managed_completion_block(source_line),
    )


def _windows_powershell_profiles(environ: Mapping[str, str]) -> list[Path]:
    profiles: list[Path] = []
    command = "[Console]::Out.Write($PROFILE.CurrentUserAllHosts)"
    for executable in ("pwsh.exe", "powershell.exe"):
        resolved = shutil.which(executable)
        if resolved is None:
            continue
        try:
            result = subprocess.run(
                [resolved, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        value = result.stdout.strip()
        if result.returncode == 0 and value:
            profile = Path(value)
            if profile not in profiles:
                profiles.append(profile)
    if profiles:
        return profiles

    user_profile = environ.get("USERPROFILE")
    if user_profile:
        return [Path(user_profile) / "Documents" / "WindowsPowerShell" / "profile.ps1"]
    return []


def _managed_completion_block(source_line: str) -> str:
    return f"{COMPLETION_BLOCK_START}\n{source_line}\n{COMPLETION_BLOCK_END}"


def _upsert_completion_profile(profile: Path, block: str) -> None:
    profile.parent.mkdir(parents=True, exist_ok=True)
    existing = profile.read_text(encoding="utf-8") if profile.exists() else ""
    pattern = re.compile(
        rf"{re.escape(COMPLETION_BLOCK_START)}.*?{re.escape(COMPLETION_BLOCK_END)}\n?",
        re.DOTALL,
    )
    without_managed_blocks = pattern.sub("", existing)
    prefix = "" if not without_managed_blocks or without_managed_blocks.endswith("\n") else "\n"
    updated = without_managed_blocks + prefix + block + "\n"
    profile.write_text(updated, encoding="utf-8")


def _print_path_activation_notice(scripts: str, *, platform: str, output: TextIO) -> None:
    """Explain the persistent-PATH/current-process boundary."""

    print(f"ユーザーPATHには登録済みですが、現在のterminalには未反映です: {scripts}", file=output)
    if platform == "nt":
        print(
            "PowerShell／Windows Terminal／VS Codeをいったん終了して開き直すと `gar` を使用できます。",
            file=output,
        )
        print(r"開き直すまでは `.\scripts\gar.cmd <command>` を使用してください。", file=output)
    else:
        print("新しいterminalを開くかshell profileを再読込すると `gar` を使用できます。", file=output)


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
    line = f"# Added by Gapless Agent Runtime\n{_posix_path_line(scripts)}\n"
    with profile.open("a", encoding="utf-8") as output:
        output.write(prefix + line)


def _posix_path_line(scripts: str) -> str:
    return f'export PATH={shlex.quote(scripts)}:"$PATH"'
