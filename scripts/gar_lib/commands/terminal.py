"""`gar terminal` subcommand: VSCode integrated terminal request bridge."""

from __future__ import annotations

import argparse
import shlex
import sys
from argparse import Namespace
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from scripts.gar_lib.core.config import CONFIG_PATH
from scripts.gar_lib.vscode.terminal_requests import TerminalRequestStore


def add_terminal_parser(
    subparsers: argparse._SubParsersAction,
) -> dict[str, argparse.ArgumentParser]:
    """Register ``gar terminal`` and return the parser used for group help."""

    parser = subparsers.add_parser(
        "terminal",
        help="VSCode integrated terminal への実行要求を作成します",
    )
    commands = parser.add_subparsers(dest="terminal_command", metavar="command")

    run_parser = commands.add_parser(
        "run",
        help="VSCode integrated terminal でコマンドを実行します",
    )
    run_parser.add_argument("--title", default="Gapless Agent Runtime", help="VSCode terminal の表示名")
    run_parser.add_argument("--cwd", default=None, help="コマンドを実行する作業ディレクトリ")
    run_parser.add_argument(
        "--command",
        dest="command_text",
        default=None,
        help="実行するコマンド文字列",
    )
    run_parser.add_argument(
        "command_parts",
        nargs=argparse.REMAINDER,
        help="実行するコマンド。例: gar terminal run -- gar config",
    )

    gc_parser = commands.add_parser(
        "gc",
        help="terminal-requests/processed と terminal-status の古いエントリを削除します",
    )
    gc_parser.add_argument("--keep-days", type=int, default=7, help="保持する日数 (既定: 7)")
    gc_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除対象を表示するだけで実際には削除しません",
    )
    return {"terminal": parser}


def run_terminal_cli(args: Namespace, *, help_parser: argparse.ArgumentParser) -> int:
    """Translate parsed terminal arguments into the explicit command functions."""

    if args.terminal_command == "run":
        return run_terminal_run_command(
            command_parts=args.command_parts,
            command_text=args.command_text,
            title=args.title,
            cwd=args.cwd,
        )
    if args.terminal_command == "gc":
        return run_terminal_gc_command(
            keep_days=args.keep_days,
            dry_run=args.dry_run,
        )

    help_parser.print_help()
    return 1


def run_terminal_run_command(
    *,
    command_parts: Sequence[str],
    command_text: str | None = None,
    title: str,
    cwd: str | None,
) -> int:
    if command_text is not None:
        command = command_text.strip()
    else:
        parts = list(command_parts)
        if parts[:1] == ["--"]:
            parts = parts[1:]
        command = shlex.join(parts)
    if not command:
        print("実行するコマンドを指定してください。", file=sys.stderr)
        return 1

    store = TerminalRequestStore.under(CONFIG_PATH.parent)
    try:
        _, request_path = store.create_request(
            command=command,
            title=title,
            cwd=Path(cwd) if cwd else Path.cwd(),
        )
    except (OSError, ValueError) as exc:
        print(f"VSCode terminal request を作成できませんでした: {exc}", file=sys.stderr)
        return 1

    print(f"VSCode terminal request を作成しました: {request_path}")
    return 0


def run_terminal_gc_command(*, keep_days: int, dry_run: bool) -> int:
    if keep_days < 0:
        print("--keep-days は 0 以上を指定してください。", file=sys.stderr)
        return 1

    base = CONFIG_PATH.parent
    targets = [
        base / "terminal-requests" / "processed",
        base / "terminal-status",
    ]
    cutoff = datetime.now(UTC).timestamp() - keep_days * 86400
    matched = 0
    removed = 0
    scanned = 0
    for directory in targets:
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            scanned += 1
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                continue
            matched += 1
            if dry_run:
                print(f"[dry-run] would remove: {path}")
            else:
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    print(f"failed to remove {path}: {exc}", file=sys.stderr)

    if dry_run:
        print(f"scan: {scanned} ファイル / 対象: {matched}")
    else:
        print(f"scan: {scanned} ファイル / 削除: {removed}")
    return 0
