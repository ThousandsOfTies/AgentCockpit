"""Machine-local connection settings for SimulationHost providers."""

from __future__ import annotations

import sys

from scripts.gar_lib.commands.setup.environment_setup import configure_default_ec2_host
from scripts.gar_lib.core.config import is_valid_runtime_host, save_config
from scripts.gar_lib.vscode.terminal_ui import BLUE, BOLD, DIM, GREEN, RED, YELLOW, safe_input, style


def configure_simulation_host_connection(
    config: dict,
    *,
    ec2_host: str | None = None,
) -> None:
    provider = config.get("selected_environments", {}).get("simulation_host")
    if provider == "aws_ec2":
        _record_provider(config, provider)
        configure_default_ec2_host(config, ec2_host=ec2_host)
        return
    if provider != "virtualbox":
        return
    _record_provider(config, provider)
    _configure_virtualbox(config)


def _record_provider(config: dict, provider: str) -> None:
    settings = config.setdefault("simulation_host", {})
    if not isinstance(settings, dict):
        settings = {}
        config["simulation_host"] = settings
    if settings.get("provider") != provider:
        # Host, address, architecture, and port all describe one provider.
        # Carrying them across a provider switch can route SSH or artifacts to
        # the previous machine, so retain them only for legacy provider-less
        # settings or when the provider itself is unchanged.
        if settings.get("provider") is not None:
            settings.clear()
        settings["provider"] = provider
        save_config(config)


def _configure_virtualbox(config: dict) -> None:
    simulation_host = config.setdefault("simulation_host", {})
    virtualbox = config.setdefault("virtualbox", {})
    if not isinstance(simulation_host, dict) or not isinstance(virtualbox, dict):
        return
    current_host = simulation_host.get("host") if isinstance(simulation_host.get("host"), str) else ""
    current_vm = virtualbox.get("vm") if isinstance(virtualbox.get("vm"), str) else ""

    print(style("Local Sim Host:", BOLD, BLUE))
    print(f"  SSH alias: {style(current_host or '未設定', BOLD, GREEN if current_host else YELLOW)}")
    print(f"  VirtualBox VM: {style(current_vm or '未設定', BOLD, GREEN if current_vm else YELLOW)}")
    if not sys.stdin.isatty():
        if not current_host or not current_vm:
            print(f"     {style('対話terminalでgar setupを実行してVM名とSSH aliasを保存してください。', DIM)}")
        return

    host = _prompt_ssh_alias(current_host)
    vm = (
        safe_input(
            f"  VirtualBox VM名またはUUID [{current_vm or '入力必須'}]: ",
            default_on_eof=current_vm,
        ).strip()
        or current_vm
    )
    changed = False
    if host and host != current_host:
        simulation_host["host"] = host
        changed = True
    if vm and vm != current_vm:
        virtualbox["vm"] = vm
        changed = True
    if changed:
        save_config(config)
        print(f"  {style('更新しました。', GREEN)}")


def _prompt_ssh_alias(current_host: str) -> str:
    while True:
        host = (
            safe_input(
                f"  Ubuntu VMのSSH config Host名 [{current_host or '入力必須'}]: ",
                default_on_eof=current_host,
            ).strip()
            or current_host
        )
        if host and is_valid_runtime_host(host):
            return host
        print(f"  {style('空白を含まないSSH config Host名を入力してください。', RED)}")
