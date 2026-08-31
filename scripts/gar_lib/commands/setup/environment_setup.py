"""Environment selection phase for ``gar config``."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from scripts.gar_lib.core.config import (
    default_ec2_host,
    is_valid_runtime_host,
    save_config,
    set_default_ec2_host,
)
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption
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

EnvironmentOption = type[EnvironmentSetupOption]


@dataclass(frozen=True)
class EnvironmentCategory:
    """One setup category and the concrete environments offered for it."""

    id: str
    name: str
    environments: tuple[EnvironmentOption, ...]


class SetupMenuChoice(Enum):
    TARGET = "target"
    CANCELLED = "cancelled"


class EnvironmentSelectionStatus(Enum):
    CHOSEN = "chosen"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EnvironmentSelection:
    """Explicit result of selecting an environment from one category."""

    status: EnvironmentSelectionStatus
    environment: EnvironmentOption | None = None

    @classmethod
    def chosen(cls, environment: EnvironmentOption) -> EnvironmentSelection:
        return cls(EnvironmentSelectionStatus.CHOSEN, environment)

    @classmethod
    def skipped(cls) -> EnvironmentSelection:
        return cls(EnvironmentSelectionStatus.SKIPPED)

    @classmethod
    def cancelled(cls) -> EnvironmentSelection:
        return cls(EnvironmentSelectionStatus.CANCELLED)


def configure_default_ec2_host(config: dict, *, ec2_host: str | None) -> None:
    selected_simulation = config.get("selected_environments", {}).get("simulator")
    if selected_simulation != "ssh_remote":
        return
    selected_provider = config.get("selected_environments", {}).get("simulation_host")
    if selected_provider not in {None, "aws_ec2"}:
        return

    current_host = default_ec2_host(config)
    if config.pop("_invalid_ec2_host", False):
        ec2 = config.get("ec2")
        if isinstance(ec2, dict):
            ec2.pop("host", None)
        save_config(config)
        print(f"  {style('不正な既定 host を削除しました。', YELLOW)}")

    if ec2_host:
        set_default_ec2_host(config, ec2_host)
        _set_generic_simulation_host(config, ec2_host)
        save_config(config)
        print(f"Runtime host: {style(ec2_host, BOLD, GREEN)}")
        return

    print(style("Simulation Runtime:", BOLD, BLUE))
    print("  SSH config の Host 名で接続します（鍵なども同じ設定を使用します）。")
    print(f"  現在の SSH Host: {style(current_host or '(未設定)', BOLD)}")
    if not sys.stdin.isatty():
        return

    selected_host = _prompt_runtime_host(current_host)
    if selected_host != current_host:
        set_default_ec2_host(config, selected_host)
        _set_generic_simulation_host(config, selected_host)
        save_config(config)
        print(f"  {style('更新しました:', GREEN)} {selected_host}")


def _set_generic_simulation_host(config: dict, host: str) -> None:
    settings = config.setdefault("simulation_host", {})
    if not isinstance(settings, dict):
        settings = {}
        config["simulation_host"] = settings
    settings["provider"] = "aws_ec2"
    settings["host"] = host


def _prompt_runtime_host(current_host: str | None) -> str:
    while True:
        answer = safe_input(
            f"  SSH Host 名 [{current_host or '入力必須'}]: ",
            default_on_eof=current_host or "",
        )
        selected_host = answer or current_host
        if selected_host is not None and is_valid_runtime_host(selected_host):
            return selected_host
        invalid_host_message = (
            "host には制御文字や空白を含められません。" "SSH config の host 名または IP address を入力してください。"
        )
        print(f"  {style(invalid_host_message, RED)}")


def ensure_environment_dependencies(
    environment: EnvironmentOption,
    *,
    config: dict | None = None,
    no_install: bool = False,
) -> int:
    missing = environment.missing_commands()

    print()
    print("選択: " f"{style(environment.display_name, BOLD)} " f"{style(f'({environment.environment_id})', DIM)}")

    if not missing:
        if config is not None:
            environment.record_detected_configuration(config)
        print(style(f"{environment.display_name} に必要なコマンドは見つかりました。", GREEN))
        return 0

    print(style("不足しているコマンド:", BOLD, YELLOW))
    for command in missing:
        print(f"  - {style(command, YELLOW)}")

    if no_install:
        print()
        print(environment.install_hint(missing))
        return 1

    print()
    answer = safe_input(
        "不足コマンドのインストール/案内を実行しますか？ [Y/n]: ",
        default_on_eof="n",
    )
    if answer.lower() not in ("", "y", "yes"):
        print(environment.install_hint(missing))
        return 1

    result = environment.install_dependencies(missing)
    if result != 0:
        return result

    remaining = environment.missing_commands()
    if remaining:
        print()
        print(style("まだ不足しているコマンド:", BOLD, RED))
        for command in remaining:
            print(f"  - {style(command, RED)}")
        return 1

    if config is not None:
        environment.record_detected_configuration(config)
    print()
    print(style(f"{environment.display_name} に必要なコマンドは見つかりました。", GREEN))
    return 0


def print_environment_overview(
    environments: Sequence[EnvironmentOption],
    config: dict,
    *,
    optional_categories: set[str] | None = None,
    start_index: int = 1,
) -> list[EnvironmentCategory]:
    categories = grouped_environments(environments)
    selected_environments = config["selected_environments"]
    optional_categories = optional_categories or set()

    for category_index, category in enumerate(categories):
        if category_index > 0:
            print()
        category_number = start_index + category_index
        optional_text = f" {style('(後で設定可)', YELLOW)}" if category.id in optional_categories else ""
        print(style(f"{category_number}. {category.name}", BOLD, CYAN) + optional_text)

        selected = environment_by_id(
            category.environments,
            selected_environments.get(category.id),
        )
        if selected is None:
            print(f"  {style('未設定', BOLD, YELLOW)}")
            print(f"     {style('この項目を選ぶと利用する環境を選択できます。', DIM)}")
            continue

        status = _environment_status_text(selected.missing_commands())
        print(f"  {status} " f"{style(selected.display_name, BOLD)} " f"{style(f'({selected.environment_id})', DIM)}")
        print(f"     {style(selected.description, DIM)}")
        print(f"     {style('必要:', BLUE)} {_dependency_summary(selected)}")

    print()
    return categories


def select_setup_category(
    categories: Sequence[EnvironmentCategory],
    config: dict,
    *,
    optional_categories: set[str] | None = None,
    start_index: int = 1,
    target_configured: bool = True,
) -> EnvironmentCategory | SetupMenuChoice:
    optional_categories = optional_categories or set()
    default_index = (
        first_unconfigured_category_index(
            categories,
            config,
            optional_categories=optional_categories,
        )
        if target_configured
        else None
    )
    prompt = _setup_category_prompt(
        categories,
        default_index=default_index,
        optional_categories=optional_categories,
        start_index=start_index,
        target_configured=target_configured,
    )

    while True:
        raw = safe_input(prompt)
        if raw == "":
            if not target_configured:
                return SetupMenuChoice.TARGET
            if default_index is None:
                return SetupMenuChoice.CANCELLED
            return categories[default_index - 1]
        if raw.lower() in ("q", "quit", "exit"):
            return SetupMenuChoice.CANCELLED

        try:
            selected_number = int(raw)
        except ValueError:
            print(style("番号で入力してください。終了する場合は q を入力してください。", YELLOW))
            continue

        if selected_number == 1:
            return SetupMenuChoice.TARGET
        list_index = selected_number - start_index
        if 0 <= list_index < len(categories):
            return categories[list_index]

        last_index = start_index + len(categories) - 1
        print(style(f"1 または {start_index} から {last_index} の番号を入力してください。", YELLOW))


def _setup_category_prompt(
    categories: Sequence[EnvironmentCategory],
    *,
    default_index: int | None,
    optional_categories: set[str],
    start_index: int,
    target_configured: bool,
) -> str:
    if not target_configured:
        return "設定する項目番号を入力してください [1: Target] (qで終了): "
    if default_index is not None:
        default_category = categories[default_index - 1]
        default_number = start_index + default_index - 1
        return "設定する項目番号を入力してください " f"[{default_number}: {default_category.name}] " "(qで終了): "
    if optional_categories:
        return "設定する項目番号を入力してください " "(Enter/qで終了、後で設定可の項目も番号で設定できます): "
    return "設定する項目番号を入力してください (Enter/qで終了): "


def select_environment_for_category(
    category: EnvironmentCategory,
    config: dict,
) -> EnvironmentSelection:
    selected = environment_by_id(
        category.environments,
        config["selected_environments"].get(category.id),
    )
    if selected is not None:
        if selected.missing_commands():
            return EnvironmentSelection.chosen(selected)
        if not _confirm_environment_change(category, selected):
            return EnvironmentSelection.skipped()

    _print_environment_menu(category)
    return _prompt_environment(category.environments)


def _confirm_environment_change(
    category: EnvironmentCategory,
    selected: EnvironmentOption,
) -> bool:
    print()
    print(f"{style(category.name, BOLD, CYAN)} は " f"{style(selected.display_name, BOLD)} で設定済みです。")
    answer = safe_input(
        "別の環境に変更しますか？ [y/N]: ",
        default_on_eof="n",
    ).lower()
    return answer in ("y", "yes")


def _print_environment_menu(category: EnvironmentCategory) -> None:
    print()
    print(style(f"[{category.name}]", BOLD, CYAN))
    print(style("利用する環境を選択してください:", BOLD))
    print()
    for index, environment in enumerate(category.environments, start=1):
        print(f"  {style(str(index) + '.', BOLD)} {style(environment.display_name, BOLD)}")
        print(f"     {style(environment.description, DIM)}")
        print(f"     {style('必要:', BLUE)} {_dependency_summary(environment)}")
        print()


def _prompt_environment(
    environments: Sequence[EnvironmentOption],
) -> EnvironmentSelection:
    while True:
        raw = safe_input("番号を入力してください [1]: ")
        if raw == "":
            return EnvironmentSelection.chosen(environments[0])
        if raw.lower() in ("q", "quit", "exit"):
            return EnvironmentSelection.cancelled()

        try:
            selected_index = int(raw)
        except ValueError:
            print(style("番号で入力してください。", YELLOW))
            continue

        if 1 <= selected_index <= len(environments):
            return EnvironmentSelection.chosen(environments[selected_index - 1])
        print(style(f"1 から {len(environments)} の番号を入力してください。", YELLOW))


def unconfigured_categories(
    environments: Sequence[EnvironmentOption],
    config: dict,
    *,
    optional_categories: set[str] | None = None,
    only_categories: set[str] | None = None,
) -> list[str]:
    missing: list[str] = []
    selected_environments = config["selected_environments"]
    optional_categories = optional_categories or set()

    for category in grouped_environments(environments):
        if only_categories is not None and category.id not in only_categories:
            continue
        if category.id in optional_categories:
            continue
        selected = environment_by_id(
            category.environments,
            selected_environments.get(category.id),
        )
        if selected is None or selected.missing_commands():
            missing.append(category.name)
    return missing


def first_unconfigured_category_index(
    categories: Sequence[EnvironmentCategory],
    config: dict,
    *,
    optional_categories: set[str] | None = None,
) -> int | None:
    selected_environments = config["selected_environments"]
    optional_categories = optional_categories or set()

    for index, category in enumerate(categories, start=1):
        if category.id in optional_categories:
            continue
        selected = environment_by_id(
            category.environments,
            selected_environments.get(category.id),
        )
        if selected is None or selected.missing_commands():
            return index

    for index, category in enumerate(categories, start=1):
        if category.id not in optional_categories:
            continue
        selected = environment_by_id(
            category.environments,
            selected_environments.get(category.id),
        )
        if selected is None or selected.missing_commands():
            return index
    return None


def grouped_environments(
    environments: Sequence[EnvironmentOption],
) -> list[EnvironmentCategory]:
    groups: list[EnvironmentCategory] = []
    for environment in environments:
        if groups and groups[-1].id == environment.category_id:
            previous = groups[-1]
            groups[-1] = EnvironmentCategory(
                id=previous.id,
                name=previous.name,
                environments=(*previous.environments, environment),
            )
        else:
            groups.append(
                EnvironmentCategory(
                    id=environment.category_id,
                    name=environment.category_name,
                    environments=(environment,),
                )
            )
    return groups


def environment_by_id(
    environments: Sequence[EnvironmentOption],
    environment_id: str | None,
) -> EnvironmentOption | None:
    if environment_id is None:
        return None
    return next(
        (environment for environment in environments if environment.environment_id == environment_id),
        None,
    )


def _dependency_summary(environment: EnvironmentOption) -> str:
    statuses = environment.dependency_status()
    if not statuses:
        return style("なし", DIM)
    return ", ".join(_dependency_status_text(status.name, status.installed) for status in statuses)


def _environment_status_text(missing: list[str]) -> str:
    if missing:
        return style("未設定", BOLD, YELLOW)
    return style("設定済み", BOLD, GREEN)


def _dependency_status_text(name: str, installed: bool) -> str:
    if installed:
        return f"{name}({style('OK', GREEN)})"
    return f"{name}({style('未インストール', YELLOW)})"
