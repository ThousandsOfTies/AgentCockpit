"""CLI definition and adapter for ``gar sim <subject> <action>``."""

from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from collections.abc import Mapping, Sequence

from scripts.gar_lib.api import Gar
from scripts.gar_lib.commands.common.workspace import workspace_for
from scripts.gar_lib.commands.infra import run_sim_infra_command
from scripts.gar_lib.core.command import GarCommand
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.recovery.access import report_access_failure

IO_PARAMETERS = ("device", "button", "line", "duration_ms", "value", "uid")

# This is the single whitelist used to create the parser surface and resolve API
# methods. The action name deliberately matches the programmatic API method name.
SIM_ACTIONS: dict[str, dict[str, str]] = {
    "app": {
        "build": "product の simulation build hook を実行します",
        "clean": "product の simulation build artifact を削除します",
        "deploy": "product application を simulation runtime へ配置します",
    },
    "runtime": {
        "build": "仮想デバイス stub（CUSE I2C/SPI など）や Wokwi firmware をビルドします",
        "deploy": "simulation runtime を host へ配置します",
        "start": "simulation runtime を起動します",
        "stop": "simulation runtime を停止します",
        "status": "simulation runtime の状態を確認します",
        "log": "simulation runtime のログを表示します",
        "diag": "simulation runtime を診断します",
    },
    "host": {
        "start": "simulation host を起動します",
        "stop": "simulation host を停止します",
        "status": "simulation host の状態を確認します",
    },
    "gpio": {
        "install": "GPIO dummy runtime を host へ配置します",
        "start": "GPIO dummy runtime を起動します",
        "stop": "GPIO dummy runtime を停止します",
        "plan": "hardware 定義から生成する GPIO runtime の内容を表示します",
        "status": "GPIO dummy runtime の状態を確認します",
        "check": "GPIO dummy runtime の kernel 側前提条件を確認します",
    },
    "io": {
        "state": "virtual H/W の現在値を取得します",
        "press": "button を押下します（--device 必須）",
        "set": "device の値を設定します（--device 必須）",
        "clear": "device の値を解除します（--device 必須）",
    },
}


def _shared_option(*args: object, **kwargs: object) -> argparse.ArgumentParser:
    """複数のleaf parserで共有するoptionを1回だけ定義する。"""

    option = argparse.ArgumentParser(add_help=False)
    option.add_argument(*args, **kwargs)  # type: ignore[arg-type]
    return option


def _selected_actions(subject: str, *names: str) -> dict[str, str]:
    return {name: SIM_ACTIONS[subject][name] for name in names}


def _add_actions(
    subparsers: argparse._SubParsersAction,
    subject: str,
    actions: Mapping[str, str],
    *,
    parents: Sequence[argparse.ArgumentParser] = (),
) -> dict[str, argparse.ArgumentParser]:
    """Add leaf parsers whose execution is resolved later from ``GarCommand``."""

    created: dict[str, argparse.ArgumentParser] = {}
    for action, help_text in actions.items():
        leaf = subparsers.add_parser(action, help=help_text, parents=list(parents))
        leaf.set_defaults(gar_command=GarCommand("sim", subject, action))
        created[action] = leaf
    return created


def add_sim_parser(
    subparsers: argparse._SubParsersAction,
) -> dict[str, argparse.ArgumentParser]:
    """Register the complete ``gar sim`` CLI surface and return its help parsers."""

    workspace_option = _shared_option(
        "--workspace",
        default=None,
        metavar="NAME",
        help="gar setup で登録した workspace 名。登録が1件なら省略できます",
    )
    json_option = _shared_option(
        "--json",
        dest="json_output",
        action="store_true",
        help="結果を機械可読な JSON で出力します（AI / CI 向け）",
    )
    workspace_json = (workspace_option, json_option)

    sim_parser = subparsers.add_parser(
        "sim", help="simulation の host / runtime / application / virtual H/W を操作します"
    )
    sim_parser.set_defaults(help_target="sim")
    sim_subparsers = sim_parser.add_subparsers(dest="sim_subject", metavar="subject")

    sim_app_parser = sim_subparsers.add_parser(
        "app", help="product application を simulation 向けに build / deploy します"
    )
    sim_app_parser.set_defaults(help_target="sim_app")
    _add_actions(
        sim_app_parser.add_subparsers(dest="action", metavar="action"),
        "app",
        SIM_ACTIONS["app"],
        parents=(workspace_option,),
    )

    sim_runtime_parser = sim_subparsers.add_parser(
        "runtime", help="simulation runtime（device stub / bridge）を操作します"
    )
    sim_runtime_parser.set_defaults(help_target="sim_runtime")
    sim_runtime_subparsers = sim_runtime_parser.add_subparsers(dest="action", metavar="action")
    sim_runtime_actions = _add_actions(
        sim_runtime_subparsers,
        "runtime",
        _selected_actions("runtime", "build", "deploy", "start", "stop", "status", "log"),
        parents=(workspace_option,),
    )
    _add_actions(
        sim_runtime_subparsers,
        "runtime",
        _selected_actions("runtime", "diag"),
        parents=workspace_json,
    )
    sim_runtime_actions["start"].add_argument("--settings", default=None, help="VS Code settings.json path")
    sim_runtime_actions["start"].add_argument("--profile-name", default=None, help="VS Code terminal profile 名")
    sim_runtime_actions["start"].add_argument(
        "--no-port-forward",
        action="store_true",
        help="Hardware Panel 用の 8080/8765 port forward を開始しません",
    )
    sim_runtime_actions["stop"].add_argument(
        "--keep-port-forward",
        action="store_true",
        help="Hardware Panel 用の port forward を停止しません",
    )

    sim_host_parser = sim_subparsers.add_parser(
        "host",
        help="simulation を載せる host（container / EC2 など）を操作します",
    )
    sim_host_parser.set_defaults(help_target="sim_host")
    sim_host_subparsers = sim_host_parser.add_subparsers(dest="action", metavar="action")
    sim_host_actions = _add_actions(
        sim_host_subparsers,
        "host",
        _selected_actions("host", "start", "stop"),
        parents=(workspace_option,),
    )
    _add_actions(
        sim_host_subparsers,
        "host",
        _selected_actions("host", "status"),
        parents=workspace_json,
    )
    sim_host_actions["start"].add_argument(
        "--no-update-ssh",
        action="store_true",
        help="起動後に ~/.ssh/config の HostName を更新しません",
    )
    sim_host_actions["start"].add_argument(
        "--pull",
        action="store_true",
        help="起動後に repo_dir で git pull を実行します",
    )

    sim_gpio_parser = sim_subparsers.add_parser(
        "gpio",
        help="GPIO dummy runtime を生成・配置・確認します",
    )
    sim_gpio_parser.set_defaults(help_target="sim_gpio")
    sim_gpio_subparsers = sim_gpio_parser.add_subparsers(dest="action", metavar="action")
    _add_actions(
        sim_gpio_subparsers,
        "gpio",
        _selected_actions("gpio", "install", "start", "stop"),
        parents=(workspace_option,),
    )
    _add_actions(
        sim_gpio_subparsers,
        "gpio",
        _selected_actions("gpio", "plan", "status", "check"),
        parents=workspace_json,
    )

    sim_io_parser = sim_subparsers.add_parser(
        "io",
        help="共通 Bridge control plane 経由で virtual H/W を操作します（AI / CI 向け）",
    )
    sim_io_parser.set_defaults(help_target="sim_io")
    io_option = _shared_option(
        "--device",
        default=None,
        metavar="NAME",
        help="操作対象の device 種別（button / rfid / range など）",
    )
    for name, kwargs in (
        ("--button", {"default": None}),
        ("--line", {"default": None}),
        ("--duration-ms", {"type": int, "default": 150}),
        ("--value", {"default": None}),
        ("--uid", {"default": None}),
    ):
        io_option.add_argument(name, **kwargs)  # type: ignore[arg-type]
    _add_actions(
        sim_io_parser.add_subparsers(dest="action", metavar="action"),
        "io",
        SIM_ACTIONS["io"],
        parents=(*workspace_json, io_option),
    )

    sim_infra_parser = sim_subparsers.add_parser("infra", help="simulation host インフラを Terraform で管理します")
    sim_infra_parser.set_defaults(help_target="sim_infra")
    sim_infra_subparsers = sim_infra_parser.add_subparsers(dest="infra_action", metavar="action")
    for infra_action in ("setup", "apply", "destroy"):
        infra_action_parser = sim_infra_subparsers.add_parser(infra_action, help=f"terraform {infra_action}")
        infra_action_parser.add_argument("--key-name", default=None, help="EC2 SSH key pair name")
        infra_action_parser.add_argument("--region", default=None, help="AWS region")
        infra_action_parser.add_argument(
            "--auto-approve",
            action="store_true",
            help="--auto-approve を terraform に渡します",
        )

    return {
        "sim": sim_parser,
        "sim_app": sim_app_parser,
        "sim_runtime": sim_runtime_parser,
        "sim_host": sim_host_parser,
        "sim_gpio": sim_gpio_parser,
        "sim_io": sim_io_parser,
        "sim_infra": sim_infra_parser,
    }


def run_sim_command(
    args: Namespace,
    *,
    subcommand_parsers: Mapping[str, argparse.ArgumentParser] | None = None,
) -> int:
    """Resolve and run every command below ``gar sim``."""

    if getattr(args, "sim_subject", None) == "infra":
        if args.infra_action is None:
            _print_help(subcommand_parsers, "sim_infra")
            return 1
        return run_sim_infra_command(
            args.infra_action,
            key_name=getattr(args, "key_name", None),
            region=getattr(args, "region", None),
            auto_approve=getattr(args, "auto_approve", False),
        )

    command = getattr(args, "gar_command", None)
    if command is None:
        _print_help(
            subcommand_parsers,
            getattr(args, "help_target", "sim"),
        )
        return 1
    if not isinstance(command, GarCommand) or command.group != "sim":
        group = getattr(command, "group", type(command).__name__)
        raise GarDomainError(f"simulation command ではありません: {group}")

    workspace_selector = getattr(args, "workspace", None)
    try:
        workspace = workspace_for(workspace_selector)
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1

    try:
        subject_name = command.subject
        if subject_name is None or command.action not in SIM_ACTIONS.get(subject_name, {}):
            raise GarDomainError(f"未対応の simulation command: {subject_name or '(none)'} {command.action}")
        subject = getattr(Gar(workspace).sim, subject_name, None)
        action = getattr(subject, command.action, None)
        if not callable(action):
            raise GarDomainError(f"未対応の simulation command: {subject_name} {command.action}")
        return action(**_action_kwargs(command, args))
    except AccessConnectionError as error:
        device = getattr(args, "device", None)
        return report_access_failure(
            error,
            workspace=workspace,
            retry_command=command.to_cli(
                workspace=workspace_selector,
                options=("--device", str(device)) if device else (),
            ),
            purpose="simulation",
        )
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1


def _print_help(
    subcommand_parsers: Mapping[str, argparse.ArgumentParser] | None,
    target: str,
) -> None:
    if subcommand_parsers is not None:
        subcommand_parsers[target].print_help()


def _action_kwargs(command: GarCommand, args: Namespace) -> dict[str, object]:
    if command.subject == "runtime" and command.action == "start":
        return {
            "settings": getattr(args, "settings", None),
            "profile_name": getattr(args, "profile_name", None),
            "no_port_forward": getattr(args, "no_port_forward", False),
        }
    if command.subject == "runtime" and command.action == "stop":
        return {"keep_port_forward": getattr(args, "keep_port_forward", False)}
    if command.subject == "host" and command.action == "start":
        return {
            "no_update_ssh": getattr(args, "no_update_ssh", False),
            "pull": getattr(args, "pull", False),
        }
    if (
        (command.subject == "runtime" and command.action == "diag")
        or (command.subject == "host" and command.action == "status")
        or command.subject == "gpio"
    ):
        return {"json_output": getattr(args, "json_output", False)}
    if command.subject == "io":
        params = {name: value for name in IO_PARAMETERS if (value := getattr(args, name, None)) is not None}
        return {"json_output": getattr(args, "json_output", False), **params}
    return {}
