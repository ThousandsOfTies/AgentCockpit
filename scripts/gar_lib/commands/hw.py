"""CLI boundary for ``gar hw``."""

from __future__ import annotations

import argparse
from argparse import Namespace

from scripts.gar_lib.core.config import load_config
from scripts.gar_lib.core.hardware import write_hw_template


def add_hw_parser(
    subparsers: argparse._SubParsersAction,
) -> dict[str, argparse.ArgumentParser]:
    parser = subparsers.add_parser("hw", help="hardware 定義 CSV を管理します")
    commands = parser.add_subparsers(dest="hw_command", metavar="command")
    init_parser = commands.add_parser(
        "init",
        help="hardware 定義 CSV を gar-tools のテンプレートから作成します",
    )
    init_parser.add_argument(
        "--target",
        dest="target_id",
        default=None,
        help="使用するtarget template（既定: 現在workspaceのselected_target、未選択時はlinux-device）",
    )
    init_parser.add_argument(
        "--dir",
        dest="output_dir",
        default=None,
        help="CSV を作成するディレクトリ（既定: ./hardware、テンプレート: gar-tools）",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="既存のテンプレート CSV を上書きします",
    )
    return {"hw": parser}


def run_hw_cli(args: Namespace, *, help_parser: argparse.ArgumentParser) -> int:
    if args.hw_command is None:
        help_parser.print_help()
        return 1
    return run_hw_command(
        args.hw_command,
        output_dir=args.output_dir,
        force=args.force,
        target_id=args.target_id,
    )


def run_hw_command(
    command: str,
    *,
    output_dir: str | None = None,
    force: bool = False,
    target_id: str | None = None,
) -> int:
    if command == "init":
        selected_target = target_id or load_config().get("selected_target") or "linux-device"
        return write_hw_template(
            output_dir=output_dir,
            force=force,
            target_id=selected_target,
        )

    print(f"gar hw: unknown command: {command}")
    return 1
