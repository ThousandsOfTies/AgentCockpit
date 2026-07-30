"""CLI definition and adapter for ``gar target <action>``."""

from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from collections.abc import Mapping

from scripts.gar_lib.api import Gar
from scripts.gar_lib.commands.recovery import report_access_failure
from scripts.gar_lib.commands.terminal import run_terminal_run_command
from scripts.gar_lib.commands.workspace import workspace_for
from scripts.gar_lib.core.command import GarCommand
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError

TARGET_ACTIONS = {
    "build": "setup 済み target の実機用 artifact をビルドします",
    "deploy": "target runtime へ成果物を配置します",
    "fetch": "build environment から artifact bundle を WSL hub へ取得します",
}


def add_target_parser(
    subparsers: argparse._SubParsersAction,
) -> dict[str, argparse.ArgumentParser]:
    """Register the complete ``gar target`` CLI surface and return its help parser."""

    workspace_option = argparse.ArgumentParser(add_help=False)
    workspace_option.add_argument(
        "--workspace",
        default=None,
        metavar="NAME",
        help="gar setup で登録した workspace 名。登録が1件なら省略できます",
    )
    target_parser = subparsers.add_parser(
        "target",
        help="接続先が提供する I/O を使う実機 target を操作します",
    )
    target_parser.set_defaults(help_target="target")
    action_parsers = target_parser.add_subparsers(dest="action", metavar="action")
    for action, help_text in TARGET_ACTIONS.items():
        action_parser = action_parsers.add_parser(
            action,
            help=help_text,
            parents=[workspace_option],
        )
        action_parser.set_defaults(gar_command=GarCommand("target", None, action))
    return {"target": target_parser}


def run_target_command(
    args: Namespace,
    *,
    subcommand_parsers: Mapping[str, argparse.ArgumentParser] | None = None,
) -> int:
    """Resolve and run every command below ``gar target``."""

    command = getattr(args, "gar_command", None)
    if command is None:
        if subcommand_parsers is not None:
            subcommand_parsers["target"].print_help()
        return 1
    if not isinstance(command, GarCommand) or command.group != "target":
        group = getattr(command, "group", type(command).__name__)
        raise GarDomainError(f"target command ではありません: {group}")

    workspace_selector = getattr(args, "workspace", None)
    try:
        workspace = workspace_for(workspace_selector)
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1
    try:
        if command.subject is not None:
            raise GarDomainError(f"target commandにsubjectはありません: {command.subject}")
        if command.action not in TARGET_ACTIONS:
            raise GarDomainError(f"未対応の target action: {command.action}")
        target = Gar(workspace).target
        action = getattr(target, command.action, None)
        if not callable(action):
            raise GarDomainError(f"未対応の target action: {command.action}")
        return action()
    except AccessConnectionError as error:
        device = getattr(args, "device", None)
        return report_access_failure(
            error,
            workspace=workspace,
            retry_command=command.to_cli(
                workspace=workspace_selector,
                options=("--device", str(device)) if device else (),
            ),
            purpose="target",
            run_terminal=run_terminal_run_command,
        )
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1
