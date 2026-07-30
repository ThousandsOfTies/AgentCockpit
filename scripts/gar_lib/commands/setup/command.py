"""Orchestrate the ordered phases of ``gar setup``."""

from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from collections.abc import Sequence

from scripts.gar_lib.commands.setup.environment_setup import (
    EnvironmentSelectionStatus,
    SetupMenuChoice,
    configure_default_ec2_host,
    ensure_environment_dependencies,
    print_environment_overview,
    select_environment_for_category,
    select_setup_category,
    unconfigured_categories,
)
from scripts.gar_lib.commands.setup.target_setup import (
    configure_esp32_serial_port,
    configure_target,
    configure_target_connection,
    optional_setup_categories,
    prepare_target_backend,
    print_target_next_steps,
    save_selected_target,
    select_target,
    selected_target_manifest,
)
from scripts.gar_lib.commands.setup.workspace_setup import configure_workspace_root
from scripts.gar_lib.core.config import (
    default_ec2_host,
    is_valid_runtime_host,
    load_config,
    save_config,
)
from scripts.gar_lib.core.tools_repository import ensure_gar_tools_available
from scripts.gar_lib.environments.discovery import discover_environments
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption
from scripts.gar_lib.target.manifest import (
    TargetManifest,
    TargetManifestValidationError,
    discover_target_manifests,
)
from scripts.gar_lib.vscode.terminal_bridge import (
    install_vscode_terminal_bridge,
    installed_vscode_terminal_bridge_path,
)
from scripts.gar_lib.vscode.terminal_ui import (
    BLUE,
    BOLD,
    CYAN,
    DIM,
    GREEN,
    RED,
    YELLOW,
    safe_input,
    style,
)


def add_setup_parser(
    subparsers: argparse._SubParsersAction,
) -> dict[str, argparse.ArgumentParser]:
    parser = subparsers.add_parser(
        "setup",
        help="接続環境を選択して依存コマンドを確認します",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="不足コマンドのインストール処理を実行せず案内だけ表示します",
    )
    parser.add_argument(
        "--ec2-host",
        default=None,
        help="gar sim が既定で使う SSH config 上の runtime host 名",
    )
    parser.add_argument(
        "--esp32-port",
        default=None,
        help="ESP32 esptool environment が使う serial port を保存します（例: COM3, /dev/ttyUSB0）",
    )
    return {"setup": parser}


def run_setup_cli(args: Namespace) -> int:
    return run_setup(
        no_install=args.no_install,
        ec2_host=args.ec2_host,
        esp32_port=args.esp32_port,
    )


def run_setup(
    no_install: bool = False,
    ec2_host: str | None = None,
    esp32_port: str | None = None,
) -> int:
    if ec2_host is not None and not is_valid_runtime_host(ec2_host):
        print(
            "gar setup: --ec2-hostには空白や制御文字を含まないSSH host名を指定してください。",
            file=sys.stderr,
        )
        return 1

    environments = discover_environments()
    if not environments:
        print("接続環境が見つかりません。", file=sys.stderr)
        return 1

    _print_setup_intro()
    if not no_install:
        ensure_gar_tools_for_setup()
        print()

    targets = _discover_targets(environments)
    if targets is None:
        return 1
    config = _load_setup_config()
    config = _configure_workspace_phase(config)

    optional_categories = optional_setup_categories(config, targets)
    optional_categories = _run_environment_selection_phase(
        config,
        targets,
        environments,
        optional_categories=optional_categories,
        no_install=no_install,
        ec2_host=ec2_host,
    )
    configure_default_ec2_host(config, ec2_host=ec2_host)

    missing_categories = _required_missing_categories(
        config,
        targets,
        environments,
        optional_categories,
    )
    optional_missing_categories = unconfigured_categories(
        environments,
        config,
        optional_categories=set(),
        only_categories=optional_categories,
    )
    if missing_categories:
        _print_incomplete_setup(missing_categories, optional_missing_categories)
        return 1

    _run_completion_phase(
        config,
        targets,
        optional_missing_categories=optional_missing_categories,
        no_install=no_install,
        esp32_port=esp32_port,
    )
    return 0


def _print_setup_intro() -> None:
    print(style("Gapless Agent Runtime の環境を設定します。", BOLD, CYAN))
    print(style("確認対象の状況を確認し、必要な項目を設定します。", DIM))
    print()


def _load_setup_config() -> dict:
    config = load_config()
    config.setdefault("selected_environments", {})
    return config


def _discover_targets(
    environments: Sequence[type[EnvironmentSetupOption]],
) -> list[TargetManifest] | None:
    try:
        return discover_target_manifests(environments)
    except TargetManifestValidationError as error:
        print(style("Target manifest に問題があります:", BOLD, RED), file=sys.stderr)
        for issue in error.issues:
            print(f"  - {issue}", file=sys.stderr)
        return None


def _configure_workspace_phase(config: dict) -> dict:
    if not sys.stdin.isatty():
        return config

    active_workspace_root = configure_workspace_root(config)
    print()
    if active_workspace_root is None:
        return config

    selected_config = load_config(workspace_selector=active_workspace_root)
    selected_config.setdefault("selected_environments", {})
    return selected_config


def _run_environment_selection_phase(
    config: dict,
    targets: Sequence[TargetManifest],
    environments: Sequence[type[EnvironmentSetupOption]],
    *,
    optional_categories: set[str],
    no_install: bool,
    ec2_host: str | None,
) -> set[str]:
    redraw_notice: str | None = None
    while True:
        _begin_selection_screen(redraw_notice)
        redraw_notice = None

        configure_target(config, targets)
        print()
        categories = print_environment_overview(
            environments,
            config,
            optional_categories=optional_categories,
            start_index=2,
        )
        category_choice = select_setup_category(
            categories,
            config,
            optional_categories=optional_categories,
            start_index=2,
            target_configured=selected_target_manifest(config, targets) is not None,
        )

        if category_choice is SetupMenuChoice.CANCELLED:
            break
        if category_choice is SetupMenuChoice.TARGET:
            selected = select_target(targets)
            if selected is None:
                break
            save_selected_target(config, selected)
            redraw_notice = f"更新しました: Target = {selected.display_name}"
            optional_categories = optional_setup_categories(config, targets)
            continue

        category = category_choice
        selection = select_environment_for_category(category, config)
        if selection.status is EnvironmentSelectionStatus.CANCELLED:
            break
        if selection.status is EnvironmentSelectionStatus.SKIPPED:
            continue

        environment = selection.environment
        if environment is None:
            raise RuntimeError("chosen environment selection has no environment")
        result = ensure_environment_dependencies(
            environment,
            config=config,
            no_install=no_install,
        )
        if result != 0:
            break

        config["selected_environments"][environment.category_id] = environment.environment_id
        save_config(config)
        redraw_notice = f"更新しました: {category.name} = {environment.display_name}"

    return optional_categories


def _begin_selection_screen(redraw_notice: str | None) -> None:
    if redraw_notice is None:
        print()
        return
    clear_setup_screen()
    print(style(redraw_notice, GREEN))
    print()


def _required_missing_categories(
    config: dict,
    targets: Sequence[TargetManifest],
    environments: Sequence[type[EnvironmentSetupOption]],
    optional_categories: set[str],
) -> list[str]:
    missing: list[str] = []
    if targets and selected_target_manifest(config, targets) is None:
        missing.append("Target")
    if config.get("selected_environments", {}).get("simulator") == "ssh_remote" and default_ec2_host(config) is None:
        missing.append("Simulation Runtime host (--ec2-host)")
    missing.extend(
        unconfigured_categories(
            environments,
            config,
            optional_categories=optional_categories,
        )
    )
    return missing


def _print_incomplete_setup(
    missing_categories: Sequence[str],
    optional_missing_categories: Sequence[str],
) -> None:
    print()
    print(style("未完了のセットアップ:", BOLD, RED))
    for category_name in missing_categories:
        print(f"  - {style(category_name, RED)}")
    _print_optional_missing_categories(optional_missing_categories)


def _run_completion_phase(
    config: dict,
    targets: Sequence[TargetManifest],
    *,
    optional_missing_categories: Sequence[str],
    no_install: bool,
    esp32_port: str | None,
) -> None:
    print()
    selected_target = selected_target_manifest(config, targets)
    if selected_target is not None:
        prepare_target_backend(selected_target)
        print()

    print_terminal_bridge_status(offer_install=not no_install)
    print()
    configure_esp32_serial_port(config, esp32_port=esp32_port)
    print()
    configure_target_connection(config)
    print()
    print_target_next_steps(config)
    print()

    _print_optional_missing_categories(optional_missing_categories)
    print(style("初期化が完了しました。", BOLD, GREEN))


def _print_optional_missing_categories(categories: Sequence[str]) -> None:
    if not categories:
        return
    print(style("あとで設定できる項目:", BOLD, YELLOW))
    for category_name in categories:
        print(f"  - {style(category_name, YELLOW)}")


def ensure_gar_tools_for_setup() -> None:
    root = ensure_gar_tools_available(auto_clone=True)
    print(style("GAR Tools:", BOLD, BLUE))
    if root is None:
        print(f"  {style('未取得', YELLOW)}")
        print(
            f"     {style('gar-tools を .gar/tools に取得できませんでした。'
            'ネットワークまたは git を確認してください。', DIM)}"
        )
        return
    print(f"  {style('利用可能', GREEN)} {style(str(root), DIM)}")


def clear_setup_screen() -> None:
    if not sys.stdout.isatty():
        return
    print("\033[2J\033[H", end="")


def print_terminal_bridge_status(*, offer_install: bool) -> None:
    installed_path = installed_vscode_terminal_bridge_path()
    print(style("VSCode Terminal Bridge:", BOLD, BLUE))
    if installed_path is not None:
        print(f"  {style('導入済み', GREEN)} {style(str(installed_path), DIM)}")
        return

    print(f"  {style('未導入', YELLOW)}")
    print(f"     {style('AI が VSCode の見える terminal へ実行要求を送るための拡張です。', DIM)}")
    if not offer_install or not sys.stdin.isatty():
        print(f"     {style('導入するには make init を実行してください。', DIM)}")
        return

    answer = safe_input(
        "VSCode Terminal Bridge をインストールしますか？ [Y/n]: ",
        default_on_eof="n",
    ).lower()
    if answer not in ("", "y", "yes"):
        print(f"     {style('あとで make init で導入できます。', DIM)}")
        return

    if install_vscode_terminal_bridge() == 0:
        print(
            style(
                "VSCode Terminal Bridge をインストールしました。" "VSCode window を reload してください。",
                GREEN,
            )
        )
    else:
        print(style("VSCode Terminal Bridge のインストールに失敗しました。", RED))
