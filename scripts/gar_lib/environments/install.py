"""Shared setup-time dependency installation helpers."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from scripts.gar_lib.vscode.terminal_requests import TerminalRequestStore


def sudo_block_reason() -> str | None:
    result = subprocess.run(
        ["sudo", "-n", "true"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return None

    stderr = result.stderr.strip()
    lowered = stderr.lower()
    if (
        "no new privileges" in lowered
        or "password is required" in lowered
        or ("terminal" in lowered and "required" in lowered)
    ):
        return stderr
    return None


def print_user_terminal_handoff(
    title: str,
    commands: list[str],
    *,
    reason: str | None = None,
) -> None:
    print()
    print(title)
    if reason:
        print("この実行環境では sudo を直接実行できません:")
        print(textwrap.indent(reason, "  "))
    print("ユーザーの通常ターミナルで次のコマンドを実行してください。")
    print("完了後、もう一度 `gar setup` を実行すると続きから確認できます。")
    print()
    print("```bash")
    for command in commands:
        print(command)
    print("```")

    request_path = create_visible_terminal_request(title, commands)
    print()
    print("VSCode integrated terminal にも実行要求を作成しました:")
    print(f"  {request_path}")
    print("sudo password や認証入力を求められたら、その terminal に直接入力してください。")


def create_visible_terminal_request(title: str, commands: list[str]) -> Path:
    cwd = Path.cwd()
    store = TerminalRequestStore.under(cwd / ".gar")
    _, request_path = store.create_request(
        command=" && ".join(commands),
        title="Gapless Agent Runtime User Action",
        cwd=cwd,
        reason=title,
    )
    return request_path
