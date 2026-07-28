"""`gar` CLI entry point. 引数解析と、対応する関数の呼び出しだけを行う。

`gar <group> <subject> <action>` は command ごとのモジュールへ渡す。実体は以下にある:

- :mod:`scripts.gar_lib.commands.sim` — ``gar sim app/runtime/host/gpio/io``
- :mod:`scripts.gar_lib.commands.target` — ``gar target app``

コマンド1本を実行する関数は、どの層にあっても ``run_`` で始める。
実装手段（execute / dispatch / handle など）を名前に持ち込まない。

workspace 非依存の plumbing コマンド（``setup`` / ``code`` / ``terminal`` / ``usb`` /
``hw`` / ``sim infra`` / ``completion``）は :func:`main` から直接呼ぶ。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from scripts.gar_lib.commands import sim, target
from scripts.gar_lib.commands.code import run_code_command
from scripts.gar_lib.commands.hw import run_hw_command
from scripts.gar_lib.commands.infra import run_sim_infra_command
from scripts.gar_lib.commands.setup import run_setup
from scripts.gar_lib.commands.terminal import run_terminal_gc_command, run_terminal_run_command
from scripts.gar_lib.commands.usb import run_usb_command
from scripts.gar_lib.core.command import GarCommand

CODE_COMMAND_MAP = {
    "boot": "boot",
    "start": "start",
    "stop": "stop",
    "shutdown": "shutdown",
    "status": "status",
}


def normalize_question_help(argv: Sequence[str] | None = None) -> list[str]:
    """Treat `?` before `--` as a context-local argparse help request."""

    args = list(sys.argv[1:] if argv is None else argv)
    scan_end = args.index("--") if "--" in args else len(args)
    for index, value in enumerate(args[:scan_end]):
        if value == "?":
            return [*args[:index], "--help", *args[index + 1 :]]
    return args


def completion_bash_script() -> str:
    return """# Gapless Agent Runtime bash completion.
if command -v register-python-argcomplete >/dev/null 2>&1 && python -c 'import argcomplete' >/dev/null 2>&1; then
  eval "$(register-python-argcomplete gar)"
else
  _agp_completion() {
    local IFS=$'\\n'
    COMPREPLY=($(COMP_LINE="$COMP_LINE" COMP_POINT="$COMP_POINT" "$1" completion words --cword "$COMP_CWORD" -- "${COMP_WORDS[@]}"))
  }
  complete -o nosort -F _agp_completion gar
fi
"""


def enable_argcomplete(parser: argparse.ArgumentParser) -> None:
    try:
        import argcomplete
    except ImportError:
        return
    argcomplete.autocomplete(parser)


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _parser_options(parser: argparse.ArgumentParser) -> list[str]:
    options: list[str] = []
    for action in parser._actions:
        options.extend(action.option_strings)
    return options


def parser_completion_words(cword: int, words: Sequence[str]) -> list[str]:
    """Return shell completion candidates from argparse parser structure."""

    parser = build_parser()
    current = words[cword] if cword < len(words) else ""
    tokens = list(words[1:cword])

    index = 0
    while index < len(tokens):
        token = tokens[index]
        subparsers = _subparser_action(parser)
        if subparsers and token in subparsers.choices:
            parser = subparsers.choices[token]
            index += 1
            continue
        if token.startswith("-"):
            option_action = parser._option_string_actions.get(token)
            if option_action and option_action.nargs in (None, 1) and index + 1 < len(tokens):
                index += 2
                continue
        index += 1

    candidates = _parser_options(parser)
    subparsers = _subparser_action(parser)
    if subparsers:
        candidates.extend(subparsers.choices)

    return sorted(candidate for candidate in candidates if candidate.startswith(current))


def add_code_start_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target",
        "--codespace",
        dest="codespace",
        default=None,
        metavar="TARGET",
        help="接続する development target 名",
    )
    parser.add_argument("--remote-path", default=None, help="Codespace 側 workspace path")
    parser.add_argument("--mount-dir", default=None, help="WSL 側 sshfs mount path")
    parser.add_argument("--settings", default=None, help="VS Code settings.json path")
    parser.add_argument("--profile-name", default=None, help="VS Code terminal profile 名")
    parser.add_argument(
        "--no-mount",
        action="store_true",
        help="sshfs mount を更新せず、SSH 設定と terminal profile だけ更新します",
    )


def _shared_option(*args: object, **kwargs: object) -> argparse.ArgumentParser:
    """複数のleaf parserで共有するoptionを1回だけ定義する。"""

    option = argparse.ArgumentParser(add_help=False)
    option.add_argument(*args, **kwargs)  # type: ignore[arg-type]
    return option


def add_actions(
    subparsers: argparse._SubParsersAction,
    group: str,
    subject: str,
    actions: dict[str, tuple[str, object]],
    *,
    parents: Sequence[argparse.ArgumentParser] = (),
) -> dict[str, argparse.ArgumentParser]:
    """`gar <group> <subject> <action>` の action parser を作る。

    実行先の選択は parser ではなく group / subject command runner が担う。
    """

    created: dict[str, argparse.ArgumentParser] = {}
    for action, (help_text, _) in actions.items():
        leaf = subparsers.add_parser(action, help=help_text, parents=list(parents))
        leaf.set_defaults(gar_command=GarCommand(group, subject, action))
        created[action] = leaf
    return created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gar")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

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

    setup_parser = subparsers.add_parser(
        "setup",
        help="接続環境を選択して依存コマンドを確認します",
    )
    setup_parser.add_argument(
        "--no-install",
        action="store_true",
        help="不足コマンドのインストール処理を実行せず案内だけ表示します",
    )
    setup_parser.add_argument(
        "--ec2-host",
        default=None,
        help="gar sim が既定で使う SSH config 上の runtime host 名",
    )
    setup_parser.add_argument(
        "--esp32-port",
        default=None,
        help="ESP32 esptool environment が使う serial port を保存します（例: COM3, /dev/ttyUSB0）",
    )
    code_parser = subparsers.add_parser(
        "code",
        help="Build Artifacts workspace との接続を管理します",
    )
    code_subparsers = code_parser.add_subparsers(dest="code_command", metavar="command")
    code_boot_parser = code_subparsers.add_parser(
        "boot",
        help="development target を起動します",
    )
    code_boot_parser.add_argument(
        "--target",
        "--codespace",
        dest="codespace",
        default=None,
        metavar="TARGET",
        help="起動する development target 名",
    )
    code_start_parser = code_subparsers.add_parser(
        "start",
        help="Codespace build workspace を WSL hub から見えるようにします",
    )
    add_code_start_arguments(code_start_parser)
    code_stop_parser = code_subparsers.add_parser(
        "stop",
        help="Codespace build workspace の WSL hub 側接続を停止します",
    )
    code_stop_parser.add_argument(
        "--target",
        "--codespace",
        dest="codespace",
        default=None,
        metavar="TARGET",
        help="停止する development target 名",
    )
    code_stop_parser.add_argument("--mount-dir", default=None, help="WSL 側 sshfs mount path")
    code_stop_parser.add_argument("--settings", default=None, help="VS Code settings.json path")
    code_stop_parser.add_argument("--profile-name", default=None, help="VS Code terminal profile 名")
    code_stop_parser.add_argument(
        "--shutdown",
        action="store_true",
        help="WSL 側接続の後片付け後に GitHub Codespace VM も停止します",
    )
    code_shutdown_parser = code_subparsers.add_parser(
        "shutdown",
        help="development target を停止します",
    )
    code_shutdown_parser.add_argument(
        "--target",
        "--codespace",
        dest="codespace",
        default=None,
        metavar="TARGET",
        help="停止する development target 名",
    )
    code_status_parser = code_subparsers.add_parser(
        "status",
        help="Codespace VM / 接続状態を確認します",
    )
    code_status_parser.add_argument(
        "--target",
        "--codespace",
        dest="codespace",
        default=None,
        metavar="TARGET",
        help="確認する development target 名",
    )
    code_status_parser.add_argument("--mount-dir", default=None, help="WSL 側 sshfs mount path")

    terminal_parser = subparsers.add_parser(
        "terminal",
        help="VSCode integrated terminal への実行要求を作成します",
    )
    terminal_subparsers = terminal_parser.add_subparsers(dest="terminal_command", metavar="command")
    terminal_run_parser = terminal_subparsers.add_parser(
        "run",
        help="VSCode integrated terminal でコマンドを実行します",
    )
    terminal_run_parser.add_argument("--title", default="Gapless Agent Runtime", help="VSCode terminal の表示名")
    terminal_run_parser.add_argument("--cwd", default=None, help="コマンドを実行する作業ディレクトリ")
    terminal_run_parser.add_argument(
        "--command",
        dest="command_text",
        default=None,
        help="実行するコマンド文字列",
    )
    terminal_run_parser.add_argument(
        "command_parts",
        nargs=argparse.REMAINDER,
        help="実行するコマンド。例: gar terminal run -- gar setup",
    )
    terminal_gc_parser = terminal_subparsers.add_parser(
        "gc",
        help="terminal-requests/processed と terminal-status の古いエントリを削除します",
    )
    terminal_gc_parser.add_argument("--keep-days", type=int, default=7, help="保持する日数 (既定: 7)")
    terminal_gc_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除対象を表示するだけで実際には削除しません",
    )

    completion_parser = subparsers.add_parser(
        "completion",
        help="shell completion script を出力します",
    )
    completion_subparsers = completion_parser.add_subparsers(dest="completion_shell", metavar="shell")
    completion_subparsers.add_parser("bash", help="bash completion script を出力します")
    completion_words_parser = completion_subparsers.add_parser(
        "words",
        help=argparse.SUPPRESS,
    )
    completion_words_parser.add_argument("--cword", type=int, required=True)
    completion_words_parser.add_argument("words", nargs=argparse.REMAINDER)

    sim_parser = subparsers.add_parser(
        "sim", help="simulation の host / runtime / application / virtual H/W を操作します"
    )
    sim_parser.set_defaults(help_target="sim")
    sim_subparsers = sim_parser.add_subparsers(dest="sim_subject", metavar="subject")

    sim_app_parser = sim_subparsers.add_parser(
        "app", help="product application を simulation 向けに build / deploy します"
    )
    sim_app_parser.set_defaults(help_target="sim_app")
    add_actions(
        sim_app_parser.add_subparsers(dest="action", metavar="action"),
        "sim",
        "app",
        {
            "build": ("product の simulation build hook を実行します", sim.run_sim_app_build),
            "clean": ("product の simulation build artifact を削除します", sim.run_sim_app_clean),
            "deploy": ("product application を simulation runtime へ配置します", sim.run_sim_app_deploy),
        },
        parents=(workspace_option,),
    )

    sim_runtime_parser = sim_subparsers.add_parser(
        "runtime", help="simulation runtime（device stub / bridge）を操作します"
    )
    sim_runtime_parser.set_defaults(help_target="sim_runtime")
    sim_runtime_subparsers = sim_runtime_parser.add_subparsers(dest="action", metavar="action")
    sim_runtime_actions = add_actions(
        sim_runtime_subparsers,
        "sim",
        "runtime",
        {
            "build": (
                "仮想デバイス stub（CUSE I2C/SPI など）や Wokwi firmware をビルドします",
                sim.run_sim_runtime_build,
            ),
            "deploy": ("simulation runtime を host へ配置します", sim.run_sim_runtime_deploy),
            "start": ("simulation runtime を起動します", sim.run_sim_runtime_start),
            "stop": ("simulation runtime を停止します", sim.run_sim_runtime_stop),
            "status": ("simulation runtime の状態を確認します", sim.run_sim_runtime_status),
            "log": ("simulation runtime のログを表示します", sim.run_sim_runtime_log),
        },
        parents=(workspace_option,),
    )
    add_actions(
        sim_runtime_subparsers,
        "sim",
        "runtime",
        {"diag": ("simulation runtime を診断します", sim.run_sim_runtime_diag)},
        parents=workspace_json,
    )
    sim_runtime_actions["start"].add_argument(
        "--settings", default=None, help="VS Code settings.json path"
    )
    sim_runtime_actions["start"].add_argument(
        "--profile-name", default=None, help="VS Code terminal profile 名"
    )
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
    sim_host_actions = add_actions(
        sim_host_subparsers,
        "sim",
        "host",
        {
            "start": ("simulation host を起動します", sim.run_sim_host_start),
            "stop": ("simulation host を停止します", sim.run_sim_host_stop),
        },
        parents=(workspace_option,),
    )
    add_actions(
        sim_host_subparsers,
        "sim",
        "host",
        {"status": ("simulation host の状態を確認します", sim.run_sim_host_status)},
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
    add_actions(
        sim_gpio_subparsers,
        "sim",
        "gpio",
        {
            "install": ("GPIO dummy runtime を host へ配置します", sim.run_sim_gpio),
            "start": ("GPIO dummy runtime を起動します", sim.run_sim_gpio),
            "stop": ("GPIO dummy runtime を停止します", sim.run_sim_gpio),
        },
        parents=(workspace_option,),
    )
    add_actions(
        sim_gpio_subparsers,
        "sim",
        "gpio",
        {
            "plan": ("hardware 定義から生成する GPIO runtime の内容を表示します", sim.run_sim_gpio),
            "status": ("GPIO dummy runtime の状態を確認します", sim.run_sim_gpio),
            "check": ("GPIO dummy runtime の kernel 側前提条件を確認します", sim.run_sim_gpio),
        },
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
    add_actions(
        sim_io_parser.add_subparsers(dest="action", metavar="action"),
        "sim",
        "io",
        {
            "state": ("virtual H/W の現在値を取得します", sim.run_sim_io),
            "press": ("button を押下します（--device 必須）", sim.run_sim_io),
            "set": ("device の値を設定します（--device 必須）", sim.run_sim_io),
            "clear": ("device の値を解除します（--device 必須）", sim.run_sim_io),
        },
        parents=(*workspace_json, io_option),
    )

    sim_infra_parser = sim_subparsers.add_parser(
        "infra", help="simulation host インフラを Terraform で管理します"
    )
    sim_infra_parser.set_defaults(help_target="sim_infra")
    sim_infra_subparsers = sim_infra_parser.add_subparsers(dest="infra_action", metavar="action")
    for _infra_action in ("setup", "apply", "destroy"):
        _p = sim_infra_subparsers.add_parser(_infra_action, help=f"terraform {_infra_action}")
        _p.add_argument("--key-name", default=None, help="EC2 SSH key pair name")
        _p.add_argument("--region", default=None, help="AWS region")
        _p.add_argument("--auto-approve", action="store_true", help="--auto-approve を terraform に渡します")

    target_parser = subparsers.add_parser(
        "target",
        help="接続先が提供する I/O を使う実機 target を操作します",
    )
    target_parser.set_defaults(help_target="target")
    target_subparsers = target_parser.add_subparsers(dest="target_subject", metavar="subject")
    target_app_parser = target_subparsers.add_parser(
        "app", help="product application を実機 target 向けに build / deploy します"
    )
    target_app_parser.set_defaults(help_target="target_app")
    add_actions(
        target_app_parser.add_subparsers(dest="action", metavar="action"),
        "target",
        "app",
        {
            "build": ("setup 済み target の実機用 artifact をビルドします", target.run_target_app_build),
            "deploy": ("target runtime へ成果物を配置します", target.run_target_app_deploy),
            "fetch": (
                "build environment から artifact bundle を WSL hub へ取得します",
                target.run_target_app_fetch,
            ),
        },
        parents=(workspace_option,),
    )

    usb_parser = subparsers.add_parser(
        "usb",
        help="USB-C 実機を usbipd-win 経由で WSL2 に attach します",
    )
    usb_subparsers = usb_parser.add_subparsers(dest="usb_command", metavar="command")
    for usb_command_name in ("attach", "detach", "status", "list", "bind"):
        usb_command_parser = usb_subparsers.add_parser(
            usb_command_name,
            help=f"USB: {usb_command_name}",
        )
        if usb_command_name != "list":
            usb_command_parser.add_argument(
                "--busid",
                default=None,
                help="usbipd の busid。省略時は保存済み busid → Android 自動検出",
            )
            usb_command_parser.add_argument(
                "--match",
                default=None,
                help="USB device description / VID:PID / BUSID の部分一致で対象を選びます（例: CH9102）",
            )
        if usb_command_name in ("status", "list"):
            usb_command_parser.add_argument(
                "--json",
                dest="json_output",
                action="store_true",
                help="結果を機械可読な JSON で出力します（AI / CI 向け）",
            )
        if usb_command_name in ("attach", "bind"):
            usb_command_parser.add_argument(
                "--no-remember",
                action="store_true",
                help="対象 busid を .gar/config.json に記憶しません",
            )

    hw_parser = subparsers.add_parser(
        "hw",
        help="hardware 定義 CSV を管理します",
    )
    hw_subparsers = hw_parser.add_subparsers(dest="hw_command", metavar="command")
    hw_init_parser = hw_subparsers.add_parser(
        "init",
        help="hardware 定義 CSV を gar-tools のテンプレートから作成します",
    )
    hw_init_parser.add_argument(
        "--dir",
        dest="output_dir",
        default=None,
        help="CSV を作成するディレクトリ（既定: ./hardware、テンプレート: gar-tools）",
    )
    hw_init_parser.add_argument(
        "--force",
        action="store_true",
        help="既存のテンプレート CSV を上書きします",
    )
    parser._agp_subcommand_parsers = {  # type: ignore[attr-defined]
        "code": code_parser,
        "terminal": terminal_parser,
        "completion": completion_parser,
        "sim": sim_parser,
        "sim_app": sim_app_parser,
        "sim_runtime": sim_runtime_parser,
        "sim_host": sim_host_parser,
        "sim_gpio": sim_gpio_parser,
        "sim_io": sim_io_parser,
        "sim_infra": sim_infra_parser,
        "target": target_parser,
        "target_app": target_app_parser,
        "usb": usb_parser,
        "hw": hw_parser,
    }
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    subcommand_parsers = parser._agp_subcommand_parsers  # type: ignore[attr-defined]
    enable_argcomplete(parser)
    try:
        args = parser.parse_args(normalize_question_help(argv))
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        raise

    if args.command == "setup":
        return run_setup(no_install=args.no_install, ec2_host=args.ec2_host, esp32_port=args.esp32_port)
    if args.command == "code":
        if args.code_command is None:
            subcommand_parsers["code"].print_help()
            return 1
        return run_code_command(
            CODE_COMMAND_MAP[args.code_command],
            codespace=getattr(args, "codespace", None),
            remote_path=getattr(args, "remote_path", None),
            mount_dir=getattr(args, "mount_dir", None),
            settings=getattr(args, "settings", None),
            profile_name=getattr(args, "profile_name", None),
            no_mount=getattr(args, "no_mount", False),
            shutdown=getattr(args, "shutdown", False),
        )
    if args.command == "terminal" and args.terminal_command == "run":
        return run_terminal_run_command(
            command_parts=args.command_parts,
            command_text=args.command_text,
            title=args.title,
            cwd=args.cwd,
        )
    if args.command == "terminal" and args.terminal_command == "gc":
        return run_terminal_gc_command(keep_days=args.keep_days, dry_run=args.dry_run)
    if args.command == "terminal":
        subcommand_parsers["terminal"].print_help()
        return 1
    if args.command == "sim" and getattr(args, "gar_command", None) is not None:
        return sim.run_sim_command(args)
    if args.command == "target" and getattr(args, "gar_command", None) is not None:
        return target.run_target_command(args)

    if args.command == "sim" and getattr(args, "sim_subject", None) == "infra":
        if args.infra_action is None:
            subcommand_parsers["sim_infra"].print_help()
            return 1
        return run_sim_infra_command(
            args.infra_action,
            key_name=getattr(args, "key_name", None),
            region=getattr(args, "region", None),
            auto_approve=getattr(args, "auto_approve", False),
        )

    if args.command in {"sim", "target"}:
        subcommand_parsers[getattr(args, "help_target", args.command)].print_help()
        return 1

    if args.command == "usb":
        if args.usb_command is None:
            subcommand_parsers["usb"].print_help()
            return 1
        return run_usb_command(
            args.usb_command,
            busid=getattr(args, "busid", None),
            match=getattr(args, "match", None),
            remember=not getattr(args, "no_remember", False),
            json_output=getattr(args, "json_output", False),
        )

    if args.command == "hw":
        if args.hw_command is None:
            subcommand_parsers["hw"].print_help()
            return 1
        return run_hw_command(
            args.hw_command,
            output_dir=args.output_dir,
            force=args.force,
        )

    if args.command == "completion":
        if args.completion_shell == "bash":
            print(completion_bash_script(), end="")
            return 0
        if args.completion_shell == "words":
            words = args.words[1:] if args.words[:1] == ["--"] else args.words
            print("\n".join(parser_completion_words(args.cword, words)))
            return 0
        subcommand_parsers["completion"].print_help()
        return 1

    parser.print_help()
    return 0
